# Auditoría de seguridad de licencias

Fecha: 2026-10-27  
Producto verificado: Codivis One, CRM local para una empresa por instalación.

## Conclusión

El diseño criptográfico base es correcto para licencias offline: el emisor
firma con Ed25519 y el CRM verifica con una clave pública. No proporciona
protección absoluta contra el administrador del Windows, snapshots o la
modificación del ejecutable. El emisor no debe considerarse listo para
Internet público hasta añadir gestión de operadores, TLS/mTLS y custodia
operativa de la clave privada.

## Evidencias confirmadas

| Área | Estado encontrado | Evidencia |
|---|---|---|
| Producto | Codivis One; instalación única, no multi-tenant | `README.md`, `backend/app/main.py` |
| Firma | Ed25519, canonicalización JSON ordenada y verificación en importación y login | [`security.py`](../backend/app/core/security.py), [`license_service.py`](../backend/app/services/license_service.py) |
| Permisos | Edición, módulos, límites y fechas están dentro del payload firmado | [`license.py`](../backend/app/modules/core/schemas/license.py) |
| Manipulación de PostgreSQL | Cambiar una fila sin cambiar el documento firmado invalida la licencia | [`license_service.py`](../backend/app/services/license_service.py) |
| Identidad anterior | `installation_id` se generaba con `uuid4()` en cada solicitud | historial de [`license.py`](../backend/app/routers/license.py) |
| Identidad actual | Se conserva en `codivis-one-device.json`; la clave privada permanece en el volumen local | [`security.py`](../backend/app/core/security.py) |
| Emisor anterior | Emisión y renovación no exigían autenticación | historial de [`license-issuer/app/main.py`](../license-issuer/app/main.py) |
| Emisor actual | Exige `ISSUER_ADMIN_TOKEN`, limita peticiones y registra auditoría | [`license-issuer/app/main.py`](../license-issuer/app/main.py) |
| Repetición | La solicitud v2 lleva firma de posesión y `request_id`; el emisor impide reutilizarlo | [`license-issuer/app/main.py`](../license-issuer/app/main.py) |
| Ventanas | La importación tiene 30 minutos; la vigencia comercial es independiente | CRM y emisor |
| Reloj | Se detecta retroceso superior a cinco minutos con estado local | [`security.py`](../backend/app/core/security.py) |

## Cambios implementados

- Solicitudes de activación v2 con `schema_version`, `installation_id` estable,
  firma de posesión, fecha y `request_id`.
- Compatibilidad de lectura con licencias antiguas sin `product`; las nuevas
  licencias incluyen `product=codivis-one` y `schema_version=1`.
- Rechazo de producto incorrecto, JSON no objeto y claves JSON duplicadas.
- Rechazo de importación de archivos inválidos sin tocar la licencia existente.
- Token administrativo obligatorio para emitir y renovar.
- Límite de diez operaciones por IP y minuto en el emisor.
- Registro de actor, acción, licencia, solicitud y fecha en `issuer_audit_log`.
- Índice único para evitar emitir dos veces la misma solicitud de activación.
- Huella SHA-256 opcional y configurada localmente para fijar la clave pública
  del emisor (`LICENSE_PUBLIC_KEY_SHA256`).
- Detección de retroceso del reloj y bloqueo de login/validación mientras persista.
- El arranque genera `ISSUER_ADMIN_TOKEN` en `.env` y pasa explícitamente el
  `.env` raíz al Compose del emisor.

## Limitaciones residuales

1. La clave privada del emisor está fuera de la imagen y del repositorio, pero
   sigue siendo un archivo sin cifrar en el almacenamiento del host del emisor.
   En producción debe tener ACL exclusiva, copia de seguridad cifrada,
   procedimiento de recuperación y preferiblemente HSM/Key Vault.
2. `ISSUER_ADMIN_TOKEN` es un único operador administrativo. Falta RBAC por
   operador, rotación y revocación individual.
3. La limitación de peticiones vive en memoria del proceso. Un despliegue con
   varios workers necesita un almacén compartido o un proxy/WAF.
4. No se ha implementado TPM/CNG porque este entorno es Linux. La clave local
   sigue siendo copiable por un administrador; el vínculo dificulta copias
   casuales, no un atacante con control del equipo.
5. El estado del reloj también puede restaurarse con una snapshot o editarse
   con privilegios. Es detección de manipulación casual, no una fuente de hora
   confiable offline.
6. La revocación inmediata no existe offline. Requiere conexión, una nueva
   licencia o una lista de revocación firmada importada posteriormente.
7. La migración no puede apagar instantáneamente un equipo antiguo que nunca
   vuelva a conectarse.
8. El emisor solo está publicado en `127.0.0.1:8001` en desarrollo. Si se
   requiere acceso remoto, debe ir detrás de VPN/mTLS/TLS y firewall; no se
   debe publicar directamente el puerto.
9. La rotación de claves requiere cambiar la clave pública fijada y el código
   confiable del CRM. No se acepta que un JSON introduzca una clave nueva.

## Procedimiento operativo

1. El cliente genera una solicitud v2 desde el CRM.
2. Codivis la traslada al entorno separado del emisor.
3. El operador introduce el token administrativo y los datos comerciales.
4. El emisor valida la firma de posesión, la fecha, el producto y la solicitud
   no utilizada; genera el JSON Ed25519 y registra la operación.
5. El cliente importa el JSON offline.
6. El CRM verifica clave fijada, firma, producto, instalación, fechas y reloj.
7. Una renovación reemplaza la licencia anterior, revoca tokens y conserva la
   empresa y sus datos.

## Pendiente antes de producción

- Integrar TPM/CNG en el instalador Windows y definir el flujo de equipos sin
  TPM, reinstalación y migración autorizada.
- Sustituir el token único por operadores con roles, sesiones seguras, CSRF
  explícito si se adopta autenticación por cookie, rotación y auditoría.
- Firmar instalador y actualizaciones; verificar autenticidad antes de aplicar.
- Ejecutar pruebas en Windows 10/11 con TPM, clonación de VM, restauración de
  snapshot, cambio de hora y reinstalación.
- Definir política comercial de gracia, revocación y recuperación antes de
  prometer comportamiento al cliente.

## Verificación ejecutada

```text
27 passed
python3 -m py_compile license-issuer/app/main.py
Solicitud HTTP real: codivis-one-activation-request-v2, schema 2, firma presente
Dos solicitudes consecutivas: mismo installation_id
Backend y emisor arrancan sin errores
```

No se han declarado verificadas pruebas de TPM/CNG ni del instalador Windows.
