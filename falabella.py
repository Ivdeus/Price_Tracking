"""
Scraper de Falabella — NO IMPLEMENTADO TODAVÍA.
--------------------------------------------------
Falabella usa una plataforma de e-commerce propia (no VTEX, no Hybris), y
es conocida por tener protección anti-bot (tipo Akamai/PerimeterX) en su
tráfico. Esto significa dos cosas importantes:

1. Es poco probable que haya una API JSON pública y abierta como la de
   VTEX — probablemente necesites simular un navegador real (Playwright)
   con headers/comportamiento humano para no ser bloqueado.
2. Incluso con Playwright, el acceso puede ser inestable: la protección
   anti-bot puede empezar a bloquear la IP si el scraper corre muy seguido
   (ej. todos los días desde el mismo runner de GitHub Actions), lo cual
   rompe justo el caso de uso que quieres (tracking diario confiable).

CÓMO VERIFICAR SI HAY UNA RUTA MÁS FÁCIL:
1. Abre https://www.falabella.com.co/falabella-co/category/CATG32130/Refrigeracion
   en Chrome, F12 -> Network -> filtra "Fetch/XHR", recarga la página.
2. Busca peticiones que devuelvan JSON con productos y precios (usualmente
   algo con "search" o "listing" en el path).
3. Si encuentras una, prueba pegarle esa misma URL con `requests` desde
   Python (fuera del navegador) — si responde igual, hay chance de usarla
   directamente. Si responde con error/challenge, es que está protegida
   y se necesitaría Playwright sí o sí.

Mi recomendación honesta: empieza con Éxito y Jumbo (si se confirma VTEX),
que dan una API estable y gratis de verdad. Agrega Alkosto y Falabella
después, y para Falabella en particular, considera que puede requerir más
mantenimiento del que un tracker "gratis y que corra solo" idealmente
necesita.

No genero un scraper que aparente funcionar sin haber verificado una ruta
real de acceso a los datos.
"""

RETAILER = "Falabella"


def scrape() -> list[dict]:
    raise NotImplementedError(
        "Falabella probablemente requiere Playwright por su protección "
        "anti-bot. Revisa las instrucciones en este archivo antes de implementar."
    )
