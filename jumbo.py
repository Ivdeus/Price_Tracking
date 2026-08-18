"""
Scraper de Jumbo Colombia — confirmado funcionando (VTEX clásico).
----------------------------------------------------------------------
Ojo con la ruta: el "co/" que aparece en la URL del storefront
(jumbocolombia.com/co/electrodomesticos/...) es solo un prefijo de
enrutamiento del sitio, NO hace parte del árbol de categorías real que
usa esta API. La ruta correcta es sin el "co/" inicial.

Requisitos:
    pip install requests
"""

import time

import requests

BASE_URL = "https://www.jumbocolombia.com/api/catalog_system/pub/products/search"

CATEGORIAS = {
    "Neveras":      "electrodomesticos/refrigeracion/neveras",
    "Nevecones":    "electrodomesticos/refrigeracion/nevecones",
    "Minibares":    "electrodomesticos/refrigeracion/minibares",
    "Congeladores": "electrodomesticos/refrigeracion/congeladores",
}

PAGE_SIZE = 50
MAX_PAGES = 20
SLEEP_BETWEEN_REQUESTS = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}

RETAILER = "Jumbo"


def _parsear_producto(producto: dict, categoria_nombre: str) -> list[dict]:
    # Misma lógica que Éxito, porque si Jumbo está en VTEX el JSON debería
    # tener la misma forma.
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
        disponible = oferta.get("AvailableQuantity", 0)

        if precio is None or precio <= 0:
            continue

        specs = {}
        for nombre_var in (item.get("Variations") or []):
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
            "precio_lista": oferta.get("ListPrice"),
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
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
        except requests.RequestException as e:
            print(f"  ! [{RETAILER}] error de red: {e}")
            break

        if resp.status_code in (200, 206):
            try:
                data = resp.json()
            except ValueError:
                print(f"  ! [{RETAILER}] la respuesta no es JSON -> Jumbo probablemente "
                      f"NO está en VTEX, o la ruta es distinta. Revisa con DevTools.")
                break
        elif resp.status_code == 416:
            break
        else:
            print(f"  ! [{RETAILER}] status inesperado {resp.status_code} -> "
                  f"revisa BASE_URL con DevTools")
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
    todas_las_filas = []
    for nombre, path in CATEGORIAS.items():
        filas = _obtener_categoria(nombre, path)
        print(f"  [{RETAILER}] {nombre}: {len(filas)} SKUs")
        todas_las_filas.extend(filas)
    return todas_las_filas


if __name__ == "__main__":
    filas = scrape()
    print(f"Total {RETAILER}: {len(filas)} filas")