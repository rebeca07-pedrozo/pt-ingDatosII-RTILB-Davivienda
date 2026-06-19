# Primero - Librerias 
import pandas as pd, numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import display
sns.set_style('whitegrid')

# Segundo - Cargar 

# Entonces, para recargar el entorno:
# df = pd.read_csv(f'Punto_1_Base_Limpia_{NOMBRE}.csv', encoding='utf-8-sig',
#                  parse_dates=['FECHA_CORTE','FECHA_DESEMBOLSO','FECHA_VENCIMIENTO'])

def wavg(valor, peso):
    """Promedio ponderado robusto (ignora nulos y pesos no positivos)."""
    m = valor.notna() & peso.notna() & (peso > 0)
    return np.average(valor[m], weights=peso[m]) if m.sum() > 0 else np.nan

#Tercero - resumen por Modalidad (NIVEL2) y Producto (NIVEL3)
def resumen_grupo(g):
    s = g['SALDO_MO_CAPITALIZABLE']; tot = s.sum()
    return pd.Series({
        'SALDO_TOTAL':        tot,
        'TASA_PROM_POND':     wavg(g['TASA_COMPLETA'], s),
        'MIX_%_TF':           s[g['INDICADOR_INDEXACION']=='TF'].sum()/tot*100 if tot>0 else np.nan,
        'MIX_%_TV':           s[g['INDICADOR_INDEXACION']=='TV'].sum()/tot*100 if tot>0 else np.nan,
        'PLAZO_ORIG_POND_ANIOS': wavg(g['PLAZO_ORIGINACION'], s),
        'PLAZO_REM_POND_ANIOS':  wavg(g['PLAZO_REMANENTE'],  s),
    })

tabla_resumen = (df.groupby(['NIVEL2','NIVEL3'], observed=True)
                   .apply(resumen_grupo, include_groups=False)
                   .reset_index())

print(">>> 2.1 CARACTERIZACIÓN GENERAL DEL PORTAFOLIO")
display(tabla_resumen.round(4))
tabla_resumen.to_csv(f'Punto_2_Tabla_Resumen_{NOMBRE}.csv', index=False, encoding='utf-8-sig')

# Cuarto - Visualizaciones

orden_bandas = ['0 a 1 año','1 a 3 años','3 a 5 años','5 a 10 años','10 a 15 años','más de 15 años']

tabla_cruzada = (pd.pivot_table(df, index='BANDA_PLAZO_REMANENTE',
                                columns='INDICADOR_INDEXACION',
                                values='SALDO_MO_CAPITALIZABLE',
                                aggfunc='sum', observed=False, fill_value=0)
                   .reindex(orden_bandas).fillna(0))

print(">>> 2.2 CONCENTRACIÓN POR PLAZO REMANENTE (suma de saldo)")
display(tabla_cruzada.round(0))
tabla_cruzada.to_csv(f'Punto_2_Tabla_Cruzada_{NOMBRE}.csv', encoding='utf-8-sig')

ax = tabla_cruzada.plot(kind='bar', stacked=True, figsize=(10,6),
                        color={'TF':'#1f4e79','TV':'#c55a11'})
ax.set_title('Concentración de saldo por banda de plazo remanente e indexación')
ax.set_xlabel('Banda plazo remanente'); ax.set_ylabel('Saldo (COP)')
ax.legend(title='Indexación')
plt.xticks(rotation=30, ha='right'); plt.tight_layout()
plt.savefig(f'Punto_2_grafico_barras_apiladas_{NOMBRE}.png', dpi=150, bbox_inches='tight')
plt.show()

# Quinto - Distribución de plazos en HIPOTECARIO por departamento

hip = df[df['NIVEL2'] == 'HIPOTECARIO']
plt.figure(figsize=(10,6))
sns.boxplot(data=hip, x='DEPARTAMENTO', y='PLAZO_ORIGINACION',
            order=sorted(hip['DEPARTAMENTO'].unique()))
plt.title('Distribución del PLAZO_ORIGINACION (Hipotecario) por departamento')
plt.xticks(rotation=30, ha='right'); plt.tight_layout()
plt.savefig(f'Punto_2_grafico_plazos_hipotecario_{NOMBRE}.png', dpi=150, bbox_inches='tight')
plt.show()

li = df[df['NIVEL3'] == 'LIBRE_INVERSION']
plt.figure(figsize=(10,6))
sns.boxplot(data=li, x='DEPARTAMENTO', y='TASA_COMPLETA',
            order=sorted(li['DEPARTAMENTO'].unique()))
plt.title('Distribución de la TASA_COMPLETA (Libre Inversión) por departamento')
plt.xticks(rotation=30, ha='right'); plt.tight_layout()
plt.savefig(f'Punto_2_grafico_tasas_libreinversion_{NOMBRE}.png', dpi=150, bbox_inches='tight')
plt.show()

print(">>> Hipotecario - mediana PLAZO_ORIGINACION por depto")
display(hip.groupby('DEPARTAMENTO')['PLAZO_ORIGINACION'].median().round(2))
print(">>> Libre Inversión - mediana TASA_COMPLETA por depto")
display(li.groupby('DEPARTAMENTO')['TASA_COMPLETA'].median().round(4))
