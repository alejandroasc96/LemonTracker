import json
from typing import List, Dict, Any
from scrapers.base import BaseScraper

class GogScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="GogScraper")
        # API de catálogo filtrando por juegos gratuitos de manera ligera
        self.url = "https://catalog.gog.com/v1/catalog?limit=20&order=desc:trending&price=eq:0"

    def extraer(self) -> List[Dict[str, Any]]:
        raw_response = self.fetch_html(self.url)
        if not raw_response:
            return []

        juegos_procesados = []
        try:
            data = json.loads(raw_response)
            products = data.get("products", [])
            
            for product in products:
                title = product.get("title")
                slug = product.get("slug")
                product_id = product.get("id")
                
                if not title or not product_id:
                    continue

                game_url = f"https://www.gog.com/game/{slug}" if slug else "https://www.gog.com/"
                
                # Extraer imagen principal de GOG
                # La API suele entregar un template con '{formatter}', lo limpiamos para obtener una resolución ligera
                raw_img = product.get("coverHorizontal") or product.get("coverVertical")
                image_url = raw_img.replace("{formatter}", "product_card_v2_mobile_slider_2x") if raw_img else None

                juegos_procesados.append({
                    "id": f"gog_{product_id}",
                    "platform": "gog",
                    "title": title,
                    "url": game_url,
                    "image_url": image_url,
                    "promo_type": "Keep",  # GOG regala copias DRM-Free para siempre
                    "status": "current",   # Su catálogo online muestra lo activo inmediatamente
                    "end_date": None,      # Su API de catálogo general no expone la fecha exacta de fin de forma directa
                    "estimated_date": None
                })

        except Exception as e:
            self.logger.error(f"❌ Error procesando el JSON de GOG: {e}")

        return juegos_procesados