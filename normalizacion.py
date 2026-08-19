"""
Normalizacion y matching de productos entre retailers
--------------------------------------------------------
Objetivo: que el mismo producto fisico, vendido en distintas tiendas con
nombres distintos, termine bajo un mismo canonical_id.

DISENO (2 pasos, deliberado):

PASO 1 - Llave primaria determinística (generar_producto_normalizado):
    Usa SIEMPRE marca + tipo + capacidad como llave base cuando hay
    capacidad detectable. Es la señal más universal: casi todos los
    retailers ponen los litros en el nombre, no siempre ponen el código
    de modelo. Si no hay capacidad, cae a un fallback de texto (baja
    confianza).

PASO 2 - Fusion por referencia (fusionar_por_referencia):
    Un post-procesamiento que UNE grupos que ya se generaron con llaves
    distintas en el paso 1, cuando comparten la misma referencia/modelo
    detectada. Esto resuelve el caso real que tenías en mente: una tienda
    escribe "Samsung RT38K5930 435L" (con codigo) y otra "Nevera Samsung
    435 Litros Silver" (sin codigo) -- ambas quedan con capacidad=435 y
    ya coinciden en el paso 1; pero si una tienda redondea distinto la
    capacidad (ej. 435 vs 434.7), el codigo de modelo compartido las
    fusiona igual en el paso 2.

Por que no usar la referencia como llave primaria (como en la version
anterior): porque un producto SIN código detectado (frecuente) generaría
una llave de un "espacio" distinto al de su version CON código, y nunca
se cruzarían -- exactamente el bug que teníamos que evitar.

Requisitos:
    pip install rapidfuzz
"""

import hashlib
import re
import unicodedata

from rapidfuzz import fuzz

# ----------------------------------------------------------------------------
# Diccionarios y patrones
# ----------------------------------------------------------------------------

MARCAS_CONOCIDAS = [
    "lg", "samsung", "whirlpool", "mabe", "haceb", "challenger", "electrolux",
    "kalley", "ge", "indurama", "frigidaire", "midea", "hisense", "koblenz",
    "oster", "philco", "sankey", "abba", "hyundai", "condura", "fensa",
    "smeg", "bosch", "beko", "daewoo", "coldex", "khepri", "westinghouse",
]

TIPOS_PRODUCTO = {
    "nevera": ["nevera", "refrigerador", "frigorifico", "combi"],
    "nevecon": ["nevecon", "side by side", "french door"],
    "congelador": ["congelador", "freezer", "friser"],
    "minibar": ["minibar", "mini bar", "mini nevera", "mininevera", "minirefrigerador", "frigobar"],
    "cava_vinos": ["cava de vino", "cava vinos", "vinera", "wine cooler"],
    "dispensador_agua": ["dispensador de agua", "dispensador agua"],
}

PATRON_LITROS = re.compile(r"(\d{2,4}(?:[.,]\d{1,2})?)\s*(?:l|lt|lts|litros)\b", re.IGNORECASE)
PATRON_PIES = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:pies|pies3|pie3|cu\.?\s*ft|pc)\b", re.IGNORECASE)

# Candidatos a referencia/modelo: alfanumérico con guiones opcionales, 4-20 chars
PATRON_REFERENCIA = re.compile(r"\b(?=[a-z0-9\-]*[0-9])(?=[a-z0-9\-]*[a-z])[a-z0-9\-]{4,20}\b", re.IGNORECASE)

# Tokens que el patrón de arriba podría atrapar mal (num+unidad pegados)
FALSOS_REFERENCIAS = re.compile(r"^\d+(l|lt|lts|litros|v|w|kw|pies|pc|hz)$")


# ----------------------------------------------------------------------------
# Normalización de texto
# ----------------------------------------------------------------------------

def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_texto(texto: str) -> str:
    texto = quitar_acentos(texto or "").lower()
    texto = texto.replace("no frost", "nofrost")
    texto = texto.replace("acero inoxidable", "inox")
    texto = re.sub(r"[^a-z0-9\s.,\-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# ----------------------------------------------------------------------------
# Extracción de atributos
# ----------------------------------------------------------------------------

def extraer_marca(nombre_producto: str, marca_declarada: str = "") -> str:
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
    m = PATRON_PIES.search(texto)
    if m:
        pies = float(m.group(1).replace(",", "."))
        return round(pies * 28.3168, 1)
    return None


def _es_referencia_valida(token: str) -> bool:
    if FALSOS_REFERENCIAS.match(token):
        return False
    digitos = sum(c.isdigit() for c in token)
    letras = sum(c.isalpha() for c in token)
    # Al menos 2 dígitos y 1 letra: reduce falsos positivos tipo "plata1"
    return digitos >= 2 and letras >= 1


def extraer_referencia(nombre_producto: str) -> str | None:
    """Extrae el codigo de modelo, normalizado SIN guiones para que
    'RMA-313-FXCU' y 'RMA313FXCU' (distinto formato entre tiendas) generen
    el mismo valor."""
    texto = normalizar_texto(nombre_producto)
    candidatos = [m for m in PATRON_REFERENCIA.findall(texto) if _es_referencia_valida(m)]
    if not candidatos:
        return None
    # Preferir el candidato con más dígitos (más probable que sea el código
    # real de modelo y no un adjetivo suelto), y de empate el más largo.
    mejor = max(candidatos, key=lambda t: (sum(c.isdigit() for c in t), len(t)))
    return mejor.replace("-", "")


# ----------------------------------------------------------------------------
# Paso 1: llave primaria (capacidad) + atributos
# ----------------------------------------------------------------------------

def generar_producto_normalizado(nombre_producto: str, marca_declarada: str = "", categoria: str = "") -> dict:
    marca = extraer_marca(nombre_producto, marca_declarada)
    tipo = extraer_tipo_producto(nombre_producto, categoria)
    capacidad = extraer_capacidad_litros(nombre_producto)
    referencia = extraer_referencia(nombre_producto)

    if capacidad is not None:
        clave = f"{marca}|{tipo}|{capacidad}"
        confianza_alta = True
        nivel_match = "capacidad"
    elif referencia:
        # Sin capacidad pero con codigo de modelo: sigue siendo bastante
        # confiable, el paso 2 lo puede fusionar con su version "con litros"
        # de otra tienda si comparten la misma referencia.
        clave = f"{marca}|ref|{referencia}"
        confianza_alta = True
        nivel_match = "referencia"
    else:
        texto_norm = normalizar_texto(nombre_producto)
        palabras_limpias = [
            w for w in texto_norm.split()
            if w not in ("nevera", "refrigerador", "de", "con", "litros", "lts")
        ]
        fragmento = " ".join(sorted(palabras_limpias)[:5])
        clave = f"{marca}|{tipo}|{fragmento}"
        confianza_alta = False
        nivel_match = "texto_basico"

    canonical_id = hashlib.md5(clave.encode("utf-8")).hexdigest()[:12]

    return {
        "canonical_id": canonical_id,
        "marca_normalizada": marca,
        "tipo_producto": tipo,
        "capacidad_litros": capacidad,
        "referencia_modelo": referencia,
        "confianza_alta": confianza_alta,
        "nivel_match": nivel_match,
    }


# ----------------------------------------------------------------------------
# Paso 2: fusion posterior por referencia compartida (une distintas llaves)
# ----------------------------------------------------------------------------

def fusionar_por_referencia(productos: list[dict]) -> dict[str, str]:
    """
    Recibe TODAS las filas de una corrida (ya con canonical_id del paso 1)
    y devuelve un mapeo {canonical_id_viejo: canonical_id_final}.

    Si dos productos de la MISMA marca comparten la misma referencia_modelo
    detectada -- aunque hayan quedado con canonical_id distinto en el paso 1
    (uno via capacidad, otro via referencia, o capacidades que no
    coincidieron exacto por redondeo) -- se fusionan en un solo grupo.

    Cada producto necesita al menos: canonical_id, marca_normalizada,
    referencia_modelo.
    """
    padre: dict[str, str] = {}

    def find(x: str) -> str:
        padre.setdefault(x, x)
        raiz = x
        while padre[raiz] != raiz:
            raiz = padre[raiz]
        while padre[x] != raiz:
            padre[x], x = raiz, padre[x]
        return raiz

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            padre[ra] = rb

    por_referencia: dict[str, list[str]] = {}
    for p in productos:
        ref = p.get("referencia_modelo")
        if ref:
            clave_ref = f"{p['marca_normalizada']}|{ref}"
            por_referencia.setdefault(clave_ref, []).append(p["canonical_id"])

    for ids in por_referencia.values():
        for i in range(1, len(ids)):
            union(ids[0], ids[i])

    todos_los_ids = {p["canonical_id"] for p in productos}
    return {cid: find(cid) for cid in todos_los_ids}


# ----------------------------------------------------------------------------
# Revision asistida para casos de baja confianza (fuzzy matching)
# ----------------------------------------------------------------------------

def sugerir_posibles_duplicados(productos: list[dict], umbral: int = 85) -> list[dict]:
    """Compara SOLO productos de baja confianza (mismo marca+tipo) via
    similitud de texto, para revision manual -- no fusiona nada solo."""
    sugerencias = []
    baja_confianza = [p for p in productos if not p.get("confianza_alta", True)]

    por_grupo: dict[str, list[dict]] = {}
    for p in baja_confianza:
        llave_grupo = f"{p['marca_normalizada']}_{p['tipo_producto']}"
        por_grupo.setdefault(llave_grupo, []).append(p)

    for grupo in por_grupo.values():
        for i in range(len(grupo)):
            for j in range(i + 1, len(grupo)):
                a, b = grupo[i], grupo[j]
                if a["canonical_id"] == b["canonical_id"]:
                    continue
                if a.get("retailer") == b.get("retailer"):
                    continue
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
