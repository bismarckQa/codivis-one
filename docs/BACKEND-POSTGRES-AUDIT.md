# Auditoría backend PostgreSQL — productos, inventario y ventas

Fecha de verificación: 2026-10-27.

## Resultado

El backend dispone de modelos SQLAlchemy, esquemas Pydantic, routers y servicios funcionales para productos, inventario y ventas. Las migraciones `0007_integrity_constraints` y `0008_stock_operation_idempotency` añaden restricciones de base de datos para que los invariantes no dependan únicamente de la API.

La prueba de integración usa PostgreSQL real en la base aislada `codivis_one_test`; no usa SQLite y no toca la base comercial. La base `codivis_one_upgrade_test` se utilizó únicamente para comprobar la actualización desde `0006_sales` hasta `0007_integrity_constraints`.

## Cambios verificados

- Productos: `ProductUpdate`, normalización, límites Decimal, actualización parcial y conflicto 409 únicamente para `uq_products_company_code`.
- Inventario: unicidad de saldo por empresa/sucursal/producto, cantidades no negativas, movimientos positivos y bloqueo común por producto para escritores concurrentes.
- Entradas: endpoint `POST /api/inventory/adjustments/receipts`, incremento atómico de saldo, movimiento `in`, aislamiento por empresa e idempotencia mediante `operation_id`.
- Ventas: confirmación/cancelación con transición única, bloqueo de la venta y de los productos, descuento de stock y movimiento de salida en la misma transacción.
- Sucursales: creación serializada mediante bloqueo pesimista de la fila de empresa antes de contar el límite.
- PostgreSQL: checks para importes, descuentos, totales, cantidades y unicidades de líneas.
- Aislamiento: las operaciones comprueban `company_id`; una venta no puede usar productos de otra empresa.

## Pruebas ejecutadas

```text
.venv/bin/pytest -q
51 passed, 6 skipped

TEST_DATABASE_URL=.../codivis_one_test \
.venv/bin/pytest backend/tests/test_postgres_products_inventory_sales.py -q
11 passed

.venv/bin/python -m compileall -q backend/app backend/tests
OK
```

Las seis pruebas PostgreSQL cubren carrera de productos duplicados, confirmación idempotente, rollback por stock insuficiente, confirmación concurrente, restricciones/aislamiento y autenticación/autorización de API.

Migraciones comprobadas:

- Base vacía: `0001` → `0007`.
- Base existente: `0001` → `0006` y después `0007`.
- Versión final observada: `0008_stock_operation_idempotency`.
- Restricciones comprobadas en PostgreSQL: checks, unicidades de saldos/líneas y unicidad de operación de movimientos.

## Módulos todavía no funcionales

`purchases`, `finance` y `services` contienen actualmente únicamente los inicializadores de modelos/esquemas. No tienen modelos de negocio, migraciones, servicios ni routers, por lo que no deben presentarse como módulos terminados.

Para la primera versión operativa actual, productos + inventario + ventas son el núcleo mínimo. Compras requiere decidir proveedores, recepción y actualización de coste/stock; finanzas requiere decidir impuestos, cobros, caja y cierres; servicios requiere decidir catálogo, agenda, estados y si consume inventario. Esas decisiones son pendientes de producto, no se inventan en esta auditoría.

## Pendientes y límites

- No se aplicó `0007` a la base principal ni se reconstruyó el contenedor del backend: la petición prohíbe modificar datos comerciales o desplegar. Antes de actualizar una instalación real debe ejecutarse `alembic upgrade head` con copia de seguridad y plan de rollback.
- Las validaciones de esquemas de sucursales y el rechazo de sesiones de usuarios desactivados quedan fuera y pertenecen al otro frente.
- TPM/CNG, instalador Windows y pruebas E2E de escritorio no forman parte de esta ejecución Linux.
- PostgreSQL bloquea concurrencia de stock por productos ordenados; la política comercial sobre reservas, devoluciones y cancelación de ventas confirmadas todavía debe definirse.
