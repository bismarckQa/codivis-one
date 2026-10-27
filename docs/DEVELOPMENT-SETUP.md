# Entorno de desarrollo

## Requisitos

- Python 3.13.
- Docker Desktop con Compose.
- Git.

El proyecto usa Python 3.13 para mantener el mismo entorno en desarrollo y en
los contenedores. Las dependencias del backend se instalan dentro de `.venv`.

## Arranque rápido

Linux/macOS:

```bash
bash scripts/dev-up.sh
```

Windows PowerShell:

```powershell
.\scripts\dev-up.ps1
```

El primer arranque crea `.venv`, instala dependencias, genera `.env` con
secretos locales si faltan y levanta el emisor separado y el CRM.

```text
Emisor de licencias: http://localhost:8001/
CRM:                 http://localhost/
```

El emisor tiene su propia clave privada y su propia base SQLite. El CRM solo
recibe el JSON firmado y la clave pública.

## Preparar solo Python

```bash
bash scripts/setup-dev.sh
source .venv/bin/activate
python -m pytest
```

En Windows:

```powershell
.\scripts\setup-dev.ps1
.venv\Scripts\Activate.ps1
```

Instalación manual:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
```

El editor debe usar `.venv/bin/python` en Linux/macOS o
`.venv\Scripts\python.exe` en Windows.

## Tests y migraciones

Con `.venv` activado:

```bash
python -m pytest
```

El backend ejecuta automáticamente `alembic upgrade head` al iniciar. Las
migraciones están en `backend/alembic/versions/`; los cambios de estructura se
hacen con una nueva migración Alembic.

## Variables de entorno

`scripts/bootstrap_env.py` crea o completa `.env` sin eliminar variables
personalizadas existentes. Las principales variables son:

- `DATABASE_URL` y `POSTGRES_PASSWORD` para PostgreSQL.
- `APP_ENCRYPTION_KEY` para cifrado Fernet.
- `TOKEN_PEPPER` para hashes HMAC de tokens.
- `LICENSE_PUBLIC_KEY_FILE` para la clave pública del emisor.
- `ISSUER_ADMIN_TOKEN` para autorizar emisión y renovación desde el emisor.
  Se genera automáticamente en `.env` y nunca se incluye en una licencia.

`.env` contiene secretos locales y no debe subirse al repositorio.

## Prueba de licencias

1. Abrir `http://localhost/` y pulsar **Solicitar activación**.
2. Enviar el JSON descargado al emisor y cargarlo en `http://localhost:8001/`.
3. Completar los datos de la empresa; el equipo se vincula automáticamente con la solicitud.
4. Usar “Prueba: vencer en 1 hora” o establecer fecha y hora manualmente.
5. Descargar el JSON firmado e importarlo desde `http://localhost/`.
5. Crear el administrador e iniciar sesión.
6. Al vencer, el CRM debe bloquear el acceso.
7. Crear una renovación con la misma empresa e instalación.
8. Importarla y comprobar que usuarios y datos se conservan.

La renovación elimina la licencia anterior y sus tokens, pero conserva la
empresa, usuarios y datos operativos.

El JSON firmado incluye también una ventana de activación de 30 minutos desde
su emisión. Si se intenta importar después de esa ventana, el backend lo
rechaza aunque la fecha de vencimiento de la licencia todavía sea futura. Esta
ventana limita la reutilización del archivo; más adelante se complementará con
una vinculación criptográfica al equipo instalado.

La solicitud de activación contiene una clave pública generada automáticamente
por el CRM. La clave privada se guarda en un volumen local y nunca se incluye
en el archivo enviado al emisor. Al importar la licencia, el CRM verifica que
la clave privada local corresponde a la clave pública firmada.

El emisor rechaza emisiones y renovaciones si no recibe el token administrativo.
La limitación de peticiones es local al proceso; en producción debe combinarse
con red privada, firewall o un proxy autenticado.
