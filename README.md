# Tracker de precios - Refrigeración (multi-tienda)

Guarda el histórico diario de precios de refrigeración en varios retailers
colombianos, detecta cuándo el mismo producto aparece en más de una tienda
(aunque cada una lo nombre distinto), y lo muestra en un dashboard filtrable.

## Estado por tienda

| Tienda | Estado |
|---|---|
| Éxito | ✅ Funcionando (`retailers/exito.py`) |
| Jumbo Colombia | ✅ Funcionando (`retailers/jumbo.py`) — VTEX clásico, confirmado |
| Alkosto | 🔴 No implementado — no es VTEX, ver instrucciones en `retailers/alkosto.py` |
| Falabella | 🔴 No implementado — anti-bot conocido, ver instrucciones en `retailers/falabella.py` |

## Cómo probarlo

```bash
pip install -r requirements.txt
python run_all.py           # corre todos los scrapers disponibles, guarda en precios_multitienda.db
streamlit run dashboard.py  # abre el dashboard
```

Los retailers no implementados (Alkosto, Falabella) se saltan automáticamente
con un aviso en consola — no rompen la corrida de los demás.

## Cómo funciona el matching entre tiendas

Cada producto se pasa por `normalizacion.py`, que extrae marca, tipo de
producto (nevera/nevecón/congelador/minibar/etc.) y capacidad en litros
usando reglas y expresiones regulares. Con esos 3 atributos arma una
"llave canónica" — si dos productos de tiendas distintas generan la misma
llave, se tratan como el mismo producto en la gráfica (`canonical_id`).

Cuando no se puede detectar la capacidad (texto raro, producto atípico),
el match cae a "baja confianza" (`confianza_alta = 0`) y el dashboard lo
marca así — puedes ocultarlos con el checkbox del sidebar. Además,
`run_all.py` genera `revisar_posibles_duplicados.csv` con sugerencias de
posibles duplicados entre tiendas (via fuzzy matching) para que confirmes
manualmente en vez de que el sistema fusione productos sin que tú lo veas.

**Esto es deliberadamente conservador.** Un matching 100% automático y
perfecto no es realista de forma gratuita — prefiero que productos
distintos NO se mezclen por error, a costa de que algunos matches
legítimos queden en la categoría "revisar manualmente".

## Agregar Jumbo de verdad (verificar VTEX)

1. Abre `https://www.jumbocolombia.com/co/electrodomesticos/refrigeracion`
   en Chrome, F12 → Network → filtra "Fetch/XHR" → recarga la página.
2. Busca una petición a `.../api/catalog_system/pub/products/search/...`
   (o la versión Intelligent Search de VTEX).
3. Si aparece, confirma el dominio exacto y ajusta `BASE_URL` en
   `retailers/jumbo.py`. Si no aparece, Jumbo no está en VTEX — avísame
   qué encontraste para adaptar el scraper.

## Agregar Alkosto / Falabella

Lee las instrucciones detalladas dentro de `retailers/alkosto.py` y
`retailers/falabella.py` — ambos necesitan que verifiques con DevTools si
existe una API JSON accesible antes de intentar scrapear el HTML/JS
directamente (que requeriría Playwright y sería más frágil).

## Automatizar (gratis)

1. Sube esta carpeta a un repo de GitHub.
2. Copia `.github_workflow_price_tracker.yml` a `.github/workflows/price_tracker.yml`.
3. En Settings → Actions → General, activa "Read and write permissions"
   para que el workflow pueda commitear la base de datos actualizada.
4. Listo — corre todos los días a las 6am hora Colombia.

## Estructura de datos

Tabla `price_history` en `precios_multitienda.db`, una fila por SKU por día:

| columna | qué es |
|---|---|
| retailer | Exito, Jumbo, Alkosto, Falabella |
| sku_id | identificador único (prefijado con el retailer) |
| producto / marca | como los reporta cada tienda (sin normalizar) |
| canonical_id | producto normalizado — úsalo para agrupar entre tiendas |
| marca_normalizada / tipo_producto / capacidad_litros | atributos extraídos |
| confianza_alta | 1 si se detectó capacidad exacta, 0 si el match es aproximado |
| precio / precio_lista / disponible | oferta del día |
