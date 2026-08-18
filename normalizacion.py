"""
Normalización y matching de productos entre retailers
--------------------------------------------------------
Objetivo: que "Nevera LG 471L No Frost Silver" (Éxito) y
"Refrigerador LG 471 Litros Silver No Frost" (Jumbo) terminen con el
MISMO canonical_id, para que la gráfica histórica los trate como un
solo producto en vez de dos líneas separadas.

Estrategia (híbrida, no "IA mágica" — deliberadamente conservadora
para evitar falsos positivos que mezclen productos distintos):

1. Extraer atributos estructurados por reglas: marca, tipo de producto,
   capacidad en litros. Esto es determinístico y confiable.
2. canonical_key = "marca|tipo|capacidad_l" -> hash corto = canonical_id.
   Si dos filas (de cualquier retailer) generan el mismo canonical_id,
   son "el mismo producto" para efectos de la gráfica.
3. Si no se pudo extraer capacidad (ej. minibares chiquitos, o texto raro),
   se cae a un canonical_id basado solo en marca+tipo+similitud de texto,
   y se marca is_low_confidence=True para que sepas que ese match es
   menos seguro.
4. Adicionalmente, generar_reporte_revision() compara TODOS los productos
   sin capacidad detectada usando fuzzy matching (rapidfuzz) y saca un CSV
   de "posibles duplicados" para que TÚ decidas si son el mismo producto,
   en vez de que el sistema los fusione solo.

Requisitos:
    pip install rapidfuzz
"""

import hashlib
import re
import unicodedata

from rapidfuzz import fuzz

# ----------------------------------------------------------------------------
# Diccionarios de referencia (ajusta/agrega marcas y tipos según lo que veas)
# ----------------------------------------------------------------------------

MARCAS_CONOCIDAS = [
    "lg", "samsung", "whirlpool", "mabe", "haceb", "challenger", "electrolux",
    "kalley", "ge", "indurama", "frigidaire", "midea", "hisense", "koblenz",
    "oster", "philco", "sankey", "abba", "hyundai", "condura", "fensa",
    "smeg", "bosch", "beko", "daewoo", "coldex", "khepri", "westinghouse",
]

TIPOS_PRODUCTO = {
    "nevera": ["nevera", "refrigerador", "frigorifico", "frigorífico"],
    "nevecon": ["nevecon", "nevecón"],
    "congelador": ["congelador", "freezer", "friser"],
    "minibar": ["minibar", "mini bar", "mini nevera", "mininevera", "minirefrigerador"],
    "cava_vinos": ["cava de vino", "cava vinos", "vinera", "wine cooler"],
    "dispensador_agua": ["dispensador de agua", "dispensador agua"],
}

# Patrones de capacidad: "471L", "471 L", "471 Litros", "471Lt", "18 Pies"
PATRON_LITROS = re.compile(r"(\d{2,4}(?:[.,]\d{1,2})?)\s*(?:l|lt|lts|litros)\b", re.IGNORECASE)
PATRON_PIES = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:pies|pies3|pie3|cu\.?\s*ft)\b", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Normalización de texto
# ----------------------------------------------------------------------------

def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_texto(texto: str) -> str:
    texto = quitar_acentos(texto or "").lower()
    texto = re.sub(r"[^a-z0-9\s.,]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# ----------------------------------------------------------------------------
# Extracción de atributos
# ----------------------------------------------------------------------------

def extraer_marca(nombre_producto: str, marca_declarada: str = "") -> str:
    """Prioriza la marca que ya venga del retailer; si no, la busca en el nombre."""
    if marca_declarada and marca_declarada.strip():
        return normalizar_texto(marca_declarada)

    texto = normalizar_texto(nombre_producto)
    for marca in MARCAS_CONOCIDAS:
        if re.search(rf"\b{re.escape(marca)}\b", texto):
            return marca
    return "desconocida"


def extraer_tipo_producto(nombre_producto: str, categoria: str = "") -> str:
    texto = normalizar_texto(f"{categoria} {nombre_producto}")
    for tipo, palabras_clave in TIPOS_PRODUCTO.items():
        for palabra in palabras_clave:
            if normalizar_texto(palabra) in texto:
                return tipo
    return "otro"


def extraer_capacidad_litros(nombre_producto: str) -> float | None:
    texto = normalizar_texto(nombre_producto)

    m = PATRON_LITROS.search(texto)
    if m:
        return float(m.group(1).replace(",", "."))

    # Conversión aproximada de pies cúbicos a litros (1 pie3 = 28.3168 L)
    m = PATRON_PIES.search(texto)
    if m:
        pies = float(m.group(1).replace(",", "."))
        return round(pies * 28.3168, 1)

    return None


# ----------------------------------------------------------------------------
# Canonical ID
# ----------------------------------------------------------------------------

def generar_producto_normalizado(nombre_producto: str, marca_declarada: str = "", categoria: str = "") -> dict:
    marca = extraer_marca(nombre_producto, marca_declarada)
    tipo = extraer_tipo_producto(nombre_producto, categoria)
    capacidad = extraer_capacidad_litros(nombre_producto)

    if capacidad is not None:
        clave = f"{marca}|{tipo}|{capacidad}"
        confianza_alta = True
    else:
        # Sin capacidad detectada: la llave es menos específica -> menor confianza.
        # Se agrega un fragmento del texto normalizado para no juntar
        # productos distintos de la misma marca+tipo bajo una sola llave.
        texto_norm = normalizar_texto(nombre_producto)
        fragmento = " ".join(sorted(texto_norm.split())[:6])  # bag-of-words simple
        clave = f"{marca}|{tipo}|{fragmento}"
        confianza_alta = False

    canonical_id = hashlib.md5(clave.encode("utf-8")).hexdigest()[:12]

    return {
        "canonical_id": canonical_id,
        "marca_normalizada": marca,
        "tipo_producto": tipo,
        "capacidad_litros": capacidad,
        "confianza_alta": confianza_alta,
    }


# ----------------------------------------------------------------------------
# Revisión asistida para casos de baja confianza (fuzzy matching)
# ----------------------------------------------------------------------------

def sugerir_posibles_duplicados(productos: list[dict], umbral: int = 88) -> list[dict]:
    """
    Compara SOLO los productos de baja confianza (sin capacidad detectada,
    o de tipo 'otro') dentro de la misma marca, y sugiere pares que podrían
    ser el mismo producto según similitud de texto.

    `productos` = lista de dicts con al menos: producto, marca_normalizada,
    canonical_id, retailer.

    No fusiona nada automáticamente — genera sugerencias para que las
    confirmes tú (ver generar_reporte_revision en el script de matching).
    """
    sugerencias = []
    baja_confianza = [p for p in productos if not p.get("confianza_alta", True)]

    # Agrupar por marca para no comparar N^2 contra todo el catálogo
    por_marca: dict[str, list[dict]] = {}
    for p in baja_confianza:
        por_marca.setdefault(p["marca_normalizada"], []).append(p)

    for marca, grupo in por_marca.items():
        for i in range(len(grupo)):
            for j in range(i + 1, len(grupo)):
                a, b = grupo[i], grupo[j]
                if a["canonical_id"] == b["canonical_id"]:
                    continue
                if a.get("retailer") == b.get("retailer"):
                    continue  # dentro del mismo retailer no hace falta fusionar
                score = fuzz.token_sort_ratio(
                    normalizar_texto(a["producto"]), normalizar_texto(b["producto"])
                )
                if score >= umbral:
                    sugerencias.append({
                        "producto_a": a["producto"], "retailer_a": a.get("retailer"),
                        "producto_b": b["producto"], "retailer_b": b.get("retailer"),
                        "similitud": score,
                        "canonical_id_a": a["canonical_id"],
                        "canonical_id_b": b["canonical_id"],
                    })

    return sorted(sugerencias, key=lambda x: -x["similitud"])
