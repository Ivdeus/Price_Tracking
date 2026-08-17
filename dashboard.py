# -*- coding: utf-8 -*-
"""
Created on Sun Aug 16 13:13:38 2026

@author: ivdeu
"""
"""
Dashboard de precios - Éxito (Refrigeración)
----------------------------------------------
Lee precios_exito.db y permite filtrar por marca, producto y características,
mostrando la evolución del precio en el tiempo.

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

DB_PATH = "precios_exito.db"

st.set_page_config(page_title="Precios Éxito - Refrigeración", layout="wide")
st.title("📈 Evolución de precios - Refrigeración (Éxito)")


@st.cache_data(ttl=3600)
def cargar_datos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM price_history", conn)
    conn.close()
    if df.empty:
        return df
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["especificaciones"] = df["especificaciones"].apply(
        lambda x: json.loads(x) if x else {}
    )
    # expandir especificaciones a columnas (dinámico, según lo que haya)
    specs_df = pd.json_normalize(df["especificaciones"])
    df = pd.concat([df.drop(columns=["especificaciones"]), specs_df], axis=1)
    return df


df = cargar_datos()

if df.empty:
    st.warning(
        "No hay datos todavía. Corre `python scraper.py` al menos una vez "
        "(y de nuevo otro día distinto para ver evolución)."
    )
    st.stop()

# ---------------- FILTROS (sidebar) ----------------
st.sidebar.header("Filtros")

# Tipo de producto (Neveras, Nevecones, Minibares, Congeladores...)
tipos = sorted(df["categoria"].dropna().unique())
tipo_sel = st.sidebar.multiselect("Tipo de producto", tipos, default=tipos)

df_tipo = df[df["categoria"].isin(tipo_sel)]

marcas = sorted(df_tipo["marca"].dropna().unique())
marca_sel = st.sidebar.multiselect("Marca", marcas, default=marcas)

df_marca = df_tipo[df_tipo["marca"].isin(marca_sel)]

productos = sorted(df_marca["producto"].dropna().unique())
producto_sel = st.sidebar.multiselect("Producto específico", productos)

df_filtrado = df_marca if not producto_sel else df_marca[df_marca["producto"].isin(producto_sel)]

# filtros dinámicos por características (cualquier columna extra que no sea de precio/meta)
columnas_base = {
    "fecha", "sku_id", "product_id", "producto", "marca", "categoria",
    "precio", "precio_lista", "disponible", "url",
}
columnas_specs = [c for c in df.columns if c not in columnas_base]

for col in columnas_specs:
    valores = sorted(df_filtrado[col].dropna().unique())
    if 1 < len(valores) <= 30:
        seleccion = st.sidebar.multiselect(col, valores)
        if seleccion:
            df_filtrado = df_filtrado[df_filtrado[col].isin(seleccion)]

st.sidebar.markdown(f"**{df_filtrado['sku_id'].nunique()}** SKUs coinciden con el filtro")

# ---------------- GRÁFICA DE EVOLUCIÓN ----------------
if df_filtrado.empty:
    st.info("Ningún SKU coincide con los filtros seleccionados.")
    st.stop()

df_filtrado["etiqueta"] = df_filtrado["producto"] + " (" + df_filtrado["sku_id"].astype(str) + ")"
df_filtrado["fecha_str"] = df_filtrado["fecha"].dt.strftime("%Y-%m-%d")

fig = px.line(
    df_filtrado.sort_values("fecha"),
    x="fecha_str", y="precio", color="etiqueta",
    markers=True,
    labels={"fecha_str": "Fecha", "precio": "Precio (COP)", "etiqueta": "Producto"},
    title="Evolución de precio por SKU",
)
fig.update_xaxes(type="category")
st.plotly_chart(fig, use_container_width=True)

# ---------------- TABLA DEL ÚLTIMO SNAPSHOT ----------------
st.subheader("Último snapshot")
ultima_fecha = df_filtrado["fecha"].max()
tabla = df_filtrado[df_filtrado["fecha"] == ultima_fecha][
    ["categoria", "marca", "producto", "precio", "precio_lista", "disponible", "url"] + columnas_specs
].sort_values("precio")
st.dataframe(tabla, use_container_width=True, hide_index=True)
