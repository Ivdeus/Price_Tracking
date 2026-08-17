# -*- coding: utf-8 -*-
"""
Created on Sun Aug 16 13:09:50 2026

@author: ivdeu
"""
### Tracker de precios - Éxito (Refrigeración) ###
"""
Tracker de precios - Éxito (Refrigeración)
--------------------------------------------
Consulta la API pública de catálogo de VTEX (la plataforma e-commerce que usa
exito.com) en lugar de scrapear el HTML. Es más rápido, más estable, y trae
precio + marca + características ya estructuradas en JSON.

Cada corrida inserta una fila por SKU con la fecha de hoy en una tabla
`price_history` de SQLite. Corriéndolo todos los días (ver README) se va
construyendo el histórico solo.

Requisitos:
    pip install requests

Uso:
    python scraper.py
"""

import sqlite3
import time
import json
from datetime import date, datetime

import requests

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

BASE_URL = "https://www.exito.com/api/catalog_system/pub/products/search"

# Subcategorías a rastrear. La clave es el nombre "bonito" que verás en el
# filtro del dashboard; el valor es la ruta real de la categoría en exito.com.
CATEGORIAS = {
    "Neveras":     "electrodomesticos/refrigeracion/neveras",
    "Nevecones":   "electrodomesticos/refrigeracion/nevecones",
    "Minibares":   "electrodomesticos/refrigeracion/minibares",
    "Congeladores": "refrigeracion/congeladores",
}

PAGE_SIZE = 50          # VTEX limita a 50 por página en este endpoint
MAX_PAGES = 20          # tope de seguridad (50*20 = 1000 productos)
SLEEP_BETWEEN_REQUESTS = 1.5  # segundos, para no golpear el servidor de más
DB_PATH = "precios_exito.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}


# ----------------------------------------------------------------------------
# BASE DE DATOS
# ----------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            fecha           TEXT NOT NULL,
            sku_id          TEXT NOT NULL,
            product_id      TEXT,
            producto        TEXT,
            marca           TEXT,
            categoria       TEXT,
            precio          REAL,
            precio_lista    REAL,
            disponible      INTEGER,
            url             TEXT,
            especificaciones TEXT,  -- JSON serializado: {"Capacidad (L)": "500", "Color": "Plateado", ...}
            PRIMARY KEY (fecha, sku_id)
        )
    """)
    conn.commit()


def guardar_snapshot(conn: sqlite3.Connection, filas: list[dict]) -> int:
    cur = conn.cursor()
    insertados = 0
    for f in filas:
        try:
            cur.execute("""
                INSERT OR REPLACE INTO price_history
                (fecha, sku_id, product_id, producto, marca, categoria,
                 precio, precio_lista, disponible, url, especificaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f["fecha"], f["sku_id"], f["product_id"], f["producto"],
                f["marca"], f["categoria"], f["precio"], f["precio_lista"],
                f["disponible"], f["url"], json.dumps(f["especificaciones"], ensure_ascii=False),
            ))
            insertados += 1
        except sqlite3.Error as e:
            print(f"  ! error insertando SKU {f.get('sku_id')}: {e}")
    conn.commit()
    return insertados


# ----------------------------------------------------------------------------
# EXTRACCIÓN
# ----------------------------------------------------------------------------

def extraer_especificaciones(item: dict) -> dict:
    """Saca las variaciones (capacidad, color, tipo, etc.) de un SKU de VTEX."""
    specs = {}
    variaciones = item.get("Variations") or item.get("variations") or []
    for nombre_var in variaciones:
        valores = item.get(nombre_var)
        if valores:
            specs[nombre_var] = valores[0] if isinstance(valores, list) else valores
    return specs


def parsear_producto(producto: dict, categoria_nombre: str) -> list[dict]:
    """Convierte un producto de VTEX (con posibles varios SKUs) en filas planas."""
    filas = []
    hoy = date.today().isoformat()
    nombre_producto = producto.get("productName", "")
    marca = producto.get("brand", "")
    product_id = producto.get("productId", "")
    link = producto.get("link", "")

    for item in producto.get("items", []):
        sellers = item.get("sellers", [])
        if not sellers:
            continue
        oferta = sellers[0].get("commertialOffer", {})
        precio = oferta.get("Price")
        precio_lista = oferta.get("ListPrice")
        disponible = oferta.get("AvailableQuantity", 0)

        if precio is None or precio <= 0:
            continue  # sin oferta activa (sin stock), se ignora

        filas.append({
            "fecha": hoy,
            "sku_id": item.get("itemId", ""),
            "product_id": product_id,
            "producto": nombre_producto,
            "marca": marca,
            "categoria": categoria_nombre,
            "precio": precio,
            "precio_lista": precio_lista,
            "disponible": disponible,
            "url": link,
            "especificaciones": extraer_especificaciones(item),
        })
    return filas


def obtener_categoria(categoria_nombre: str, categoria_path: str) -> list[dict]:
    """Pagina sobre una categoría y devuelve todas las filas (SKU + precio) del día."""
    todas_las_filas = []
    for pagina in range(MAX_PAGES):
        desde = pagina * PAGE_SIZE
        hasta = desde + PAGE_SIZE - 1
        url = f"{BASE_URL}/{categoria_path}"
        params = {"_from": desde, "_to": hasta}

        print(f"  -> pidiendo {categoria_nombre} [{desde}-{hasta}]")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if resp.status_code == 206 or resp.status_code == 200:
            data = resp.json()
        elif resp.status_code == 416:
            # rango fuera de límite -> no hay más productos
            break
        else:
            print(f"  ! status inesperado {resp.status_code}, deteniendo esta categoría")
            break

        if not data:
            break  # no más productos

        for producto in data:
            todas_las_filas.extend(parsear_producto(producto, categoria_nombre))

        if len(data) < PAGE_SIZE:
            break  # última página

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return todas_las_filas


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    print(f"=== Corrida {datetime.now().isoformat(timespec='seconds')} ===")
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total_insertadas = 0
    for nombre, path in CATEGORIAS.items():
        print(f"Categoría: {nombre} ({path})")
        filas = obtener_categoria(nombre, path)
        print(f"  {len(filas)} SKUs encontrados")
        total_insertadas += guardar_snapshot(conn, filas)

    conn.close()
    print(f"Listo. {total_insertadas} filas guardadas/actualizadas en {DB_PATH}")


if __name__ == "__main__":
    main()
