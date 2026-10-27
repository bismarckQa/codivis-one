from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db, settings
from app.models import Company, LicenseToken, User
from app.services.license_service import verify_company_binding, verify_stored_license
from app.core.security import digest


def get_current_user(
    codivis_one_session: str | None = Cookie(default=None),
    session: Session = Depends(get_db),
) -> User:
    if not codivis_one_session:
        raise HTTPException(401, "Sesión requerida")
    token = session.scalar(select(LicenseToken).where(
        LicenseToken.token_hash == digest(codivis_one_session, settings.token_pepper),
        LicenseToken.token_type == "session",
        LicenseToken.revoked_at.is_(None),
        LicenseToken.expires_at > func.now(),
    ))
    if token is None or token.user is None or token.license is None:
        raise HTTPException(401, "Sesión inválida o licencia caducada")
    company = session.get(Company, token.user.company_id)
    if company is None:
        raise HTTPException(401, "Empresa no disponible")
    try:
        payload = verify_stored_license(token.license, settings)
        verify_company_binding(payload, company, settings)
    except Exception as exc:
        raise HTTPException(401, "Licencia inválida") from exc
    return token.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Se requieren permisos de administrador")
    return user
