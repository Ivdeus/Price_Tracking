"""
Normalización y matching de productos entre retailers
--------------------------------------------------------
Objetivo: Unificar productos iguales bajo un mismo canonical_id.
Estrategia:
1. Buscar Referencia/Modelo (match exacto).
2. Buscar Capacidad en Litros (match determinístico).
3. Fallback: Similitud de texto (rapidfuzz) para revisión manual.
"""

import hashlib
import re
import unicodedata
from rapidfuzz import fuzz

# ----------------------------------------------------------------------------
# Diccionarios y Patrones
# ----------------------------------------------------------------------------

MARCAS_CONOCIDAS = [
    "lg", "samsung", "whirlpool", "mabe", "haceb", "challenger", "electrolux",
    "kalley", "ge", "indurama", "frigidaire", "midea", "hisense", "koblenz",
    "oster", "philco", "sankey", "abba", "hyundai", "condura", "fensa",
    "smeg", "bosch", "beko", "daewoo", "coldex", "khepri", "westinghouse",
]

TIPOS_PRODUCTO = {
    "nevera": ["nevera", "refrigerador", "frigorifico", "frigorífico", "combi"],
    "nevecon": ["nevecon", "nevecón", "side by side", "french door"],
    "congelador": ["congelador", "freezer", "friser"],
    "minibar": ["minibar", "mini bar", "mini nevera", "mininevera", "minirefrigerador", "frigobar"],
    "cava_vinos": ["cava de vino", "cava vinos", "vinera", "wine cooler"],
    "dispensador_agua": ["dispensador de agua", "dispensador agua"],
}

# Patrones de capacidad
PATRON_LITROS = re.compile(r"(\d{2,4}(?:[.,]\d{1,2})?)\s*(?:l|lt|lts|litros)\b", re.IGNORECASE)
PATRON_PIES = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:pies|pies3|pie3|cu\.?\s*ft|pc)\b", re.IGNORECASE)

# Patrón para referencias: Debe contener letras y números, opcionalmente guiones, de 4 a 20 caracteres
# Ej: "RT43K6231UT", "WRB311", "SBS-500"
PATRON_REFERENCIA = re.compile(r"\b(?=[a-z0-9\-]*[0-9])(?=[a-z0-9\-]*[a-z])[a-z0-9\-]{4,20}\b", re.IGNORECASE)

# Falsos positivos de referencias (capacidades pegadas a unidades que el regex podría capturar)
FALSOS_REFERENCIAS = re.compile(r"^\d+(l|lt|lts|litros|v|w|kw|pies|pc|hz)$")


# ----------------------------------------------------------------------------
# Normalización de texto
# ----------------------------------------------------------------------------

def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def normalizar_texto(texto: str) -> str:
    texto = quitar_acentos(texto or "").lower()
    # Estandarizar términos comunes que los retailers escriben distinto
    texto = texto.replace("no frost", "nofrost")
    texto = texto.replace("acero inoxidable", "inox")
    
    # Permitir letras, números, espacios, puntos, comas y GUIONES (clave para referencias)
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

    # Conversión aproximada de pies cúbicos a litros (1 pie3 = 28.3168 L)
    m = PATRON_PIES.search(texto)
    if m:
        pies = float(m.group(1).replace(",", "."))
        return round(pies * 28.3168, 1)

    return None

def extraer_referencia(nombre_producto: str) -> str | None:
    """Extrae el modelo o referencia alfanumérica del producto."""
    texto = normalizar_texto(nombre_producto)
    matches = PATRON_REFERENCIA.findall(texto)
    
    if matches:
        # Filtrar los que son simplemente "471l" o "110v"
        refs_validas = [m for m in matches if not FALSOS_REFERENCIAS.match(m)]
        if refs_validas:
            # Usualmente la referencia es el token alfanumérico más largo
            return max(refs_validas, key=len)
    return None


# ----------------------------------------------------------------------------
# Canonical ID
# ----------------------------------------------------------------------------

def generar_producto_normalizado(nombre_producto: str, marca_declarada: str = "", categoria: str = "") -> dict:
    marca = extraer_marca(nombre_producto, marca_declarada)
    tipo = extraer_tipo_producto(nombre_producto, categoria)
    capacidad = extraer_capacidad_litros(nombre_producto)
    referencia = extraer_referencia(nombre_producto)

    # 1. Prioridad Máxima: Tenemos la referencia/modelo exacto
    if referencia:
        clave = f"{marca}|{referencia}"
        confianza_alta = True
        nivel_match = "referencia"
        
    # 2. Prioridad Media: Tenemos el tamaño exacto
    elif capacidad is not None:
        clave = f"{marca}|{tipo}|{capacidad}"
        confianza_alta = True
        nivel_match = "capacidad"
        
    # 3. Prioridad Baja: Fallback a similitud de texto
    else:
        texto_norm = normalizar_texto(nombre_producto)
        # Limpiamos palabras muy comunes para no ensuciar el bag-of-words
        palabras_limpias = [w for w in texto_norm.split() if w not in ("nevera", "refrigerador", "de", "con", "litros", "lts")]
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
# Revisión asistida para casos de baja confianza (fuzzy matching)
# ----------------------------------------------------------------------------

def sugerir_posibles_duplicados(productos: list[dict], umbral: int = 85) -> list[dict]:
    """
    Compara productos de baja confianza dentro de la misma marca y tipo.
    """
    sugerencias = []
    baja_confianza = [p for p in productos if not p.get("confianza_alta", True)]

    # Agrupar por marca Y tipo para optimizar y no comparar neveras con lavadoras
    por_grupo: dict[str, list[dict]] = {}
    for p in baja_confianza:
        llave_grupo = f"{p['marca_normalizada']}_{p['tipo_producto']}"
        por_grupo.setdefault(llave_grupo, []).append(p)

    for llave_grupo, grupo in por_grupo.items():
        for i in range(len(grupo)):
            for j in range(i + 1, len(grupo)):
                a, b = grupo[i], grupo[j]
                
                if a["canonical_id"] == b["canonical_id"]:
                    continue
                if a.get("retailer") == b.get("retailer"):
                    continue 
                
                score = fuzz.token_sort_ratio(
                    normalizar_texto(a["producto"]), 
                    normalizar_texto(b["producto"])
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
