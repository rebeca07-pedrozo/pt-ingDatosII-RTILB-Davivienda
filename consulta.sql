# Punto 3 — Extracción de Datos (Ingeniería Inversa SQL)

## Objetivo
Reconstruir la sábana de datos plana (15 columnas) que sirve de insumo al cálculo
de métricas de riesgo, partiendo del modelo transaccional normalizado de 3 tablas,
extrayendo **únicamente** la fotografía del cierre **2026-05-31** y **solo Cartera**.

## Mapeo de columnas → tabla de origen

| # | Columna del dataset | Tabla origen | Nota |
|---|---|---|---|
| 1 | NRO_OPERACION | MAESTRO_OPERACIONES | PK |
| 2 | FECHA_CORTE | TABLA_TASAS_SALDOS | parte de la PK compuesta |
| 3 | ENTIDAD | MAESTRO_OPERACIONES | estático |
| 4 | NIVEL1 | CATALOGO_PRODUCTOS | vía ID_PRODUCTO (FK) |
| 5 | NIVEL2 | CATALOGO_PRODUCTOS | vía ID_PRODUCTO (FK) |
| 6 | NIVEL3 | CATALOGO_PRODUCTOS | vía ID_PRODUCTO (FK) |
| 7 | MONEDA_ORIGEN | MAESTRO_OPERACIONES | estático |
| 8 | SISTEMA_PAGO | CATALOGO_PRODUCTOS | vía ID_PRODUCTO (FK) |
| 9 | FRECUENCIA_PAGO_CAPITAL | CATALOGO_PRODUCTOS | vía ID_PRODUCTO (FK) |
| 10 | INDICADOR_INDEXACION | TABLA_TASAS_SALDOS | histórico del corte |
| 11 | TASA_COMPLETA | TABLA_TASAS_SALDOS | VARCHAR crudo (con %) |
| 12 | FECHA_DESEMBOLSO | MAESTRO_OPERACIONES | estático |
| 13 | FECHA_VENCIMIENTO | MAESTRO_OPERACIONES | estático |
| 14 | MONTO_DESEMBOLSADO | MAESTRO_OPERACIONES | estático |
| 15 | SALDO_MO_CAPITALIZABLE | TABLA_TASAS_SALDOS | histórico del corte |

> Son **15 columnas, sin `ID_PRODUCTO`**: este campo solo se usa como puente para el JOIN, no se proyecta en la salida.

## Lógica de la consulta

- **`MAESTRO_OPERACIONES`** es la tabla central (información estática de la operación).
- Se une con **`TABLA_TASAS_SALDOS`** por `NRO_OPERACION`. Como esta tabla tiene **PK compuesta (`NRO_OPERACION` + `FECHA_CORTE`)**, el filtro `FECHA_CORTE = '2026-05-31'` garantiza **una sola fila por operación** (la fotografía del cierre, sin duplicar por históricos).
- Se une con **`CATALOGO_PRODUCTOS`** por `ID_PRODUCTO` para traer la jerarquía de producto y el sistema de pago.
- Se usa **`INNER JOIN`** a propósito: solo interesan operaciones que tengan foto en el corte **y** que sean Cartera.
- El filtro de **Cartera** se aplica sobre los **dos primeros caracteres del `ID_PRODUCTO`** (`'01'`): `01`=Cartera, `02`=CDTs, `03`=Cuentas de Depósito/Ahorro.

## Consulta

```sql
SELECT
    M.NRO_OPERACION,
    T.FECHA_CORTE,
    M.ENTIDAD,
    C.NIVEL1,
    C.NIVEL2,
    C.NIVEL3,
    M.MONEDA_ORIGEN,
    C.SISTEMA_PAGO,
    C.FRECUENCIA_PAGO_CAPITAL,
    T.INDICADOR_INDEXACION,
    T.TASA_COMPLETA,
    M.FECHA_DESEMBOLSO,
    M.FECHA_VENCIMIENTO,
    M.MONTO_DESEMBOLSADO,
    T.SALDO_MO_CAPITALIZABLE
FROM MAESTRO_OPERACIONES AS M
INNER JOIN TABLA_TASAS_SALDOS AS T
    ON M.NRO_OPERACION = T.NRO_OPERACION
INNER JOIN CATALOGO_PRODUCTOS AS C
    ON M.ID_PRODUCTO = C.ID_PRODUCTO
WHERE T.FECHA_CORTE = DATE '2026-05-31'   -- (1) solo la fotografía del cierre
  AND C.ID_PRODUCTO LIKE '01%'            -- (2) solo Cartera (línea contable 01)
ORDER BY M.NRO_OPERACION;
```

## Consideraciones técnicas

- **`DATE '2026-05-31'`** es literal estándar y funciona igual en BigQuery. Si `FECHA_CORTE` está como timestamp: `CAST(T.FECHA_CORTE AS DATE) = DATE '2026-05-31'`.
- El filtro de cartera se puede hacer explícito por substring: `SUBSTRING(C.ID_PRODUCTO FROM 1 FOR 2) = '01'` (estándar) o `LEFT(C.ID_PRODUCTO, 2) = '01'`.
- **`TASA_COMPLETA` se proyecta tal cual (VARCHAR con `%`)**: su limpieza a decimal es trabajo del Punto 1, no de la extracción.