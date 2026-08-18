"""
Orquestador multi-retailer
----------------------------
Corre cada scraper de retailers/, aplica normalización/matching, y guarda
todo en precios_multitienda.db. Si un retailer falla (ej. Alkosto/Falabella
aún no implementados), lo salta con un aviso en vez de tumbar toda la corrida.

Uso:
    python run_all.py
"""

import json
import sqlite3
from datetime import date, datetime

from normalizacion import generar_producto_normalizado, sugerir_posibles_duplicados
from retailers import exito, jumbo, alkosto, falabella

DB_PATH = "precios_multitienda.db"

# Agrega o quita retailers de esta lista según cuáles tengas listos
SCRAPERS = [exito, jumbo, alkosto, falabella]


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            fecha             TEXT NOT NULL,
            retailer          TEXT NOT NULL,
            sku_id            TEXT NOT NULL,
            product_id        TEXT,
            producto          TEXT,
            marca             TEXT,
            categoria         TEXT,
            precio            REAL,
            precio_lista      REAL,
            disponible        INTEGER,
            url               TEXT,
            especificaciones  TEXT,
            canonical_id      TEXT,
            marca_normalizada TEXT,
            tipo_producto     TEXT,
            capacidad_litros  REAL,
            confianza_alta    INTEGER,
            PRIMARY KEY (fecha, retailer, sku_id)
        )
    """)
    conn.commit()


def guardar_snapshot(conn: sqlite3.Connection, filas: list[dict]) -> int:
    cur = conn.cursor()
    hoy = date.today().isoformat()
    insertados = 0

    for f in filas:
        norm = generar_producto_normalizado(
            nombre_producto=f["producto"],
            marca_declarada=f.get("marca", ""),
            categoria=f.get("categoria", ""),
        )
        try:
            cur.execute("""
                INSERT OR REPLACE INTO price_history
                (fecha, retailer, sku_id, product_id, producto, marca, categoria,
                 precio, precio_lista, disponible, url, especificaciones,
                 canonical_id, marca_normalizada, tipo_producto, capacidad_litros, confianza_alta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hoy, f["retailer"], f["sku_id"], f.get("product_id"), f["producto"],
                f.get("marca"), f.get("categoria"), f["precio"], f.get("precio_lista"),
                f.get("disponible"), f.get("url"),
                json.dumps(f.get("especificaciones", {}), ensure_ascii=False),
                norm["canonical_id"], norm["marca_normalizada"], norm["tipo_producto"],
                norm["capacidad_litros"], int(norm["confianza_alta"]),
            ))
            insertados += 1
        except sqlite3.Error as e:
            print(f"  ! error insertando {f.get('sku_id')}: {e}")

    conn.commit()
    return insertados


def generar_reporte_revision(conn: sqlite3.Connection) -> None:
    """Saca un CSV con posibles duplicados cross-retailer de baja confianza."""
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT producto, retailer, canonical_id, marca_normalizada, confianza_alta
        FROM price_history
        WHERE fecha = (SELECT MAX(fecha) FROM price_history)
    """)
    productos = [
        {"producto": r[0], "retailer": r[1], "canonical_id": r[2],
         "marca_normalizada": r[3], "confianza_alta": bool(r[4])}
        for r in cur.fetchall()
    ]

    sugerencias = sugerir_posibles_duplicados(productos)
    if not sugerencias:
        print("Sin sugerencias de posibles duplicados para revisar.")
        return

    import csv
    with open("revisar_posibles_duplicados.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sugerencias[0].keys()))
        writer.writeheader()
        writer.writerows(sugerencias)
    print(f"{len(sugerencias)} posibles duplicados cross-retailer -> revisar_posibles_duplicados.csv")


def main():
    print(f"=== Corrida {datetime.now().isoformat(timespec='seconds')} ===")
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total = 0
    for modulo in SCRAPERS:
        nombre = getattr(modulo, "RETAILER", modulo.__name__)
        print(f"\n--- {nombre} ---")
        try:
            filas = modulo.scrape()
        except NotImplementedError as e:
            print(f"  (saltado) {e}")
            continue
        except Exception as e:
            print(f"  ! error inesperado en {nombre}, se salta: {e}")
            continue

        insertadas = guardar_snapshot(conn, filas)
        print(f"  {insertadas} filas guardadas para {nombre}")
        total += insertadas

    generar_reporte_revision(conn)
    conn.close()
    print(f"\nListo. {total} filas guardadas en total en {DB_PATH}")


if __name__ == "__main__":
    main()
