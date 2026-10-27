from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db, settings
from app.schemas.auth import AuthResponse, BootstrapRequest, LoginRequest
from app.services.auth_service import authenticate, bootstrap_admin, get_me, logout


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/bootstrap", response_model=AuthResponse)
def bootstrap(data: BootstrapRequest, response: Response, session: Session = Depends(get_db), codivis_one_activation: str | None = Cookie(default=None)) -> AuthResponse:
    activation = data.activation_token or codivis_one_activation
    if not activation:
        raise HTTPException(401, "Token de activación inválido")
    bootstrap_admin(session, data, activation, settings)
    response.delete_cookie("codivis_one_activation")
    return AuthResponse(status="admin_created")


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, response: Response, session: Session = Depends(get_db)) -> AuthResponse:
    token = authenticate(session, data, settings)
    response.set_cookie("codivis_one_session", token, httponly=True, samesite="lax", secure=False, max_age=28800)
    return AuthResponse(status="authenticated")


@router.get("/me")
def me(codivis_one_session: str | None = Cookie(default=None), session: Session = Depends(get_db)) -> dict:
    if not codivis_one_session:
        raise HTTPException(401, "Sesión requerida")
    return get_me(session, codivis_one_session, settings)


@router.post("/logout", status_code=204)
def end_session(session: Session = Depends(get_db), codivis_one_session: str | None = Cookie(default=None)) -> Response:
    if codivis_one_session:
        logout(session, codivis_one_session, settings)
    response = Response(status_code=204)
    response.delete_cookie("codivis_one_session", path="/", httponly=True, samesite="lax")
    return response
