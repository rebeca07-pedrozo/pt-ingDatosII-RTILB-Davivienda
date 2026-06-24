# Explicación detallada del código — Prueba Técnica RTILB

Este documento explica la **anatomía de cada función** del pipeline: su firma (cómo se "construye"), qué hace cada parámetro, y la mecánica interna línea por línea. La idea es que puedas defender cualquier decisión del código.

---

## 0. Conceptos base que se repiten en todo el código

Antes de las funciones, conviene tener claros cinco conceptos, porque aparecen una y otra vez.

**Firma o "constructor" de una función.** En Python una función se declara con `def`:

```python
def nombre_funcion(parametro1, parametro2, parametro3=valor_por_defecto):
    # cuerpo
    return resultado
```

- `nombre_funcion`: cómo se llama.
- `parametro1, parametro2`: **parámetros obligatorios** (hay que pasarlos sí o sí).
- `parametro3=valor_por_defecto`: **parámetro opcional**; si no lo pasas, usa el valor por defecto.
- `return`: lo que la función devuelve a quien la llamó.

**Serie (`pd.Series`).** Una columna de un DataFrame. Casi todas las funciones reciben y devuelven Series.

**Máscara booleana (boolean mask).** Una Serie de `True`/`False` del mismo largo que los datos. Sirve para **seleccionar filas** sin escribir bucles. Ejemplo: `df['TASA_COMPLETA'] > 0.2817` devuelve `True` en las filas que superan la usura. Luego `df[mask]` te da solo esas filas, y `df[~mask]` (el `~` es "no") te da las contrarias.

**Vectorización.** En pandas se opera sobre **toda la columna a la vez** en vez de fila por fila con un `for`. Es más rápido y más legible. Por eso el código casi no tiene bucles.

**`.astype(...)`.** Convierte el tipo de dato de una Serie (a texto, número, fecha, etc.).

---

## 1. `registrar_modificacion` — el motor del log de cambios

```python
def registrar_modificacion(nro_series, campo, antes_series, despues_series, regla):
    antes   = antes_series.astype('string')
    despues = despues_series.astype('string')
    mask = (antes != despues) & ~(antes.isna() & despues.isna())
    if mask.any():
        log_modificaciones.append(pd.DataFrame({
            'NRO_OPERACION': nro_series[mask].values, 'CAMPO': campo,
            'VALOR_ANTERIOR': antes[mask].values, 'VALOR_NUEVO': despues[mask].values,
            'REGLA': regla}))
```

**Firma.** Recibe cinco parámetros, todos obligatorios:

| Parámetro | Qué es | Ejemplo |
|---|---|---|
| `nro_series` | columna de identificadores (`NRO_OPERACION`) | `df['NRO_OPERACION']` |
| `campo` | nombre del campo que se modificó (texto) | `'TASA_COMPLETA'` |
| `antes_series` | la columna **antes** del cambio | valores crudos |
| `despues_series` | la columna **después** del cambio | valores estandarizados |
| `regla` | descripción de la regla aplicada (texto) | `'Conversión tasa a decimal'` |

**Mecánica línea por línea:**

1. `antes = antes_series.astype('string')` y `despues = ...`: convierte ambas a texto para poder compararlas de forma justa (un `12.74%` contra un `0.1274`). Se usa `'string'` (con comillas, el tipo *nullable* de pandas) y no `str`, porque maneja los nulos sin romperse.
2. `mask = (antes != despues) & ~(antes.isna() & despues.isna())`: construye la máscara de "filas que de verdad cambiaron".
   - `antes != despues`: marca donde el valor es distinto.
   - `~(antes.isna() & despues.isna())`: descarta el caso "era nulo y sigue nulo" (eso no es un cambio real). El `&` es "y", el `~` es "no".
3. `if mask.any()`: solo trabaja si **hay al menos un cambio** (`any()` devuelve `True` si algún elemento de la máscara es `True`). Evita guardar tablas vacías.
4. `log_modificaciones.append(pd.DataFrame({...}))`: arma un mini-DataFrame solo con las filas que cambiaron y lo **agrega a la lista global** `log_modificaciones`. Al final del pipeline se concatenan todos.
   - `nro_series[mask].values`: toma los identificadores de las filas que cambiaron. El `.values` extrae el arreglo "crudo" para que el nuevo DataFrame no arrastre el índice viejo.

**Por qué está así.** Es un patrón **acumulador**: en vez de escribir en disco en cada paso, se van apilando trozos en una lista y al final se unen de una sola vez. Es eficiente y mantiene la trazabilidad centralizada.

---

## 2. `registrar_depuracion` — el log de exclusiones

```python
def registrar_depuracion(df_invalido, regla, razon):
    if len(df_invalido):
        log_depuraciones.append(pd.DataFrame({
            'NRO_OPERACION': df_invalido['NRO_OPERACION'].values,
            'REGLA': regla, 'RAZON': razon}))
```

**Firma.** Tres parámetros: `df_invalido` (las filas que se van a excluir), `regla` (categoría) y `razon` (texto explícito del motivo).

**Mecánica.**
- `if len(df_invalido):`: en Python un largo de `0` equivale a `False`, así que esto significa "solo si hay filas inválidas". Evita registrar exclusiones vacías.
- Construye un DataFrame con el identificador de cada excluido + la regla + la razón, y lo apila en `log_depuraciones`.

**Diferencia clave con la función anterior.** Aquí no se guarda "valor anterior/nuevo" porque no se modifica un campo: **se elimina la fila completa**. Por eso el log solo necesita *quién* y *por qué*.

---

## 3. `estandarizar_fecha` — normalizar fechas a datetime

```python
def estandarizar_fecha(serie):
    return pd.to_datetime(serie.astype(str).str.strip(),
                          errors='coerce', format='mixed', dayfirst=False)
```

**Firma.** Un solo parámetro: la columna de fechas en texto.

**Mecánica.**
- `serie.astype(str).str.strip()`: pasa todo a texto y le quita espacios al inicio/final (con `.str.strip()`, que aplica el strip a cada celda).
- `pd.to_datetime(...)`: convierte ese texto a fecha real (`datetime`). Aquí están las tres decisiones importantes:
  - `errors='coerce'`: si una celda no se puede convertir, en vez de reventar el programa la deja como `NaT` (Not a Time, el "nulo" de las fechas). Así el pipeline no se cae.
  - **`format='mixed'`**: parsea **cada celda por separado**, detectando su formato individual. Sin esto, pandas infiere **un solo formato** para toda la columna y convierte a `NaT` lo que no encaje (fue el bug que tenías: `"23 October 2025"` se volvía nulo).
  - `dayfirst=False`: ante una fecha ambigua como `03/04/2025`, interpreta el primer número como mes (formato tipo EE.UU.), no como día.

**Por qué importa.** Las fechas mal parseadas no fallan los filtros (`NaT < x` siempre es `False`), así que se colarían a la base limpia. Esta función + la depuración de `NaT` cierran ese hueco.

---

## 4. `estandarizar_tasa` — de "12.74%" a 0.1274

```python
def estandarizar_tasa(serie):
    limpio = (serie.astype(str)
                    .str.replace('%', '', regex=False)
                    .str.replace(',', '.', regex=False)
                    .str.extract(r'(-?\d+\.?\d*)')[0])
    num = pd.to_numeric(limpio, errors='coerce')
    return np.round(np.where(num > 1, num / 100, num), 6)
```

**Mecánica encadenada (method chaining).** Cada `.str....` se aplica sobre el resultado del anterior:
- `.str.replace('%', '', regex=False)`: borra el símbolo de porcentaje. `regex=False` significa "trátalo como texto literal, no como expresión regular" (más rápido y seguro).
- `.str.replace(',', '.', ...)`: cambia coma decimal por punto (por si hay `12,74`).
- `.str.extract(r'(-?\d+\.?\d*)')[0]`: extrae **solo el número** con una expresión regular, descartando cualquier texto sobrante.
  - `-?` opcional signo negativo, `\d+` uno o más dígitos, `\.?` punto opcional, `\d*` cero o más decimales.
  - El `[0]` toma el primer (y único) grupo capturado.
- `pd.to_numeric(limpio, errors='coerce')`: convierte ese texto a número; lo que no sea número válido queda `NaN`.

**La regla de negocio del decimal:**
- `np.where(condicion, valor_si_verdad, valor_si_falso)`: es un "if vectorizado". Aquí: `np.where(num > 1, num / 100, num)`.
  - Si el número es mayor que 1 (viene como porcentaje, ej. `12.74`), lo divide entre 100 → `0.1274`.
  - Si ya es menor o igual a 1 (ya estaba en decimal, ej. `0.24`), lo deja igual.
- `np.round(..., 6)`: redondea a 6 decimales para evitar la "basura" de punto flotante (`0.12029999999`).

---

## 5. `estandarizar_categoria` — corregir typos (la más interesante)

```python
def estandarizar_categoria(serie, validos, correcciones=None, default=None):
    correcciones = correcciones or {}
    def fix(v):
        if pd.isna(v): return v
        s = str(v).strip().upper()
        if s in validos:       return s
        if s in correcciones:  return correcciones[s]
        m = difflib.get_close_matches(s, validos, n=1, cutoff=0.6)
        if m: return m[0]
        return default if default is not None else s
    return serie.map(fix)
```

**Firma.** Cuatro parámetros, dos obligatorios y dos opcionales:

| Parámetro | Obligatorio | Qué hace |
|---|---|---|
| `serie` | sí | la columna a limpiar |
| `validos` | sí | lista de valores correctos permitidos |
| `correcciones` | no (default `None`) | diccionario de typos conocidos → valor correcto |
| `default` | no (default `None`) | valor a usar si nada coincide |

**Mecánica.**
- `correcciones = correcciones or {}`: si no se pasó diccionario (`None`), usa uno vacío. Es un truco para que el default mutable no dé problemas (`None` es "falsy", así que `None or {}` devuelve `{}`).
- **`def fix(v)` es una función anidada (closure):** una función definida *dentro* de otra, que se va a aplicar a cada celda. Sigue una cascada de 4 intentos, en orden de prioridad:
  1. `if pd.isna(v): return v`: si es nulo, lo deja como está.
  2. `s = str(v).strip().upper()`: normaliza a mayúsculas sin espacios, para comparar parejo.
  3. `if s in validos: return s`: si ya es un valor correcto, no toca nada.
  4. `if s in correcciones: return correcciones[s]`: si es un typo **conocido** del diccionario, lo reemplaza por el correcto.
  5. `difflib.get_close_matches(s, validos, n=1, cutoff=0.6)`: **corrección difusa (fuzzy)**. Busca el valor válido más parecido al texto.
     - `n=1`: devuelve como máximo 1 candidato.
     - `cutoff=0.6`: solo acepta parecidos con similitud ≥ 60%. Así `VEICULO` encuentra `VEHICULO`, pero algo totalmente distinto no se fuerza.
  6. `return default if default is not None else s`: si nada funcionó, usa el `default` (ej. forzar `DAVIVIENDA`) o, si no hay default, deja el valor tal cual.
- `return serie.map(fix)`: **`.map()` aplica la función `fix` a cada celda** de la Serie y devuelve la columna corregida.

**Por qué este diseño.** Va de lo más seguro a lo más arriesgado: primero exacto, luego diccionario explícito (control total), luego fuzzy (cubre typos no previstos) y al final el default. Esa jerarquía evita correcciones equivocadas.

---

## 6. `estandarizar_numerico` — limpiar montos

```python
def estandarizar_numerico(serie):
    return pd.to_numeric(serie.astype(str).str.replace(r'[^\d\.\-]', '', regex=True),
                         errors='coerce')
```

**Mecánica.**
- `.str.replace(r'[^\d\.\-]', '', regex=True)`: con una expresión regular borra **todo lo que NO sea** dígito, punto o signo menos.
  - `[^...]` significa "cualquier cosa que no esté en este conjunto".
  - `\d` dígitos, `\.` punto, `\-` menos. Así se eliminan separadores de miles, espacios o símbolos de moneda.
- `pd.to_numeric(..., errors='coerce')`: convierte a número; lo no convertible queda `NaN`.

---

## 7. `aplicar_regla_negocio` — depurar y registrar en un solo paso

```python
def aplicar_regla_negocio(df, mask_invalida, regla, razon):
    registrar_depuracion(df[mask_invalida], regla, razon)
    return df[~mask_invalida].copy()
```

**Firma.** Recibe el DataFrame, una **máscara de filas inválidas**, y la regla/razón para el log.

**Mecánica.**
- `registrar_depuracion(df[mask_invalida], ...)`: primero **guarda en el log** las filas que se van a botar (`df[mask_invalida]` = las que cumplen la condición inválida).
- `return df[~mask_invalida].copy()`: devuelve el DataFrame **sin** esas filas (`~` invierte la máscara). El `.copy()` crea una copia independiente para evitar el típico warning de pandas (`SettingWithCopyWarning`) en pasos siguientes.

**Por qué es elegante.** Encapsula el patrón "loguea y luego elimina" en una sola línea reutilizable. Cada regla de negocio se vuelve:
```python
df = aplicar_regla_negocio(df, <condición inválida>, 'Categoría', 'Razón explícita')
```
Como se aplican en secuencia, cada registro queda etiquetado con la **primera** causa por la que salió.

---

## 8. `asignar_departamento` — enriquecer con el código DANE

```python
def asignar_departamento(nro_series, mapa=MAPA_DANE):
    return nro_series.astype(str).str[:2].map(mapa).fillna('NO_IDENTIFICADO')
```

**Mecánica encadenada.**
- `.str[:2]`: toma los **dos primeros caracteres** de cada `NRO_OPERACION` (el código DANE, ej. `76`).
- `.map(mapa)`: usa el diccionario `MAPA_DANE` (`{'76':'Valle del Cauca', ...}`) para traducir el código al nombre del departamento.
- `.fillna('NO_IDENTIFICADO')`: cualquier código que no esté en el diccionario queda etiquetado, en vez de nulo.

**Nota sobre `mapa=MAPA_DANE`.** El diccionario es parámetro con default: si mañana cambia la llave, la pasas sin tocar la función.

---

## 9. Bandas de plazo con `pd.cut`

```python
bins   = [0, 1, 3, 5, 10, 15, np.inf]
labels = ['0 a 1 año','1 a 3 años','3 a 5 años','5 a 10 años','10 a 15 años','más de 15 años']
df['BANDA_PLAZO_ORIGINACION'] = pd.cut(df['PLAZO_ORIGINACION'], bins=bins, labels=labels, right=False)
```

No es una función propia sino una de pandas, pero conviene saber explicarla:
- `bins`: los **bordes** de los intervalos. `np.inf` es "infinito" (el último tramo abierto).
- `labels`: la etiqueta de texto para cada intervalo (debe haber una menos que bordes: 6 etiquetas, 7 bordes).
- **`right=False`**: hace los intervalos **cerrados a la izquierda y abiertos a la derecha**, es decir `[0, 1)`, `[1, 3)`, etc. Justo como pidió la prueba ("el límite superior es excluyente").

---

## 10. `wavg` — promedio ponderado (Punto 2)

```python
def wavg(valor, peso):
    m = valor.notna() & peso.notna() & (peso > 0)
    return np.average(valor[m], weights=peso[m]) if m.sum() > 0 else np.nan
```

**Firma.** Dos columnas: el `valor` a promediar y el `peso` (que en esta prueba siempre es `SALDO_MO_CAPITALIZABLE`).

**Mecánica.**
- `m = valor.notna() & peso.notna() & (peso > 0)`: máscara de filas **usables** (valor no nulo, peso no nulo y peso positivo). Esto blinda contra divisiones por cero o nulos.
- `np.average(valor[m], weights=peso[m])`: calcula el promedio ponderado solo sobre esas filas. La fórmula interna es Σ(valor·peso) / Σ(peso).
- `... if m.sum() > 0 else np.nan`: si no hay ninguna fila usable, devuelve `NaN` en vez de romperse. `m.sum()` cuenta los `True` (en Python `True` vale 1).

**Por qué ponderar por saldo.** Un crédito de 200 millones debe pesar más en la tasa promedio que uno de 5 millones; el promedio simple los trataría igual y distorsionaría la lectura de riesgo.

---

## 11. `resumen_grupo` — métricas por grupo (Punto 2)

```python
def resumen_grupo(g):
    s = g['SALDO_MO_CAPITALIZABLE']; tot = s.sum()
    return pd.Series({
        'SALDO_TOTAL':           tot,
        'TASA_PROM_POND':        wavg(g['TASA_COMPLETA'], s),
        'MIX_%_TF':              s[g['INDICADOR_INDEXACION']=='TF'].sum()/tot*100 if tot>0 else np.nan,
        'MIX_%_TV':              s[g['INDICADOR_INDEXACION']=='TV'].sum()/tot*100 if tot>0 else np.nan,
        'PLAZO_ORIG_POND_ANIOS': wavg(g['PLAZO_ORIGINACION'], s),
        'PLAZO_REM_POND_ANIOS':  wavg(g['PLAZO_REMANENTE'],  s),
    })
```

**Cómo se usa.** Esta función recibe **un grupo** `g` (un sub-DataFrame) y devuelve una fila de métricas. Se la pasa a `groupby`:

```python
tabla = df.groupby(['NIVEL2','NIVEL3'], observed=True).apply(resumen_grupo, include_groups=False)
```

- `groupby(['NIVEL2','NIVEL3'])`: parte la base en grupos por modalidad y producto.
- `.apply(resumen_grupo, ...)`: corre la función en **cada grupo** y junta los resultados en una tabla.
- `observed=True`: con columnas categóricas, solo muestra combinaciones que **existen** (no todas las teóricas).
- `include_groups=False`: evita un warning de versiones nuevas de pandas; le dice que no reinyecte las columnas de agrupación dentro de la función.

**Mecánica interna.**
- `s = g['SALDO_MO_CAPITALIZABLE']; tot = s.sum()`: el saldo del grupo y su total (denominador para los mix).
- `s[g['INDICADOR_INDEXACION']=='TF'].sum() / tot * 100`: suma el saldo solo de las filas a Tasa Fija y lo divide por el total → porcentaje del grupo a TF. Igual para TV.
- Devuelve una `pd.Series`, que `apply` convierte en una fila de la tabla final.

---

## Resumen de patrones de diseño que usaste

| Patrón | Dónde | Por qué suma |
|---|---|---|
| Funciones modulares | todo el Punto 1 | reutilizable y fácil de auditar |
| Acumulador en lista + concat final | logs | eficiente y centraliza la trazabilidad |
| Máscaras booleanas (sin bucles) | reglas de negocio | vectorizado, legible, rápido |
| Cascada exacto→dicc→fuzzy→default | `estandarizar_categoria` | corrige sin equivocarse |
| Parámetros con default (`usura`, `mapa`) | varias | parametrizable a futuro |
| Guard clauses (`if mask.any()`, `if len(...)`) | logs | evita registros vacíos y errores |
| `errors='coerce'` | conversiones | el pipeline no se cae con datos sucios |

Cualquier pregunta del tipo "¿por qué hiciste X así?" cae en alguna de estas filas.
