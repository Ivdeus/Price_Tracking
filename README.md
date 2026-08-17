### Scrapper exito:
The idea is automate 

Extracción: script Python que golpea el endpoint público de VTEX (/api/catalog_system/pub/products/search/...), pagina resultados y saca producto, marca, precio actual, precio de lista y specs (variaciones tipo capacidad, color, tipo).
Almacenamiento: SQLite local (un solo archivo .db, cero costo, cero servidor). Cada corrida inserta una fila por SKU con la fecha del día → así se acumula el histórico automáticamente.
Automatización diaria gratis: GitHub Actions con un cron job (gratis en repos públicos, y con minutos gratis en privados) que corre el script todos los días y commitea la base actualizada. Alternativa 100% local: Task Scheduler de Windows.
Visualización con filtros: app en Streamlit (gratis, corre local o se despliega gratis en Streamlit Community Cloud) que lee el SQLite y te deja filtrar por marca, producto y características, con la gráfica de evolución de precio.

Cómo funciona el paquete:
scraper.py — pega directo a la API JSON de VTEX (no HTML), pagina la categoría, y guarda en precios_exito.db (SQLite) una fila por SKU con la fecha del día. Corriéndolo a diario se va acumulando el histórico.
dashboard.py — app Streamlit que lee el SQLite y arma filtros automáticos por marca, producto, y cualquier característica que traiga el producto (capacidad, color, etc.), más la gráfica de evolución de precio.
.github_workflow_price_tracker.yml — para que corra solo, todos los días, gratis, sin tener el PC prendido (GitHub Actions).
README.md — instrucciones y qué hacer si el endpoint no responde tal cual (Éxito a veces migra a la Intelligent Search API nueva de VTEX; dejé la ruta para diagnosticarlo con DevTools).
