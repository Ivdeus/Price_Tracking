"""
Dashboard de precios - Multi-retailer (Refrigeración)
---------------------------------------------------------
Lee precios_multitienda.db. Agrupa por canonical_id (el "mismo producto"
detectado entre retailers) en vez de por SKU individual, para que la
gráfica de un producto muestre su histórico de precio sin importar en
cuántas tiendas se vende ni cómo cada una lo nombra.

Requisitos:
    pip install streamlit pandas plotly

Uso:
    streamlit run dashboard.py
"""

import json
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = "precios_multitienda.db"

st.set_page_config(page_title="Precios Refrigeración - Multi-tienda", layout="wide")
st.title("📈 Evolución de precios - Refrigeración (multi-tienda)")


@st.cache_data(ttl=3600)
def cargar_datos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM price_history", conn)
    conn.close()
    if df.empty:
        return df
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["especificaciones"] = df["especificaciones"].apply(lambda x: json.loads(x) if x else {})
    specs_df = pd.json_normalize(df["especificaciones"])
    df = pd.concat([df.drop(columns=["especificaciones"]), specs_df], axis=1)
    return df


df = cargar_datos()

if df.empty:
    st.warning(
        "No hay datos todavía. Corre `python run_all.py` al menos una vez "
        "(y de nuevo otro día distinto para ver evolución)."
    )
    st.stop()

# ---------------- FILTROS (sidebar) ----------------
st.sidebar.header("Filtros")

retailers = sorted(df["retailer"].dropna().unique())
retailer_sel = st.sidebar.multiselect("Tienda", retailers, default=retailers)
df_r = df[df["retailer"].isin(retailer_sel)]

tipos = sorted(df_r["tipo_producto"].dropna().unique())
tipo_sel = st.sidebar.multiselect("Tipo de producto", tipos, default=tipos)
df_t = df_r[df_r["tipo_producto"].isin(tipo_sel)]

# Filtro de capacidad (litros) — solo aplica sobre filas que sí tienen capacidad detectada
capacidades = df_t["capacidad_litros"].dropna()
if not capacidades.empty:
    cap_min, cap_max = int(capacidades.min()), int(capacidades.max())
    if cap_min == cap_max:
        # Un solo valor de capacidad en todo el dataset: no tiene sentido un slider
        df_cap = df_t
    else:
        rango_sel = st.sidebar.slider(
            "Capacidad (litros)",
            min_value=cap_min, max_value=cap_max, value=(cap_min, cap_max),
            help="Los productos sin capacidad detectada (confianza_alta=0) "
                 "quedan incluidos siempre, ya que no tienen este dato.",
        )
        sin_capacidad = df_t["capacidad_litros"].isna()
        en_rango = df_t["capacidad_litros"].between(rango_sel[0], rango_sel[1])
        df_cap = df_t[sin_capacidad | en_rango]
else:
    df_cap = df_t

marcas = sorted(df_cap["marca_normalizada"].dropna().unique())
marca_sel = st.sidebar.multiselect("Marca", marcas, default=marcas)
df_m = df_cap[df_cap["marca_normalizada"].isin(marca_sel)]

solo_alta_confianza = st.sidebar.checkbox(
    "Solo matches de alta confianza",
    value=True,
    help="Si lo desmarcas, incluye productos donde no se pudo detectar la "
         "capacidad exacta y el match entre tiendas es menos seguro.",
)
if solo_alta_confianza:
    df_m = df_m[df_m["confianza_alta"] == 1]

# Selector de producto por canonical_id, mostrando un nombre representativo
nombres_por_canonical = (
    df_m.sort_values("fecha")
    .groupby("canonical_id")["producto"]
    .last()
    .to_dict()
)
opciones = sorted(nombres_por_canonical.items(), key=lambda x: x[1])
etiquetas = {cid: f"{nombre} ({cid})" for cid, nombre in opciones}

producto_sel = st.sidebar.multiselect(
    "Producto específico (opcional)",
    options=list(etiquetas.keys()),
    format_func=lambda cid: etiquetas[cid],
)
df_filtrado = df_m if not producto_sel else df_m[df_m["canonical_id"].isin(producto_sel)]

st.sidebar.markdown(
    f"**{df_filtrado['canonical_id'].nunique()}** productos únicos coinciden "
    f"(**{df_filtrado['sku_id'].nunique()}** SKUs entre tiendas)"
)

# ---------------- GRÁFICA DE EVOLUCIÓN ----------------
if df_filtrado.empty:
    st.info("Ningún producto coincide con los filtros seleccionados.")
    st.stop()

df_filtrado["etiqueta"] = (
    df_filtrado["producto"].str.slice(0, 40) + " — " + df_filtrado["retailer"]
)
df_filtrado["fecha_str"] = df_filtrado["fecha"].dt.strftime("%Y-%m-%d")

fig = px.line(
    df_filtrado.sort_values("fecha"),
    x="fecha_str", y="precio", color="etiqueta",
    markers=True,
    labels={"fecha_str": "Fecha", "precio": "Precio (COP)", "etiqueta": "Producto (tienda)"},
    title="Evolución de precio por producto y tienda",
)
fig.update_xaxes(type="category")
st.plotly_chart(fig, use_container_width=True)

# ---------------- COMPARATIVO ENTRE TIENDAS (mismo canonical_id) ----------------
st.subheader("Comparativo entre tiendas (mismo producto)")
ultima_fecha = df_filtrado["fecha"].max()
comparativo = (
    df_filtrado[df_filtrado["fecha"] == ultima_fecha]
    .sort_values(["canonical_id", "precio"])
    [["canonical_id", "producto", "retailer", "marca_normalizada", "tipo_producto",
      "capacidad_litros", "precio", "confianza_alta", "url"]]
)
st.dataframe(comparativo, use_container_width=True, hide_index=True)

st.caption(
    "⚠️ Los productos con 'confianza_alta' = 0 fueron agrupados sin detectar "
    "la capacidad exacta — revisa `revisar_posibles_duplicados.csv` (generado "
    "por run_all.py) para confirmar o descartar esos matches manualmente."
)
