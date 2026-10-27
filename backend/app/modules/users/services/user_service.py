from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import passwords
from app.models import Company, License, LicenseToken, User
from app.schemas.user import UserCreate, UserUpdate


USER_EMAIL_CONSTRAINTS = {"uq_users_company_email", "users_company_id_email_key"}


def _is_email_constraint(error: IntegrityError) -> bool:
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    return constraint in USER_EMAIL_CONSTRAINTS


def _lock_company(session: Session, company_id: UUID) -> Company:
    company = session.scalar(select(Company).where(Company.id == company_id).with_for_update())
    if company is None:
        raise HTTPException(404, "Empresa no encontrada")
    return company


def _revoke_sessions(session: Session, user_id: UUID) -> None:
    session.execute(
        update(LicenseToken)
        .where(
            LicenseToken.user_id == user_id,
            LicenseToken.token_type == "session",
            LicenseToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )


def list_users(session: Session, user: User) -> list[User]:
    return list(session.scalars(select(User).where(User.company_id == user.company_id).order_by(User.email)).all())


def create_user(session: Session, actor: User, data: UserCreate) -> User:
    _lock_company(session, actor.company_id)
    license_row = session.scalar(select(License).where(License.company_id == actor.company_id).order_by(License.created_at.desc()).limit(1))
    if license_row is None:
        raise HTTPException(409, "La instalación no tiene licencia")
    count = session.scalar(select(func.count(User.id)).where(User.company_id == actor.company_id)) or 0
    if count >= license_row.max_users:
        raise HTTPException(409, "Se alcanzó el límite de usuarios de la licencia")
    user = User(
        id=uuid4(),
        company_id=actor.company_id,
        email=str(data.email).lower(),
        password_hash=passwords.hash(data.password),
        is_admin=False,
        is_active=True,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _is_email_constraint(error):
            raise HTTPException(409, "Ya existe un usuario con ese email") from error
        raise
    session.refresh(user)
    return user


def update_user(session: Session, actor: User, user_id: UUID, data: UserUpdate) -> User:
    _lock_company(session, actor.company_id)
    user = session.scalar(select(User).where(User.id == user_id, User.company_id == actor.company_id).with_for_update())
    if user is None:
        raise HTTPException(404, "Usuario no encontrado")

    values = data.model_dump(exclude_unset=True)
    resulting_active_admin = values.get("is_active", user.is_active) and values.get("is_admin", user.is_admin)
    current_active_admin = user.is_active and user.is_admin
    if current_active_admin and not resulting_active_admin:
        active_admins = session.scalar(select(func.count(User.id)).where(User.company_id == actor.company_id, User.is_active.is_(True), User.is_admin.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(409, "No se puede dejar la instalación sin administrador activo")

    password_changed = "password" in values
    if "email" in values:
        user.email = str(values["email"]).lower()
    if password_changed:
        user.password_hash = passwords.hash(values["password"])
    for field in ("is_admin", "is_active"):
        if field in values:
            setattr(user, field, values[field])
    if password_changed or values.get("is_active") is False:
        _revoke_sessions(session, user.id)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _is_email_constraint(error):
            raise HTTPException(409, "Ya existe un usuario con ese email") from error
        raise
    session.refresh(user)
    return user
