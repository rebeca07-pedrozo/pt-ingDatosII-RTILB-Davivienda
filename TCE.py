#Primero - Librerias 
import pandas as pd
import numpy as np
import difflib
from IPython.display import display


#segundo - Carga de datos
from google.colab import files
uploaded = files.upload()                
NOMBRE_ARCHIVO = next(iter(uploaded))

#Tercero - Definicion de los parametros de negocio dinamicos y definicion de la trazabilidad de los cambios que se van a realizar en la base de datos
df_raw = pd.read_csv(NOMBRE_ARCHIVO, sep=None, engine='python', dtype=str)
df_raw.columns = [c.strip().upper() for c in df_raw.columns]
print("Filas cargadas:", df_raw.shape[0])
df_raw.head()

#Cuarto - Desarrollo de funciones de estandarizacion reusables y log de cambios
TASA_USURA           = 0.2817         
FECHA_CORTE_ESPERADA = '2026-05-31'

MAPA_DANE = {'05':'Antioquia', '11':'Bogotá D.C.', '76':'Valle del Cauca',
             '08':'Atlántico', '68':'Santander'}

log_modificaciones = []  
log_depuraciones   = []  

def registrar_modificacion(nro_series, campo, antes_series, despues_series, regla):
    """Log de las celdas que cambiaron de valor, se compara el anterior vs lo nuevo"""
    antes   = antes_series.astype('string')
    despues = despues_series.astype('string')
    mask = (antes != despues) & ~(antes.isna() & despues.isna())
    if mask.any():
        log_modificaciones.append(pd.DataFrame({
            'NRO_OPERACION': nro_series[mask].values, 'CAMPO': campo,
            'VALOR_ANTERIOR': antes[mask].values, 'VALOR_NUEVO': despues[mask].values,
            'REGLA': regla}))

def registrar_depuracion(df_invalido, regla, razon):
    """Logueamos los registros excluidos con la razon explicita"""
    if len(df_invalido):
        log_depuraciones.append(pd.DataFrame({
            'NRO_OPERACION': df_invalido['NRO_OPERACION'].values,
            'REGLA': regla, 'RAZON': razon}))
        

#Quinto - Aplicaciones de las reglas de los datos y log de cambios  
def estandarizar_fecha(serie):
    """format='mixed' parsea cada celda por separado (evita que '23 October 2025' se vuelva NaT)."""
    return pd.to_datetime(serie.astype(str).str.strip(),
                          errors='coerce', format='mixed', dayfirst=False)

def estandarizar_tasa(serie):
    """Quitamos el %, texto y se deja la tasa en decimal, como por ejemplo (12.74% -> 0.1274 ; 0.24 -> 0.24)."""
    limpio = (serie.astype(str)
                    .str.replace('%', '', regex=False)
                    .str.replace(',', '.', regex=False)
                    .str.extract(r'(-?\d+\.?\d*)')[0])
    num = pd.to_numeric(limpio, errors='coerce')
    return np.where(num > 1, num / 100, num)   

def estandarizar_categoria(serie, validos, correcciones=None, default=None):
    """Corregimos los typos que hay, ej: 1) match exacto, 2) diccionario, 3) fuzzy, 4) default."""
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

def estandarizar_numerico(serie):
    return pd.to_numeric(serie.astype(str).str.replace(r'[^\d\.\-]', '', regex=True),
                         errors='coerce')


#Sexto - Aplicacion de las funciones de estandarizacion y log de cambios, aplicacion de las reglas de negocio
df = df_raw.copy()

dups = df[df.duplicated(keep='first')]
registrar_depuracion(dups, 'DUPLICIDAD (Regla de Datos)', 'Registro duplicado exacto')
df = df.drop_duplicates(keep='first').reset_index(drop=True)

for col in ['FECHA_CORTE', 'FECHA_DESEMBOLSO', 'FECHA_VENCIMIENTO']:
    antes = df[col]; nueva = estandarizar_fecha(df[col])
    registrar_modificacion(df['NRO_OPERACION'], col, antes,
                           nueva.dt.strftime('%Y-%m-%d'), 'Estandarización fecha YYYY-MM-DD')
    df[col] = nueva

antes = df['TASA_COMPLETA']; df['TASA_COMPLETA'] = estandarizar_tasa(df['TASA_COMPLETA'])
registrar_modificacion(df['NRO_OPERACION'], 'TASA_COMPLETA', antes,
                       df['TASA_COMPLETA'].astype('string'), 'Conversión tasa a decimal')

antes = df['ENTIDAD']
df['ENTIDAD'] = estandarizar_categoria(df['ENTIDAD'], ['DAVIVIENDA'], default='DAVIVIENDA')
registrar_modificacion(df['NRO_OPERACION'], 'ENTIDAD', antes, df['ENTIDAD'], 'Estandarización entidad')

antes = df['NIVEL3']
df['NIVEL3'] = estandarizar_categoria(
    df['NIVEL3'], ['VIS','CORPORATIVO','LIBRE_INVERSION','VEHICULO','TARJETA_CREDITO'],
    correcciones={'VIS__MARCA':'VIS','LIBRE_INBERSION':'LIBRE_INVERSION','VEICULO':'VEHICULO'})
registrar_modificacion(df['NRO_OPERACION'], 'NIVEL3', antes, df['NIVEL3'], 'Corrección tipográfica NIVEL3')

antes = df['MONEDA_ORIGEN']
df['MONEDA_ORIGEN'] = estandarizar_categoria(
    df['MONEDA_ORIGEN'], ['COP'],
    correcciones={'MONEDA COLOMBIANA':'COP','PESOS':'COP','PESO COLOMBIANO':'COP'})
registrar_modificacion(df['NRO_OPERACION'], 'MONEDA_ORIGEN', antes, df['MONEDA_ORIGEN'], 'Estandarización moneda COP')

for col in ['NIVEL1','NIVEL2','SISTEMA_PAGO','FRECUENCIA_PAGO_CAPITAL','INDICADOR_INDEXACION']:
    antes = df[col]; df[col] = df[col].astype(str).str.strip().str.upper()
    registrar_modificacion(df['NRO_OPERACION'], col, antes, df[col], 'Normalización texto')

for col in ['MONTO_DESEMBOLSADO', 'SALDO_MO_CAPITALIZABLE']:
    antes = df[col]; df[col] = estandarizar_numerico(df[col])
    registrar_modificacion(df['NRO_OPERACION'], col, antes, df[col].astype('string'), 'Conversión a numérico')


#Septimo - Aplicacion de las reglas de negocio y log de cambios
 
mask_nat = df[['FECHA_CORTE','FECHA_DESEMBOLSO','FECHA_VENCIMIENTO']].isna().any(axis=1)
df = aplicar_regla_negocio(df, mask_nat, 'Consistencia fechas',
        'Fecha no parseable / inconsistente (NaT)')

def aplicar_regla_negocio(df, mask_invalida, regla, razon):
    registrar_depuracion(df[mask_invalida], regla, razon)
    return df[~mask_invalida].copy()

df = aplicar_regla_negocio(df, df['FECHA_VENCIMIENTO'] < df['FECHA_DESEMBOLSO'],
        'Consistencia fechas', 'FECHA_VENCIMIENTO < FECHA_DESEMBOLSO')
df = aplicar_regla_negocio(df, df['FECHA_VENCIMIENTO'] < df['FECHA_CORTE'],
        'Consistencia fechas', 'FECHA_VENCIMIENTO < FECHA_CORTE')
df = aplicar_regla_negocio(df, df['FECHA_DESEMBOLSO'] > df['FECHA_CORTE'],
        'Consistencia fechas', 'FECHA_DESEMBOLSO en el futuro (> FECHA_CORTE)')

mask_saldo = (df['SALDO_MO_CAPITALIZABLE'] > df['MONTO_DESEMBOLSADO']) | \
             ((df['SALDO_MO_CAPITALIZABLE'] == df['MONTO_DESEMBOLSADO']) &
              (df['FECHA_DESEMBOLSO'] != df['FECHA_CORTE']))
df = aplicar_regla_negocio(df, mask_saldo, 'Consistencia saldos',
        'SALDO > MONTO, o SALDO = MONTO con desembolso != corte')

df = aplicar_regla_negocio(df,
        (df['SISTEMA_PAGO']=='CUOTA_FIJA') & (df['INDICADOR_INDEXACION']=='TV'),
        'Amortización', 'CUOTA_FIJA no puede estar indexado a TV')
df = aplicar_regla_negocio(df,
        (df['SISTEMA_PAGO']=='CUOTA_FIJA') & ((df['TASA_COMPLETA']==0) | (df['TASA_COMPLETA'].isna())),
        'Amortización', 'CUOTA_FIJA con tasa 0 o nula')
df = aplicar_regla_negocio(df,
        (df['SISTEMA_PAGO']=='BULLET') & (df['FRECUENCIA_PAGO_CAPITAL']!='VENCIMIENTO'),
        'Amortización', 'BULLET debe pagar capital al VENCIMIENTO')

df = aplicar_regla_negocio(df, df['TASA_COMPLETA'] > TASA_USURA,
        'Usura', f'TASA_COMPLETA supera la usura ({TASA_USURA:.4f})')

#Octavo - Enriquecimiento con los nuevos campos
def asignar_departamento(nro_series, mapa=MAPA_DANE):
    return nro_series.astype(str).str[:2].map(mapa).fillna('NO_IDENTIFICADO')

df['DEPARTAMENTO'] = asignar_departamento(df['NRO_OPERACION'])

ANIO = 365.25
df['PLAZO_ORIGINACION'] = (df['FECHA_VENCIMIENTO'] - df['FECHA_DESEMBOLSO']).dt.days / ANIO
df['PLAZO_REMANENTE']   = (df['FECHA_VENCIMIENTO'] - df['FECHA_CORTE']).dt.days / ANIO

bins   = [0, 1, 3, 5, 10, 15, np.inf]
labels = ['0 a 1 año','1 a 3 años','3 a 5 años','5 a 10 años','10 a 15 años','más de 15 años']
df['BANDA_PLAZO_ORIGINACION'] = pd.cut(df['PLAZO_ORIGINACION'], bins=bins, labels=labels, right=False)
df['BANDA_PLAZO_REMANENTE']   = pd.cut(df['PLAZO_REMANENTE'],   bins=bins, labels=labels, right=False)


#Noveno - Consolidar logs, base limpia y exportar con tu nomenclatura

NOMBRE = 'Rebeca_Pedrozo' 

log_mod = pd.concat(log_modificaciones, ignore_index=True) if log_modificaciones \
          else pd.DataFrame(columns=['NRO_OPERACION','CAMPO','VALOR_ANTERIOR','VALOR_NUEVO','REGLA'])
log_dep = pd.concat(log_depuraciones, ignore_index=True) if log_depuraciones \
          else pd.DataFrame(columns=['NRO_OPERACION','REGLA','RAZON'])

df.to_csv(f'Punto_1_Base_Limpia_{NOMBRE}.csv', index=False, encoding='utf-8-sig')
log_mod.to_csv(f'Punto_1_Log_Modificaciones_{NOMBRE}.csv', index=False, encoding='utf-8-sig')
log_dep.to_csv(f'Punto_1_Log_Depuraciones_{NOMBRE}.csv', index=False, encoding='utf-8-sig')

print(f"Base limpia: {len(df)} | Modificaciones: {len(log_mod)} | Depuraciones: {len(log_dep)}\n")

print(">>> RESUMEN DE DEPURACIONES (Reglas de Negocio)")
display(log_dep['RAZON'].value_counts().rename_axis('RAZON').reset_index(name='REGISTROS'))

print(">>> LOG DE DEPURACIONES (detalle)")
display(log_dep)

print(">>> LOG DE MODIFICACIONES (muestra de 20)")
display(log_mod.head(20))

print(">>> BASE LIMPIA (muestra de 10)")
display(df.head(10))

