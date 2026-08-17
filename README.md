Tracker de precios - Éxito (Refrigeración)

Guarda el histórico diario de precios de la categoría de refrigeración de exito.com (neveras, nevecones, minibares, congeladores) usando la API pública de VTEX, y lo muestra en un dashboard filtrable.

Cómo probarlo
bash
pip install requests streamlit pandas plotly
python scraper.py          # crea/actualiza precios_exito.db con el snapshot de hoy
streamlit run dashboard.py # abre el dashboard en el navegador

La primera corrida solo va a mostrar un punto por producto (no hay "evolución" todavía). El histórico se construye corriendo scraper.py todos los días — para eso está el workflow de GitHub Actions.

Si el endpoint no responde como se espera

Puede que Éxito exija algún header extra, un sc (sales channel) en la query, o que la ruta exacta de categoría cambie. Para diagnosticar:

Abre https://www.exito.com/electrodomesticos/refrigeracion en el navegador con las DevTools abiertas (pestaña Network, filtra por "Fetch/XHR").
Busca una llamada a algo como .../api/catalog_system/pub/products/search/... o .../api/io/_v/api/intelligent-search/product_search/... (la versión nueva de VTEX, si la vieja no funciona).
Copia esa URL exacta (con sus query params) y reemplázala en BASE_URL dentro de scraper.py.

Si Éxito migró a la Intelligent Search API, la estructura del JSON cambia un poco (los productos vienen bajo una clave "products"), avísame y ajusto el parser.

Automatizar (gratis, sin dejar tu PC prendido)
Sube esta carpeta a un repo de GitHub (puede ser privado).
Copia .github_workflow_price_tracker.yml a .github/workflows/price_tracker.yml.
Listo — correrá todos los días a las 6am hora Colombia y commiteará precios_exito.db actualizado.
Para ver el dashboard con datos frescos: git pull y streamlit run dashboard.py, o despliega el dashboard gratis en https://streamlit.io/cloud apuntando al repo.
Estructura de datos

Tabla price_history en SQLite, una fila por SKU por día:

columna	qué es
fecha	fecha del snapshot
sku_id / product_id	identificadores VTEX
producto / marca	nombre y marca
precio / precio_lista	precio actual y precio "antes de descuento"
disponible	cantidad en stock
especificaciones	JSON con capacidad, color, etc. (varía por producto)

Extracción: script Python que golpea el endpoint público de VTEX (/api/catalog_system/pub/products/search/...), pagina resultados y saca producto, marca, precio actual, precio de lista y specs (variaciones tipo capacidad, color, tipo).
Almacenamiento: SQLite local (un solo archivo .db, cero costo, cero servidor). Cada corrida inserta una fila por SKU con la fecha del día → así se acumula el histórico automáticamente.
Automatización diaria gratis: GitHub Actions con un cron job (gratis en repos públicos, y con minutos gratis en privados) que corre el script todos los días y commitea la base actualizada. Alternativa 100% local: Task Scheduler de Windows.
Visualización con filtros: app en Streamlit (gratis, corre local o se despliega gratis en Streamlit Community Cloud) que lee el SQLite y te deja filtrar por marca, producto y características, con la gráfica de evolución de precio.

Cómo funciona el paquete:
scraper.py — pega directo a la API JSON de VTEX (no HTML), pagina la categoría, y guarda en precios_exito.db (SQLite) una fila por SKU con la fecha del día. Corriéndolo a diario se va acumulando el histórico.
dashboard.py — app Streamlit que lee el SQLite y arma filtros automáticos por marca, producto, y cualquier característica que traiga el producto (capacidad, color, etc.), más la gráfica de evolución de precio.
.github_workflow_price_tracker.yml — para que corra solo, todos los días, gratis, sin tener el PC prendido (GitHub Actions).
README.md — instrucciones y qué hacer si el endpoint no responde tal cual (Éxito a veces migra a la Intelligent Search API nueva de VTEX; dejé la ruta para diagnosticarlo con DevTools).

