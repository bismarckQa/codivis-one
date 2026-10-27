import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import make_url

from app.models import Branch, Company, License, LicenseToken, User
from app.modules.users.services.user_service import create_user, list_users, update_user
from app.schemas.user import UserCreate, UserUpdate


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required for PostgreSQL integration tests")


def _assert_isolated_test_database() -> None:
    database_name = make_url(TEST_DATABASE_URL).database
    primary_name = os.getenv("POSTGRES_DB", "codivis_one")
    if not database_name or database_name == primary_name or not database_name.endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must point to an exclusive database ending in _test")


@pytest.fixture()
def database():
    _assert_isolated_test_database()
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE companies CASCADE"))
    company = Company(id=uuid4(), name_ciphertext=b"company", name_fingerprint=uuid4().bytes)
    other_company = Company(id=uuid4(), name_ciphertext=b"other", name_fingerprint=uuid4().bytes)
    admin = User(id=uuid4(), company_id=company.id, email="admin@test.local", password_hash="not-used", is_admin=True)
    regular = User(id=uuid4(), company_id=company.id, email="user@test.local", password_hash="not-used", is_admin=False)
    branch = Branch(id=uuid4(), company_id=company.id, name="Central")
    license_row = License(
        id=uuid4(), company_id=company.id, edition="base", max_users=3, max_branches=1,
        modules=["dashboard"], valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        valid_until=datetime.now(timezone.utc) + timedelta(days=1), installation_id="test-installation",
        key_id="test-key",
    )
    with factory() as session:
        session.add_all([company, other_company, admin, regular, branch, license_row])
        session.commit()
    yield engine, factory, SimpleNamespace(id=admin.id, company_id=company.id, is_admin=True), SimpleNamespace(id=regular.id, company_id=company.id, is_admin=False), branch, license_row
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE companies CASCADE"))
    engine.dispose()


def valid_user(email: str) -> UserCreate:
    return UserCreate(email=email, password="Segura-1234!", password_confirmation="Segura-1234!")


def test_user_schema_is_strict_and_partial(database):
    with pytest.raises(Exception):
        UserCreate(email="admin@test.local", password="weak", password_confirmation="weak")
    with pytest.raises(Exception):
        UserUpdate(password="Segura-1234!")
    with pytest.raises(Exception):
        UserUpdate()
    assert UserUpdate(email=" ADMIN@example.com ").email == "admin@example.com"


def test_api_requires_admin_and_never_returns_password_hash(database):
    _engine, factory, admin, regular, _branch, _license = database
    from app.core.dependencies import get_current_user, get_db
    from app.main import app

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        assert client.get("/api/users").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: regular
        assert client.get("/api/users").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: admin
        created = client.post("/api/users", json={"email": "new@example.com", "password": "Segura-1234!", "password_confirmation": "Segura-1234!"})
        assert created.status_code == 201
        assert "password_hash" not in created.json()
        duplicate = client.post("/api/users", json={"email": "NEW@example.com", "password": "Segura-1234!", "password_confirmation": "Segura-1234!"})
        assert duplicate.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_user_limit_is_serialized_by_company_lock(database):
    engine, _factory, admin, _regular, _branch, _license = database
    barrier = __import__("threading").Barrier(2)

    def worker(index):
        with Session(engine) as session:
            barrier.wait()
            try:
                create_user(session, admin, valid_user(f"concurrent-{index}@example.com"))
                return "created"
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))
    assert sorted(results, key=str) == [409, "created"]


def test_last_admin_cannot_be_disabled_and_sessions_are_revoked(database):
    _engine, factory, admin, regular, _branch, license_row = database
    with factory() as session:
        with pytest.raises(HTTPException, match="administrador"):
            update_user(session, admin, admin.id, UserUpdate(is_active=False))
        token = LicenseToken(
            id=uuid4(), license_id=license_row.id, user_id=regular.id, token_type="session",
            token_hash=uuid4().bytes, company_fingerprint=b"fingerprint", company_name_ciphertext=b"company",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(token)
        session.commit()
        update_user(session, admin, regular.id, UserUpdate(is_active=False))
        session.refresh(token)
        assert token.revoked_at is not None


def test_password_change_revokes_sessions_and_listing_is_company_scoped(database):
    _engine, factory, admin, regular, _branch, license_row = database
    with factory() as session:
        other_company = session.scalar(select(Company).where(Company.id != admin.company_id))
        other_user = User(id=uuid4(), company_id=other_company.id, email="other@test.local", password_hash="hash", is_admin=True)
        token = LicenseToken(
            id=uuid4(), license_id=license_row.id, user_id=regular.id, token_type="session",
            token_hash=uuid4().bytes, company_fingerprint=b"fingerprint", company_name_ciphertext=b"company",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add_all([other_user, token])
        session.commit()
        update_user(session, admin, regular.id, UserUpdate(password="Nueva-1234!x", password_confirmation="Nueva-1234!x"))
        assert session.scalar(select(LicenseToken).where(LicenseToken.id == token.id)).revoked_at is not None
        listed = list_users(session, admin)
        assert {user.email for user in listed} == {"admin@test.local", "user@test.local"}
