# Codivis One

CRM local de Codivis para una empresa por instalación.

## Levantar el proyecto en desarrollo

Requisito: Python 3.13 y Docker Desktop.

En Linux/macOS:

```bash
bash scripts/dev-up.sh
```

En Windows PowerShell:

```powershell
.\scripts\dev-up.ps1
```

El primer arranque crea `.venv`, instala las dependencias, genera `.env` con
secretos locales y levanta los dos entornos separados. El emisor queda en
`http://localhost:8001/` y el CRM en `http://localhost/`.

La guía completa está en [`docs/DEVELOPMENT-SETUP.md`](docs/DEVELOPMENT-SETUP.md).

Para preparar solo el entorno Python:

```bash
bash scripts/setup-dev.sh
source .venv/bin/activate
python -m pytest
```

Codivis One se diseña desde cero para instalarse en equipos Windows y permitir
que una empresa trabaje sin depender de una conexión permanente a Internet.
Cada instalación tendrá su propia base de datos, usuarios, permisos, módulos y
licencia.

## Objetivo

Entregar un CRM listo para usar mediante un instalador controlado por Codivis:

- instalación sencilla en un equipo Windows;
- arranque automático del sistema;
- acceso desde el navegador en `localhost`;
- funcionamiento offline después de la activación;
- licencias por empresa, instalación, usuarios y módulos;
- copias de seguridad fáciles de crear y restaurar;
- migración de equipo autorizada por Codivis.

## Ediciones previstas

- **Codivis One Base**: pequeños negocios y operación esencial.
- **Codivis One Business**: más usuarios, perfiles, permisos, reportes y módulos.
- **Codivis One Pro**: edición futura avanzada para organizaciones con mayor
  complejidad y automatización.

La licencia define qué edición, módulos, usuarios y fecha de vigencia tiene cada
instalación.

## Experiencia del cliente

1. Codivis prepara el instalador y la licencia.
2. El técnico instala el sistema en Windows.
3. El cliente importa el archivo de licencia desde la pantalla de activación.
4. El CRM verifica la firma, la empresa, la instalación y la vigencia.
5. El cliente crea sus usuarios y empieza a trabajar desde el navegador.

La pantalla inicial tendrá acceso al CRM y mostrará el estado de la licencia:
empresa autorizada, edición, módulos, usuarios permitidos, fecha de inicio y
fecha de vencimiento.

## Licencia offline

La licencia será un archivo firmado digitalmente por Codivis. Su carga no debe
requerir Internet.

El archivo contendrá, como mínimo:

- identificador de licencia;
- empresa autorizada;
- identificador de instalación;
- edición contratada;
- módulos habilitados;
- cantidad máxima de usuarios;
- fecha de inicio y vencimiento;
- versión máxima autorizada;
- identificador de la clave de firma.

Codivis conservará la clave privada de firma. El instalador solo incluirá la
clave pública necesaria para verificar el archivo. La firma impedirá modificar
fechas, módulos o límites sin invalidar la licencia.

El CRM generará un token de sesión local después de verificar la licencia. Ese
token será temporal y no sustituirá la verificación de licencia.

## Frontera del emisor de licencias

El emisor y su base de datos no forman parte de la instalación de Codivis One.
El emisor conserva la clave privada y genera el archivo firmado desde su propia
interfaz. El CRM instalado solo recibe el archivo, conserva el documento
firmado junto a la licencia y verifica la firma con la clave pública.

El CRM vuelve a verificar el documento firmado al consultar el estado de la
licencia, iniciar sesión y cargar la sesión. Una fila insertada directamente en
PostgreSQL sin una firma válida no se considera una licencia válida.

Solo puede existir una licencia para una instalación. Al importar una
renovación se invalidan los tokens de la licencia anterior y se elimina esa
licencia, pero se conservan la empresa, los usuarios y los datos operativos.

El emisor de desarrollo se ejecuta aparte desde `license-issuer/compose.yaml`.
La instalación del CRM recibe únicamente la ruta del archivo de clave pública
mediante `LICENSE_PUBLIC_KEY_FILE`.

Para una prueba local, se inicia primero el emisor desde `license-issuer/`, se
crea la licencia desde `http://localhost:8001/` y se configura
`LICENSE_PUBLIC_KEY_FILE=./license-issuer/data/public/codivis-one-ed25519.pub`
en el entorno del CRM. El CRM nunca recibe la clave privada ni expone la
interfaz del emisor.

## Seguridad de la instalación

- Usuario estándar de Windows para el trabajo diario.
- Cuenta administrativa separada para instalación y mantenimiento.
- Identidad de instalación protegida con mecanismos del sistema operativo.
- Vinculación a la máquina sin depender únicamente de la dirección MAC.
- Backend y servicios fuera del alcance del usuario estándar.
- Secretos fuera del frontend y fuera del repositorio.
- Actualizaciones firmadas y aplicables solo a licencias vigentes.
- Registro local de activaciones, restauraciones y cambios de equipo.

La protección técnica dificulta copias casuales y reventas. La licencia de uso,
el contrato y el soporte de Codivis son también parte de la protección del
producto.

## Requisitos iniciales de Windows

La primera versión se orientará a:

- Windows 10/11 de 64 bits compatible con WSL2;
- procesador de 4 núcleos recomendado;
- 8 GB de RAM mínimo, 16 GB recomendado;
- 30 GB libres para la instalación y los datos;
- virtualización habilitada en BIOS;
- permisos administrativos solo durante la instalación;
- navegador moderno para utilizar el CRM.

La instalación verificará estos requisitos antes de modificar el equipo y
mostrará un diagnóstico comprensible si falta alguno.

## Componentes técnicos iniciales

- Backend de la aplicación.
- Frontend web compilado.
- PostgreSQL local.
- Servicio de licencia local.
- Servicio de arranque y salud de la instalación.
- Herramienta de respaldo y restauración.
- Instalador y desinstalador controlados.

Docker/WSL2 se evaluará como mecanismo de empaquetado. El cliente no debería
necesitar abrir una terminal ni administrar contenedores para usar el CRM.

## Copias de seguridad

Desde el CRM se podrá crear un archivo de respaldo cifrado con:

- base de datos;
- configuración de la empresa;
- usuarios y permisos;
- datos operativos.

El respaldo no contendrá claves privadas de Codivis. La restauración pedirá la
contraseña del respaldo y una licencia válida para la nueva instalación.

## Migración de equipo

Cuando el cliente cambie de PC:

1. crea un respaldo;
2. solicita la migración a Codivis;
3. Codivis revoca la instalación anterior;
4. se genera una licencia para el nuevo equipo;
5. se restaura el respaldo y se verifica la nueva instalación.

## Primera fase de desarrollo

1. Definir arquitectura y requisitos de Windows.
2. Crear backend, frontend y base de datos mínimos.
3. Crear pantalla de login y estado de licencia.
4. Implementar firma y verificación de licencias.
5. Implementar importación offline.
6. Crear usuarios, roles y límites por edición.
7. Crear backup/restauración.
8. Crear instalador de prueba para Windows.
9. Probar instalación limpia, activación, expiración y migración.

Este proyecto es independiente y no debe compartir código, bases de datos,
contenedores ni configuraciones con otros productos.

# codivis-one
