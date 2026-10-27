from datetime import datetime, timezone
import secrets
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import activation_key_matches, canonical, check_clock_state, decrypt, digest, encrypt, verify_signature
from app.models import Company, License, LicenseToken, User
from app.schemas.license import LicensePayload, LicenseStatus, SignedLicense


EXPECTED_KEY_ID = "codivis-one-ed25519-1"


def validate_signed_license(document: dict[str, Any], settings: Settings, *, check_dates: bool = True) -> tuple[LicensePayload, dict[str, Any], str]:
    try:
        signed = SignedLicense.model_validate(document)
        if signed.payload.product != "codivis-one" or signed.payload.schema_version != 1:
            raise ValueError("unsupported license contract")
        if signed.payload.key_id != EXPECTED_KEY_ID:
            raise ValueError("unknown license key")
        raw_payload = document["payload"]
        verify_signature(raw_payload, signed.signature, settings.license_public_key_path, settings.license_public_key_sha256)
    except Exception as exc:
        raise HTTPException(400, "Licencia inválida o firma incorrecta") from exc

    if check_dates:
        if settings.clock_state_path is not None:
            try:
                check_clock_state(settings.clock_state_path)
            except ValueError as exc:
                raise HTTPException(400, "El reloj del sistema parece haber retrocedido") from exc
        now = datetime.now(timezone.utc)
        if signed.payload.activation_expires_at <= now:
            raise HTTPException(400, "El archivo de activación ha caducado")
        if signed.payload.valid_from > now:
            raise HTTPException(400, "La licencia todavía no está vigente")
        if signed.payload.valid_until <= now:
            raise HTTPException(400, "La licencia está caducada")
    return signed.payload, raw_payload, signed.signature


def verify_stored_license(license_row: License, settings: Settings) -> LicensePayload:
    if not license_row.signed_payload or not license_row.signature:
        raise ValueError("license has no signed document")
    payload, _raw_payload, _signature = validate_signed_license(
        {"payload": license_row.signed_payload, "signature": license_row.signature}, settings, check_dates=False,
    )
    if (
        payload.license_id != license_row.id
        or payload.edition != license_row.edition
        or payload.max_users != license_row.max_users
        or payload.max_branches != license_row.max_branches
        or payload.modules != license_row.modules
        or payload.valid_from != license_row.valid_from
        or payload.valid_until != license_row.valid_until
        or payload.installation_id != license_row.installation_id
        or payload.device_public_key != license_row.signed_payload.get("device_public_key")
        or payload.key_id != license_row.key_id
    ):
        raise ValueError("license row does not match signed document")
    return payload


def verify_company_binding(license_payload: LicensePayload, company: Company, settings: Settings) -> None:
    expected = digest(f"{license_payload.company_name}|{license_payload.installation_id}", settings.token_pepper)
    if company.name_fingerprint != expected:
        raise ValueError("license is not bound to the stored company")


def import_license(session: Session, payload: LicensePayload, raw_payload: dict[str, Any], signature: str, settings: Settings) -> str:
    if not activation_key_matches(payload.device_public_key, settings.activation_private_key_path):
        raise HTTPException(409, "La licencia no pertenece a este equipo")
    activation = secrets.token_urlsafe(32)
    company_fingerprint = digest(f"{payload.company_name}|{payload.installation_id}", settings.token_pepper)
    company = session.scalar(select(Company).where(Company.name_fingerprint == company_fingerprint))
    if company is None:
        company = Company(id=uuid4(), name_ciphertext=encrypt(payload.company_name, settings), name_fingerprint=company_fingerprint)
        session.add(company)
        session.flush()
    else:
        company.name_ciphertext = encrypt(payload.company_name, settings)

    license_row = session.get(License, payload.license_id)
    if license_row is not None and license_row.company_id != company.id:
        raise HTTPException(409, "La licencia ya pertenece a otra empresa")

    # Una instalación solo puede conservar una licencia. La empresa y sus
    # usuarios permanecen; se invalidan los tokens y se elimina la licencia
    # anterior antes de guardar la renovación.
    previous_licenses = session.scalars(select(License).where(
        License.company_id == company.id,
        License.id != payload.license_id,
    )).all()
    for previous in previous_licenses:
        session.query(LicenseToken).filter(LicenseToken.license_id == previous.id).delete(synchronize_session=False)
        session.delete(previous)

    if license_row is None:
        license_row = License(
            id=payload.license_id,
            company_id=company.id,
            edition=payload.edition,
            max_users=payload.max_users,
            max_branches=payload.max_branches,
            modules=payload.modules,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            installation_id=payload.installation_id,
            key_id=payload.key_id,
            signed_payload=raw_payload,
            signature=signature,
            created_at=payload.created_at,
        )
        session.add(license_row)
    else:
        license_row.company_id = company.id
        license_row.edition = payload.edition
        license_row.max_users = payload.max_users
        license_row.max_branches = payload.max_branches
        license_row.modules = payload.modules
        license_row.valid_from = payload.valid_from
        license_row.valid_until = payload.valid_until
        license_row.installation_id = payload.installation_id
        license_row.key_id = payload.key_id
        license_row.signed_payload = raw_payload
        license_row.signature = signature

    session.query(LicenseToken).filter(
        LicenseToken.license_id == payload.license_id,
        LicenseToken.token_type == "license_activation",
        LicenseToken.revoked_at.is_(None),
    ).update({LicenseToken.revoked_at: func.now()})
    session.add(LicenseToken(
        id=uuid4(),
        license_id=payload.license_id,
        token_type="license_activation",
        token_hash=digest(activation, settings.token_pepper),
        company_fingerprint=company_fingerprint,
        company_name_ciphertext=encrypt(payload.company_name, settings),
        license_payload_ciphertext=encrypt(canonical(raw_payload).decode(), settings),
        expires_at=payload.activation_expires_at,
    ))
    session.commit()
    return activation


def get_license_status(session: Session, settings: Settings) -> LicenseStatus:
    if settings.clock_state_path is not None:
        try:
            check_clock_state(settings.clock_state_path)
        except ValueError:
            return LicenseStatus(licensed=False, status="clock_rollback", renewal_required=True, server_date=datetime.now(timezone.utc), seconds_remaining=0, days_remaining=0)
    row = session.scalar(select(License).order_by(License.created_at.desc()).limit(1))
    now = datetime.now(timezone.utc)
    if row is None:
        return LicenseStatus(licensed=False, status="no_license", renewal_required=False, server_date=now, seconds_remaining=0, days_remaining=0)
    company = session.get(Company, row.company_id)
    if company is None:
        return LicenseStatus(licensed=False, status="invalid_license", renewal_required=True, server_date=now, seconds_remaining=0, days_remaining=0)
    try:
        signed_payload = verify_stored_license(row, settings)
        verify_company_binding(signed_payload, company, settings)
    except Exception:
        return LicenseStatus(licensed=False, status="invalid_license", renewal_required=True, server_date=now, seconds_remaining=0, days_remaining=0, admin_created=session.scalar(select(func.count(User.id)).where(User.company_id == row.company_id)) > 0)
    expiry = signed_payload.valid_until
    remaining = int((expiry - now).total_seconds())
    admin_created = session.scalar(select(func.count(User.id)).where(User.company_id == row.company_id)) > 0
    status = "expired" if remaining <= 0 else "expiring" if remaining <= 15 * 86400 else "active"
    return LicenseStatus(
        licensed=remaining > 0,
        status=status,
        renewal_required=remaining <= 0,
        server_date=now,
        seconds_remaining=max(remaining, 0),
        days_remaining=max(remaining // 86400, 0),
        company_name=decrypt(company.name_ciphertext, settings),
        created_at=row.created_at,
        valid_until=row.valid_until,
        edition=row.edition,
        max_users=row.max_users,
        max_branches=row.max_branches,
        modules=row.modules,
        admin_created=admin_created,
    )
