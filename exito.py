"""
Scraper de Éxito (VTEX) — confirmado funcionando.
"""

import time

import requests

BASE_URL = "https://www.exito.com/api/catalog_system/pub/products/search"

CATEGORIAS = {
    "Neveras":      "electrodomesticos/refrigeracion/neveras",
    "Nevecones":    "electrodomesticos/refrigeracion/nevecones",
    "Minibares":    "electrodomesticos/refrigeracion/minibares",
    "Congeladores": "refrigeracion/congeladores",
}

PAGE_SIZE = 50
MAX_PAGES = 20
SLEEP_BETWEEN_REQUESTS = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}

RETAILER = "Exito"


def _parsear_producto(producto: dict, categoria_nombre: str) -> list[dict]:
    filas = []
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
            continue

        specs = {}
        variaciones = item.get("Variations") or []
        for nombre_var in variaciones:
            valores = item.get(nombre_var)
            if valores:
                specs[nombre_var] = valores[0] if isinstance(valores, list) else valores

        filas.append({
            "retailer": RETAILER,
            "sku_id": f"{RETAILER}-{item.get('itemId', '')}",
            "product_id": product_id,
            "producto": nombre_producto,
            "marca": marca,
            "categoria": categoria_nombre,
            "precio": precio,
            "precio_lista": precio_lista,
            "disponible": disponible,
            "url": link,
            "especificaciones": specs,
        })
    return filas


def _obtener_categoria(categoria_nombre: str, categoria_path: str) -> list[dict]:
    todas_las_filas = []
    for pagina in range(MAX_PAGES):
        desde = pagina * PAGE_SIZE
        hasta = desde + PAGE_SIZE - 1
        url = f"{BASE_URL}/{categoria_path}"
        params = {"_from": desde, "_to": hasta}

        print(f"  [{RETAILER}] pidiendo {categoria_nombre} [{desde}-{hasta}]")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if resp.status_code in (200, 206):
            data = resp.json()
        elif resp.status_code == 416:
            break
        else:
            print(f"  ! [{RETAILER}] status inesperado {resp.status_code}")
            break

        if not data:
            break

        for producto in data:
            todas_las_filas.extend(_parsear_producto(producto, categoria_nombre))

        if len(data) < PAGE_SIZE:
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return todas_las_filas


def scrape() -> list[dict]:
    """Punto de entrada estándar que usa run_all.py."""
    todas_las_filas = []
    for nombre, path in CATEGORIAS.items():
        filas = _obtener_categoria(nombre, path)
        print(f"  [{RETAILER}] {nombre}: {len(filas)} SKUs")
        todas_las_filas.extend(filas)
    return todas_las_filas


if __name__ == "__main__":
    filas = scrape()
    print(f"Total {RETAILER}: {len(filas)} filas")
