import json
from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import get_db, settings
from app.core.security import activation_key_matches, activation_request as build_activation_request, load_json_no_duplicates
from app.models import License
from sqlalchemy import select
from app.schemas.license import LicenseStatus
from app.services.license_service import get_license_status, import_license, validate_signed_license


router = APIRouter(prefix="/api/license", tags=["license"])


@router.post("/activation-request")
def activation_request(session: Session = Depends(get_db)) -> dict:
    existing = session.scalar(select(License).order_by(License.created_at.desc()).limit(1))
    initial_installation_id = None
    if existing and existing.signed_payload and activation_key_matches(existing.signed_payload.get("device_public_key", ""), settings.activation_private_key_path):
        initial_installation_id = existing.installation_id
    return build_activation_request(settings.activation_private_key_path, initial_installation_id)


@router.post("/import")
async def import_license_file(response: Response, file: UploadFile = File(...), session: Session = Depends(get_db)) -> dict:
    try:
        document = load_json_no_duplicates((await file.read()).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        from fastapi import HTTPException

        raise HTTPException(400, "El archivo de licencia no es un JSON válido") from exc
    payload, raw_payload, signature = validate_signed_license(document, settings)
    activation = import_license(session, payload, raw_payload, signature, settings)
    response.set_cookie("codivis_one_activation", activation, httponly=True, samesite="lax", max_age=900)
    return {"activation_token": activation, "company_name": payload.company_name, "max_users": payload.max_users, "max_branches": payload.max_branches, "created_at": payload.created_at, "valid_until": payload.valid_until}


@router.get("/status", response_model=LicenseStatus)
def license_status(session: Session = Depends(get_db)) -> LicenseStatus:
    return get_license_status(session, settings)
