"""
Scraper de Alkosto — NO IMPLEMENTADO TODAVÍA.
------------------------------------------------
Alkosto NO corre sobre VTEX. Las URLs de categoría (/c/BI_163_ALKOS) y los
parámetros de búsqueda (q=:relevance:brand:X) son la firma típica de
SAP Commerce Cloud (antes "Hybris"). Esa plataforma sí tiene una API REST
(la "OCC API", normalmente en /rest/v2/...), pero casi siempre requiere
autenticación OAuth (client_id/client_secret) que no es pública — no es
tan simple como el endpoint abierto de VTEX que usamos para Éxito.

OPCIONES REALES para conseguir estos datos gratis:

1. Buscar si Alkosto expone su OCC API sin autenticación para catálogo
   público (algunos retailers en Hybris sí lo hacen para su propio
   frontend). Para verificarlo:
   - Abre https://www.alkosto.com/electrodomesticos/refrigeracion/c/BI_163_ALKOS
     en Chrome, F12 -> Network -> filtra "Fetch/XHR", recarga la página.
   - Busca peticiones a algo como /rest/v2/alkosto/products/search o similar.
   - Si encuentras una que devuelve JSON con precios SIN necesitar login,
     cópiame la URL completa y adapto este scraper a esa API.

2. Si no hay API abierta: scraping del HTML/JS renderizado con Playwright
   o Selenium (herramienta gratuita, pero mucho más lenta y frágil que una
   API — cualquier cambio de diseño en la web rompe el scraper). Es la
   opción de respaldo si la opción 1 no aparece.

3. Revisar robots.txt y términos de uso de Alkosto antes de scrapear el
   HTML directamente — un endpoint de API pública pensado para el propio
   frontend es más defendible que simular un navegador para extraer datos
   a gran escala.

No genero un scraper "de mentiras" que parezca funcionar pero en realidad
no traiga datos reales — prefiero dejarte esto documentado para que
verifiques la opción 1 primero (5 minutos con DevTools) antes de invertir
tiempo en Playwright.
"""

RETAILER = "Alkosto"


def scrape() -> list[dict]:
    raise NotImplementedError(
        "Alkosto no está confirmado en VTEX. Revisa las instrucciones en este "
        "archivo (DevTools -> Network -> Fetch/XHR) antes de implementar."
    )
