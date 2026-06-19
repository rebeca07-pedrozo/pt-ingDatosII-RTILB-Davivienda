-- ============================================================================
--  PUNTO 3 - RECONSTRUCCIÓN DE LA SÁBANA DE DATOS RTILB
--  Fotografía del cierre 2026-05-31, únicamente operaciones de Cartera.
--  Salida: 15 columnas en el orden del dataset (ID_PRODUCTO NO se proyecta).
-- ============================================================================

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

-- 1:1 con históricos. La PK compuesta (NRO_OPERACION + FECHA_CORTE) + el filtro
-- de fecha de abajo garantizan una sola fila por operación (la foto del cierre).
INNER JOIN TABLA_TASAS_SALDOS AS T
    ON M.NRO_OPERACION = T.NRO_OPERACION

-- Trae la jerarquía de producto (NIVEL1/2/3) y el esquema de pago.
INNER JOIN CATALOGO_PRODUCTOS AS C
    ON M.ID_PRODUCTO = C.ID_PRODUCTO

WHERE
    -- (1) Solo la fotografía del cierre solicitado.
    T.FECHA_CORTE = DATE '2026-05-31'

    -- ========================================================================
    -- (2) FILTRO DE CARTERA
    -- Regla del catálogo: los 2 primeros caracteres de ID_PRODUCTO indican la
    -- línea de negocio contable:
    --     '01' -> Cartera (Créditos)        <-- lo que queremos
    --     '02' -> CDTs (Captaciones a término)
    --     '03' -> Cuentas de Depósito y Ahorro
    -- Por eso filtramos únicamente los productos que empiezan por '01'.
    -- ========================================================================
    AND C.ID_PRODUCTO LIKE '01%'
    -- Alternativa explícita (estándar SQL):
    -- AND SUBSTRING(C.ID_PRODUCTO FROM 1 FOR 2) = '01'
    -- Alternativa BigQuery / Postgres:
    -- AND LEFT(C.ID_PRODUCTO, 2) = '01'

ORDER BY M.NRO_OPERACION;