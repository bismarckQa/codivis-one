import base64
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

PRIVATE = Path(os.getenv("LICENSE_PRIVATE_DIR", "/data/private"))
PUBLIC = Path(os.getenv("LICENSE_PUBLIC_DIR", "/data/public"))
PRIVATE_KEY = PRIVATE / "codivis-one-ed25519.key"
PUBLIC_KEY = PUBLIC / "codivis-one-ed25519.pub"
ISSUER_DB = Path(os.getenv("ISSUER_DB_PATH", "/data/issuer.db"))

app = FastAPI(title="Codivis One License Issuer")
SUPPORTED_EDITIONS = {"base", "business", "pro"}
SUPPORTED_MODULES = {"dashboard"}
ACTIVATION_WINDOW_MINUTES = 30
ISSUER_TOKEN = os.getenv("ISSUER_ADMIN_TOKEN")
_ISSUE_ATTEMPTS: dict[str, list[float]] = {}


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def load_json_no_duplicates(value: str) -> dict:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = item
        return result

    parsed = json.loads(value, object_pairs_hook=reject_duplicates)
    if not isinstance(parsed, dict):
        raise ValueError("JSON document must be an object")
    return parsed


def validate_issue_input(company_name: str, max_users: int, max_branches: int, edition: str, modules: str, valid_until: str, installation_id: str) -> tuple[str, str, list[str], datetime, str]:
    company_name = company_name.strip()
    installation_id = installation_id.strip()
    edition = edition.strip().lower()
    module_values = list(dict.fromkeys(m.strip().lower() for m in modules.split(",") if m.strip()))
    if not 1 <= len(company_name) <= 255 or not 1 <= len(installation_id) <= 255:
        raise ValueError("company and installation are required and must be <= 255 characters")
    if edition not in SUPPORTED_EDITIONS:
        raise ValueError("unknown edition")
    if not 1 <= max_users <= 10000 or not 1 <= max_branches <= 1000:
        raise ValueError("license limits are outside the allowed range")
    if not module_values or any(module not in SUPPORTED_MODULES for module in module_values):
        raise ValueError("unknown module")
    try:
        valid_until_dt = datetime.fromisoformat(valid_until)
    except ValueError as exc:
        raise ValueError("invalid expiration timestamp") from exc
    if valid_until_dt.tzinfo is None:
        valid_until_dt = valid_until_dt.replace(tzinfo=timezone.utc)
    else:
        valid_until_dt = valid_until_dt.astimezone(timezone.utc)
    if valid_until_dt <= datetime.now(timezone.utc):
        raise ValueError("expiration must be in the future")
    return company_name, edition, module_values, valid_until_dt, installation_id


def validate_activation_request(document: dict) -> tuple[str, str, str]:
    if document.get("request_type") != "codivis-one-activation-request-v2" or document.get("schema_version") != 2:
        raise ValueError("archivo de solicitud de activación inválido")
    try:
        request_id = UUID(document["request_id"])
        installation_id = str(UUID(document["installation_id"]))
        public_key = base64.b64decode(document["device_public_key"], validate=True)
        request_signature = base64.b64decode(document["request_signature"], validate=True)
        created_at = datetime.fromisoformat(document["created_at"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("archivo de solicitud de activación inválido")
    if created_at.tzinfo is None:
        raise ValueError("la solicitud debe incluir zona horaria")
    age = datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)
    if age < timedelta(minutes=-5) or age > timedelta(minutes=ACTIVATION_WINDOW_MINUTES):
        raise ValueError("la solicitud de activación ha caducado")
    if len(public_key) != 32 or len(request_signature) != 64 or not request_id or not installation_id:
        raise ValueError("archivo de solicitud de activación inválido")
    signed_fields = {key: value for key, value in document.items() if key != "request_signature"}
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(request_signature, canonical(signed_fields))
    except Exception as exc:
        raise ValueError("prueba de posesión de la instalación inválida") from exc
    return installation_id, document["device_public_key"], str(request_id)


def validate_operator_token(token: str | None) -> str:
    if not ISSUER_TOKEN:
        raise HTTPException(503, "El emisor no está configurado con un token administrativo")
    if not token or not hmac.compare_digest(token, ISSUER_TOKEN):
        raise HTTPException(401, "Autenticación del emisor requerida")
    return "issuer-admin"


def check_issue_rate_limit(request: Request) -> None:
    now = time.monotonic()
    address = request.client.host if request.client else "unknown"
    recent = [stamp for stamp in _ISSUE_ATTEMPTS.get(address, []) if now - stamp < 60]
    if len(recent) >= 10:
        raise HTTPException(429, "Demasiadas operaciones de emisión; inténtalo más tarde")
    recent.append(now)
    _ISSUE_ATTEMPTS[address] = recent


def audit_action(action: str, actor: str, license_id: str, request_id: str | None = None) -> None:
    with sqlite3.connect(ISSUER_DB) as connection:
        connection.execute("INSERT INTO issuer_audit_log (actor, action, license_id, request_id, created_at) VALUES (?, ?, ?, ?, ?)", (actor, action, license_id, request_id, datetime.now(timezone.utc).isoformat()))
        connection.commit()


def ensure_keys() -> Ed25519PrivateKey:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    if not PRIVATE_KEY.exists():
        key = Ed25519PrivateKey.generate()
        PRIVATE_KEY.write_bytes(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        PUBLIC_KEY.write_bytes(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return Ed25519PrivateKey.from_private_bytes(PRIVATE_KEY.read_bytes())


def ensure_database() -> None:
    ISSUER_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ISSUER_DB) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS issued_licenses (
                license_id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                edition TEXT NOT NULL,
                modules TEXT NOT NULL,
                max_users INTEGER NOT NULL,
                max_branches INTEGER NOT NULL,
                valid_from TEXT NOT NULL,
                device_public_key TEXT,
                activation_expires_at TEXT,
                valid_until TEXT NOT NULL,
                signature TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                request_id TEXT
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(issued_licenses)")}
        if "activation_expires_at" not in columns:
            connection.execute("ALTER TABLE issued_licenses ADD COLUMN activation_expires_at TEXT")
        if "device_public_key" not in columns:
            connection.execute("ALTER TABLE issued_licenses ADD COLUMN device_public_key TEXT")
        if "request_id" not in columns:
            connection.execute("ALTER TABLE issued_licenses ADD COLUMN request_id TEXT")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_issued_license_request_id ON issued_licenses(request_id) WHERE request_id IS NOT NULL")
        connection.execute("CREATE TABLE IF NOT EXISTS issuer_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL, license_id TEXT NOT NULL, request_id TEXT, created_at TEXT NOT NULL)")
        connection.commit()


def signed_license(payload: dict) -> dict:
    private = ensure_keys()
    return {"payload": payload, "signature": base64.b64encode(private.sign(canonical(payload))).decode()}


def save_issued_license(signed: dict) -> None:
    payload = signed["payload"]
    with sqlite3.connect(ISSUER_DB) as connection:
        connection.execute(
            """INSERT INTO issued_licenses
            (license_id, company_name, installation_id, edition, modules, max_users,
            max_branches, valid_from, device_public_key, activation_expires_at, valid_until, signature, issued_at, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(license_id) DO UPDATE SET
              company_name=excluded.company_name, installation_id=excluded.installation_id,
              edition=excluded.edition, modules=excluded.modules, max_users=excluded.max_users,
              max_branches=excluded.max_branches, valid_from=excluded.valid_from,
              device_public_key=excluded.device_public_key,
              activation_expires_at=excluded.activation_expires_at,
              valid_until=excluded.valid_until, signature=excluded.signature,
              issued_at=excluded.issued_at, request_id=excluded.request_id""",
            (payload["license_id"], payload["company_name"], payload["installation_id"], payload["edition"], json.dumps(payload["modules"]), payload["max_users"], payload["max_branches"], payload["valid_from"], payload["device_public_key"], payload["activation_expires_at"], payload["valid_until"], signed["signature"], payload["created_at"], payload.get("activation_request_id")),
        )
        connection.commit()


def expiration(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid expiration timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    if parsed <= datetime.now(timezone.utc):
        raise ValueError("expiration must be in the future")
    return parsed


@app.on_event("startup")
def startup() -> None:
    ensure_keys()
    ensure_database()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "license-issuer"}


@app.get("/", response_class=HTMLResponse)
def form() -> str:
    return """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Codivis One · Crear licencia</title>
    <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css' rel='stylesheet'>
    <style>body{background:#f4f7fb}.brand{letter-spacing:.02em}.card{border:0;box-shadow:0 12px 32px rgba(15,23,42,.08)}.required:after{content:' *';color:#dc3545}</style></head>
    <body><nav class='navbar bg-dark navbar-dark'><div class='container'><span class='navbar-brand brand'>Codivis One</span><span class='navbar-text'>Emisor de licencias</span></div></nav>
    <main class='container py-5'><div class='row justify-content-center'><div class='col-xl-8'><div class='card'><div class='card-body p-4 p-md-5'>
    <div class='mb-4'><h1 class='h3 mb-2'>Crear licencia para una empresa</h1><p class='text-secondary mb-0'>Completa los datos que determinarán qué puede utilizar la instalación del cliente.</p></div>
    <form method='post' action='licenses' enctype='multipart/form-data'>
      <div class='mb-3'><label class='form-label required' for='company_name'>Empresa</label><input class='form-control' id='company_name' name='company_name' placeholder='Ej.: Minimarket La Plaza' required><div class='form-text'>Nombre que aparecerá en el CRM del cliente.</div></div>
      <div class='row g-3'>
        <div class='col-md-6'><label class='form-label required' for='max_users'>Máximo de usuarios</label><input class='form-control' id='max_users' name='max_users' type='number' min='1' value='5' required><div class='form-text'>Cantidad máxima de cuentas que podrá crear la empresa.</div></div>
        <div class='col-md-6'><label class='form-label required' for='max_branches'>Máximo de sucursales</label><input class='form-control' id='max_branches' name='max_branches' type='number' min='1' value='1' required><div class='form-text'>Límite de locales o puntos de venta.</div></div>
      </div>
      <div class='row g-3 mt-1'>
        <div class='col-md-6'><label class='form-label required' for='edition'>Edición</label><select class='form-select' id='edition' name='edition'><option value='base'>Base</option><option value='business'>Business</option><option value='pro'>Pro</option></select><div class='form-text'>Define el nivel comercial contratado.</div></div>
        <div class='col-md-6'><label class='form-label required' for='valid_until'>Válida hasta</label><input class='form-control' id='valid_until' name='valid_until' type='datetime-local' required><div class='form-text'>Fecha y hora exactas de vencimiento.</div><button class='btn btn-sm btn-outline-secondary mt-2' type='button' onclick='setOneHour()'>Prueba: vencer en 1 hora</button><button class='btn btn-sm btn-outline-secondary mt-2 ms-2' type='button' onclick='setTenMinutes()'>Prueba: vencer en 10 minutos</button></div>
      </div>
      <div class='mt-4'><label class='form-label'>Módulos incluidos</label><div class='border rounded p-3 bg-light'><div class='form-check'><input class='form-check-input' type='checkbox' checked disabled><label class='form-check-label'><strong>Dashboard</strong> <span class='text-secondary'>incluido en esta primera versión</span></label></div></div><input type='hidden' name='modules' value='dashboard'><div class='form-text'>Los módulos de ventas, inventario y reportes se añadirán cuando definamos el catálogo del CRM.</div></div>
      <div class='mt-4'><label class='form-label required' for='admin_token'>Token administrativo del emisor</label><input class='form-control' id='admin_token' name='admin_token' type='password' autocomplete='off' required></div>
      <div class='mt-4'><label class='form-label required' for='activation_request'>Solicitud de activación</label><input class='form-control' id='activation_request' name='activation_request' type='file' accept='.json,application/json' required><div class='form-text'>Carga el archivo generado desde “Solicitar activación” en el CRM. El equipo queda vinculado automáticamente.</div></div>
      <div class='alert alert-warning mt-4 mb-0'><strong>Activación:</strong> el archivo firmado solo puede importarse durante 30 minutos desde su emisión. Después caduca aunque la licencia comercial siga vigente.</div>
      <div class='d-flex justify-content-end mt-4'><button class='btn btn-primary px-4' type='submit'>Generar licencia firmada</button></div>
    </form><div class='text-end mt-3'><a href='/renewals'>Renovar una licencia existente</a></div></div></div></div></div></main><script>function setExpiration(minutes){const d=new Date(Date.now()+minutes*60*1000);const p=n=>String(n).padStart(2,'0');document.getElementById('valid_until').value=d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+'T'+p(d.getHours())+':'+p(d.getMinutes())}function setOneHour(){setExpiration(60)}function setTenMinutes(){setExpiration(10)}</script></body></html>"""


@app.post("/licenses")
async def create_license(
    request: Request,
    company_name: str = Form(...), max_users: int = Form(...), max_branches: int = Form(...),
    edition: str = Form(...), modules: str = Form("crm"), valid_until: str = Form(...),
    admin_token: str = Form(...), activation_request: UploadFile = File(...),
) -> JSONResponse:
    check_issue_rate_limit(request)
    actor = validate_operator_token(admin_token)
    try:
        request_document = load_json_no_duplicates((await activation_request.read()).decode("utf-8"))
        installation_id, device_public_key, request_id = validate_activation_request(request_document)
        company_name, edition, module_values, valid_until_dt, installation_id = validate_issue_input(company_name, max_users, max_branches, edition, modules, valid_until, installation_id)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    created_at = datetime.now(timezone.utc)
    activation_expires_at = created_at + timedelta(minutes=ACTIVATION_WINDOW_MINUTES)
    payload = {
        "product": "codivis-one", "schema_version": 1, "activation_request_id": request_id,
        "license_id": str(uuid4()), "company_name": company_name, "edition": edition,
        "modules": module_values, "max_users": max_users,
        "max_branches": max_branches, "created_at": created_at.isoformat(), "activation_expires_at": activation_expires_at.isoformat(),
        "valid_from": created_at.isoformat(), "valid_until": valid_until_dt.isoformat(),
        "installation_id": installation_id, "device_public_key": device_public_key, "key_id": "codivis-one-ed25519-1",
    }
    signed = signed_license(payload)
    try:
        save_issued_license(signed)
        audit_action("issue", actor, payload["license_id"], request_id)
    except sqlite3.IntegrityError as exc:
        return JSONResponse({"error": "la solicitud de activación ya fue utilizada"}, status_code=409)
    return JSONResponse(signed, headers={"Content-Disposition": "attachment; filename=codivis-one-license.json"})


@app.get("/renewals", response_class=HTMLResponse)
def renewals_form() -> str:
    with sqlite3.connect(ISSUER_DB) as connection:
        records = connection.execute("SELECT license_id, company_name, installation_id, edition, valid_until FROM issued_licenses WHERE device_public_key IS NOT NULL ORDER BY issued_at DESC").fetchall()
    options = "".join(f"<option value='{license_id}'>{company} · {edition} · vence {valid_until} · {installation}</option>" for license_id, company, installation, edition, valid_until in records)
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Renovar licencia · Codivis One</title><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css' rel='stylesheet'></head><body class='bg-light'><main class='container py-5'><div class='card mx-auto' style='max-width:760px'><div class='card-body p-4'><h1 class='h3'>Renovar licencia</h1><p class='text-secondary'>Selecciona una licencia emitida. La renovación conserva empresa, instalación, edición, módulos y límites.</p><form method='post' action='renewals'><label class='form-label' for='admin_token'>Token administrativo del emisor</label><input class='form-control mb-3' id='admin_token' name='admin_token' type='password' autocomplete='off' required><label class='form-label' for='previous_license_id'>Licencia de la empresa</label><select class='form-select mb-3' id='previous_license_id' name='previous_license_id' required>{options}</select><label class='form-label' for='valid_until'>Nueva fecha y hora de vencimiento</label><input class='form-control mb-3' id='valid_until' name='valid_until' type='datetime-local' required><button class='btn btn-primary' type='submit'>Generar renovación firmada</button> <a class='btn btn-outline-secondary' href='/'>Volver</a></form></div></div></main></body></html>"""


@app.post("/renewals")
def renew_license(request: Request, previous_license_id: str = Form(...), valid_until: str = Form(...), admin_token: str = Form(...)) -> JSONResponse:
    check_issue_rate_limit(request)
    actor = validate_operator_token(admin_token)
    try:
        expiration_dt = expiration(valid_until)
        with sqlite3.connect(ISSUER_DB) as connection:
            record = connection.execute("SELECT company_name, installation_id, edition, modules, max_users, max_branches, device_public_key FROM issued_licenses WHERE license_id = ?", (previous_license_id,)).fetchone()
        if record is None:
            return JSONResponse({"error": "license to renew was not found"}, status_code=404)
        if not record[6]:
            return JSONResponse({"error": "la licencia anterior necesita una nueva solicitud de activación"}, status_code=422)
        created_at = datetime.now(timezone.utc)
        payload = {
            "product": "codivis-one", "schema_version": 1,
            "license_id": str(uuid4()), "company_name": record[0], "edition": record[2],
            "modules": json.loads(record[3]), "max_users": record[4], "max_branches": record[5],
            "created_at": created_at.isoformat(), "activation_expires_at": (created_at + timedelta(minutes=ACTIVATION_WINDOW_MINUTES)).isoformat(), "valid_from": created_at.isoformat(),
            "valid_until": expiration_dt.isoformat(), "installation_id": record[1], "device_public_key": record[6], "key_id": "codivis-one-ed25519-1",
        }
        signed = signed_license(payload)
        save_issued_license(signed)
        audit_action("renew", actor, payload["license_id"])
        return JSONResponse(signed, headers={"Content-Disposition": "attachment; filename=codivis-one-renewal.json"})
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
