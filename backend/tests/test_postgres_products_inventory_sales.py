import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Branch, Company, License, Product, User
from app.schemas.branch import BranchCreate
from app.services.branch_service import create_branch
from app.modules.inventory.models.stock import MovementType, StockBalance, StockMovement
from app.modules.inventory.schemas.stock_adjustment import StockAdjustmentCreate, StockReceiptCreate
from app.modules.inventory.services.stock_adjustment_service import confirm_adjustment, create_adjustment, receive_stock
from app.modules.sales.models.sale import Sale, SaleStatus
from app.modules.products.services.product_service import create_product
from app.modules.sales.schemas.sale import SaleCreate
from app.modules.sales.services.sale_service import confirm_sale, create_sale
from fastapi import HTTPException


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
    other_branch = Branch(id=uuid4(), company_id=other_company.id, name="Other")
    product = Product(id=uuid4(), company_id=company.id, code="SKU-1", name="Producto", price=Decimal("10.00"), cost=Decimal("5.00"))
    other_product = Product(id=uuid4(), company_id=other_company.id, code="SKU-1", name="Otro", price=Decimal("10.00"), cost=Decimal("5.00"))
    license_row = License(id=uuid4(), company_id=company.id, edition="base", max_users=3, max_branches=2, modules=["dashboard"], valid_from=datetime.now(timezone.utc) - timedelta(days=1), valid_until=datetime.now(timezone.utc) + timedelta(days=1), installation_id="test-installation", key_id="test-key")
    with factory() as session:
        session.add_all([company, other_company, admin, regular, branch, other_branch, product, other_product, license_row])
        session.add(StockBalance(id=uuid4(), company_id=company.id, branch_id=branch.id, product_id=product.id, quantity=Decimal("5")))
        session.commit()
    yield engine, factory, SimpleNamespace(id=admin.id, company_id=company.id, is_admin=True), SimpleNamespace(id=regular.id, company_id=company.id, is_admin=False), branch, product, other_product
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE companies CASCADE"))
    engine.dispose()


def test_product_duplicate_race_returns_one_success_and_one_conflict(database):
    engine, _factory, admin, _regular, _branch, _product, _other_product = database
    barrier = __import__("threading").Barrier(2)

    def worker():
        with Session(engine) as session:
            barrier.wait()
            try:
                create_product(session, admin, __import__("app.modules.products.schemas.product", fromlist=["ProductCreate"]).ProductCreate(code="race", name="Race"))
                return "created"
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _item: worker(), range(2)))
    assert sorted(results, key=str) == [409, "created"]


def test_sale_confirmation_is_atomic_and_idempotent(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    sale_data = SaleCreate(branch_id=branch.id, items=[{"product_id": product.id, "quantity": 2, "unit_price": "10.00"}])
    with factory() as session:
        sale = create_sale(session, admin, sale_data)
        sale_id = sale.id
    with factory() as session:
        confirmed = confirm_sale(session, admin, sale_id)
        assert confirmed.status == SaleStatus.CONFIRMED
    with factory() as session:
        balance = session.scalar(select(StockBalance).where(StockBalance.product_id == product.id))
        movements = list(session.scalars(select(StockMovement).where(StockMovement.reference_id == sale_id)).all())
        assert balance.quantity == Decimal("3.0000")
        assert len(movements) == 1
        assert movements[0].movement_type == MovementType.OUT
        with pytest.raises(HTTPException, match="borrador"):
            confirm_sale(session, admin, sale_id)


def test_sale_confirmation_rolls_back_when_stock_is_insufficient(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    sale_data = SaleCreate(branch_id=branch.id, items=[{"product_id": product.id, "quantity": 99, "unit_price": "10.00"}])
    with factory() as session:
        sale = create_sale(session, admin, sale_data)
        sale_id = sale.id
    with factory() as session:
        with pytest.raises(HTTPException, match="stock"):
            confirm_sale(session, admin, sale_id)
    with factory() as session:
        persisted = session.get(Sale, sale_id)
        balance = session.scalar(select(StockBalance).where(StockBalance.product_id == product.id))
        movements = list(session.scalars(select(StockMovement).where(StockMovement.reference_id == sale_id)).all())
        assert persisted.status == SaleStatus.DRAFT
        assert balance.quantity == Decimal("5.0000")
        assert movements == []


def test_concurrent_confirmation_produces_one_movement(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    with factory() as session:
        sale = create_sale(session, admin, SaleCreate(branch_id=branch.id, items=[{"product_id": product.id, "quantity": 1, "unit_price": "10"}]))
        sale_id = sale.id
    barrier = __import__("threading").Barrier(2)

    def worker():
        with factory() as session:
            barrier.wait()
            try:
                confirm_sale(session, admin, sale_id)
                return "confirmed"
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _item: worker(), range(2)))
    assert sorted(results, key=str) == [409, "confirmed"]
    with factory() as session:
        assert session.scalar(select(StockMovement).where(StockMovement.reference_id == sale_id)) is not None
        assert len(list(session.scalars(select(StockMovement).where(StockMovement.reference_id == sale_id)).all())) == 1


def test_two_different_sales_compete_for_insufficient_stock(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    with factory() as session:
        sale_ids = [
            create_sale(session, admin, SaleCreate(branch_id=branch.id, items=[{"product_id": product.id, "quantity": 4, "unit_price": "10"}])).id,
            create_sale(session, admin, SaleCreate(branch_id=branch.id, items=[{"product_id": product.id, "quantity": 4, "unit_price": "10"}])).id,
        ]
    barrier = __import__("threading").Barrier(2)

    def worker(sale_id):
        with factory() as session:
            barrier.wait()
            try:
                confirm_sale(session, admin, sale_id)
                return "confirmed"
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, sale_ids))
    assert sorted(results, key=str) == [409, "confirmed"]
    with factory() as session:
        balance = session.scalar(select(StockBalance).where(StockBalance.product_id == product.id))
        assert balance.quantity == Decimal("1.0000")
        assert session.scalar(select(StockMovement).where(StockMovement.reference_type == "sale").where(StockMovement.product_id == product.id)) is not None


def test_multiline_sale_rolls_back_all_stock_when_later_line_fails(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    second_product = Product(id=uuid4(), company_id=admin.company_id, code="SKU-2", name="Segundo", price=Decimal("10"), cost=Decimal("5"))
    with factory() as session:
        session.add(second_product)
        session.add(StockBalance(id=uuid4(), company_id=admin.company_id, branch_id=branch.id, product_id=second_product.id, quantity=Decimal("1")))
        session.commit()
        sale = create_sale(session, admin, SaleCreate(branch_id=branch.id, items=[
            {"product_id": product.id, "quantity": 1, "unit_price": "10"},
            {"product_id": second_product.id, "quantity": 2, "unit_price": "10"},
        ]))
        sale_id = sale.id
    with factory() as session:
        with pytest.raises(HTTPException, match="stock"):
            confirm_sale(session, admin, sale_id)
    with factory() as session:
        balances = {balance.product_id: balance.quantity for balance in session.scalars(select(StockBalance).where(StockBalance.product_id.in_([product.id, second_product.id])))}
        assert balances[product.id] == Decimal("5.0000")
        assert balances[second_product.id] == Decimal("1.0000")
        assert session.scalar(select(StockMovement).where(StockMovement.reference_id == sale_id)) is None
        assert session.get(Sale, sale_id).status == SaleStatus.DRAFT


def test_receipt_is_atomic_idempotent_and_increments_stock(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    data = StockReceiptCreate(operation_id=uuid4(), branch_id=branch.id, items=[{"product_id": product.id, "quantity": "3"}])
    with factory() as session:
        first = receive_stock(session, admin, data)
        second = receive_stock(session, admin, data)
        assert first.operation_id == second.operation_id
    with factory() as session:
        balance = session.scalar(select(StockBalance).where(StockBalance.product_id == product.id))
        movements = list(session.scalars(select(StockMovement).where(StockMovement.reference_id == data.operation_id)).all())
        assert balance.quantity == Decimal("8.0000")
        assert len(movements) == 1
        assert movements[0].movement_type == MovementType.IN


def test_concurrent_receipt_and_adjustment_share_product_lock(database):
    engine, factory, admin, _regular, branch, product, _other_product = database
    adjustment_data = StockAdjustmentCreate(branch_id=branch.id, reason="merma", items=[{"product_id": product.id, "quantity": "2"}])
    receipt_data = StockReceiptCreate(operation_id=uuid4(), branch_id=branch.id, items=[{"product_id": product.id, "quantity": "3"}])
    barrier = __import__("threading").Barrier(2)

    def receive_worker():
        with factory() as session:
            barrier.wait()
            receive_stock(session, admin, receipt_data)
            return "receipt"

    def adjustment_worker():
        with factory() as session:
            barrier.wait()
            adjustment = create_adjustment(session, admin, adjustment_data)
            confirm_adjustment(session, admin, adjustment.id)
            return "adjustment"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted([pool.submit(receive_worker), pool.submit(adjustment_worker)], key=lambda future: future.result())
    assert [future.result() for future in results] == ["adjustment", "receipt"]
    with factory() as session:
        balance = session.scalar(select(StockBalance).where(StockBalance.product_id == product.id))
        assert balance.quantity == Decimal("6.0000")
        assert len(list(session.scalars(select(StockMovement).where(StockMovement.product_id == product.id)).all())) == 2


def test_branch_limit_is_serialized_by_company_lock(database):
    engine, factory, admin, _regular, _branch, _product, _other_product = database
    barrier = __import__("threading").Barrier(2)

    def worker(name):
        with factory() as session:
            barrier.wait()
            try:
                create_branch(session, admin, BranchCreate(name=name))
                return "created"
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, ["Norte", "Sur"]))
    assert sorted(results, key=str) == [409, "created"]
    with factory() as session:
        assert session.scalar(select(__import__("sqlalchemy", fromlist=["func"]).func.count(Branch.id)).where(Branch.company_id == admin.company_id)) == 2


def test_database_rejects_negative_stock_and_cross_company_sale(database):
    engine, factory, admin, _regular, branch, product, other_product = database
    with factory() as session:
        with pytest.raises(IntegrityError):
            session.add(StockBalance(id=uuid4(), company_id=admin.company_id, branch_id=branch.id, product_id=product.id, quantity=Decimal("-1")))
            session.commit()
        session.rollback()
        with pytest.raises(HTTPException, match="productos"):
            create_sale(session, admin, SaleCreate(branch_id=branch.id, items=[{"product_id": other_product.id, "quantity": 1, "unit_price": "1"}]))


def test_api_requires_authentication_and_enforces_admin(database, monkeypatch):
    engine, factory, admin, regular, _branch, _product, _other_product = database
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    from app.core.dependencies import get_current_user, get_db
    from app.main import app

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        assert client.get("/api/sales").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: regular
        assert client.post("/api/products", json={"code": "X", "name": "X"}).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: admin
        assert client.post("/api/products", json={"code": "X", "name": "X"}).status_code == 201
        receipt_response = client.post("/api/inventory/adjustments/receipts", json={
            "branch_id": str(_branch.id),
            "items": [{"product_id": str(_product.id), "quantity": "2"}],
        })
        assert receipt_response.status_code == 201
        assert receipt_response.json()["branch_id"] == str(_branch.id)
    finally:
        app.dependency_overrides.clear()
