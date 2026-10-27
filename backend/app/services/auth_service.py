from datetime import datetime, timezone
import secrets
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import check_clock_state, decrypt, digest, passwords
from app.models import Branch, Company, License, LicenseToken, User
from app.schemas.auth import BootstrapRequest, LoginRequest
from app.services.license_service import verify_company_binding, verify_stored_license, verify_session_license


def bootstrap_admin(session: Session, data: BootstrapRequest, activation_token: str, settings: Settings) -> None:
    token = session.scalar(select(LicenseToken).where(
        LicenseToken.token_hash == digest(activation_token, settings.token_pepper),
        LicenseToken.token_type == "license_activation",
        LicenseToken.revoked_at.is_(None),
        LicenseToken.expires_at > func.now(),
    ))
    if token is None:
        raise HTTPException(401, "Token de activación inválido")
    if session.scalar(select(User.id).where(User.company_id == token.license.company_id)):
        raise HTTPException(409, "El administrador ya fue creado")
    session.add(User(id=uuid4(), company_id=token.license.company_id, email=str(data.email).lower(), password_hash=passwords.hash(data.password), is_admin=True))
    token.revoked_at = datetime.now(timezone.utc)
    session.commit()


def authenticate(session: Session, data: LoginRequest, settings: Settings) -> str:
    if settings.clock_state_path is not None:
        try:
            check_clock_state(settings.clock_state_path)
        except ValueError as exc:
            raise HTTPException(401, "El reloj del sistema parece haber retrocedido") from exc
    user = session.scalar(select(User).where(User.email == str(data.email).lower(), User.is_active.is_(True)))
    if user is None:
        raise HTTPException(401, "Credenciales inválidas")
    try:
        passwords.verify(user.password_hash, data.password)
    except Exception as exc:
        raise HTTPException(401, "Credenciales inválidas") from exc
    license_row = None
    now = datetime.now(timezone.utc)
    for candidate in session.scalars(select(License).where(License.company_id == user.company_id).order_by(License.created_at.desc())).all():
        try:
            signed_payload = verify_stored_license(candidate, settings)
            company = session.get(Company, candidate.company_id)
            if company is None:
                continue
            verify_company_binding(signed_payload, company, settings)
        except Exception:
            continue
        if signed_payload.valid_from <= now < signed_payload.valid_until:
            license_row = candidate
            break
    company = session.get(Company, user.company_id)
    if license_row is None or company is None:
        raise HTTPException(401, "Credenciales inválidas")
    token_value = secrets.token_urlsafe(32)
    session.add(LicenseToken(id=uuid4(), license_id=license_row.id, user_id=user.id, token_type="session", token_hash=digest(token_value, settings.token_pepper), company_fingerprint=company.name_fingerprint, company_name_ciphertext=company.name_ciphertext, expires_at=license_row.valid_until))
    session.commit()
    return token_value


def get_me(session: Session, token_value: str, settings: Settings) -> dict:
    token = session.scalar(select(LicenseToken).where(
        LicenseToken.token_hash == digest(token_value, settings.token_pepper),
        LicenseToken.token_type == "session",
        LicenseToken.revoked_at.is_(None),
        LicenseToken.expires_at > func.now(),
    ))
    if token is None or token.user is None or token.license is None:
        raise HTTPException(401, "Sesión inválida o licencia caducada")
    user = token.user
    if not user.is_active:
        raise HTTPException(401, "Usuario desactivado")
    license_row = token.license
    company = session.get(Company, user.company_id)
    if company is None:
        raise HTTPException(401, "Empresa no disponible")
    try:
        verify_session_license(license_row, company, settings)
    except Exception as exc:
        raise HTTPException(401, "Licencia inválida") from exc
    return {
        "company_name": decrypt(company.name_ciphertext, settings),
        "license_valid_until": token.expires_at,
        "user_email": user.email,
        "is_admin": user.is_admin,
        "edition": license_row.edition,
        "max_users": license_row.max_users,
        "max_branches": license_row.max_branches,
        "modules": license_row.modules,
        "user_count": session.scalar(select(func.count(User.id)).where(User.company_id == user.company_id)),
        "branch_count": session.scalar(select(func.count(Branch.id)).where(Branch.company_id == user.company_id)),
    }


def logout(session: Session, token_value: str, settings: Settings) -> None:
    """Revoke only this session; repeated logout requests are harmless."""
    session.execute(update(LicenseToken).where(
        LicenseToken.token_hash == digest(token_value, settings.token_pepper),
        LicenseToken.token_type == "session",
        LicenseToken.revoked_at.is_(None),
    ).values(revoked_at=datetime.now(timezone.utc)))
    session.commit()
