import json
from typing import List, Dict, Any
from scrapers.base import BaseScraper

class GogScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="GogScraper")
        # Optimizamos el parámetro de la URL usando un rango estricto de 0 a 0
        self.url = "https://catalog.gog.com/v1/catalog?limit=20&order=desc:trending&price=between:0,0"

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

                # --- CONTROL RIGUROSO DE COSTE CERO (FILTRO ANTI-DESCUENTOS) ---
                price_info = product.get("price", {})
                is_free_flag = price_info.get("isFree", False)
                
                # Extraemos el valor del precio final (puede venir como 'finalAmount' o 'amount')
                final_amount = price_info.get("finalAmount") or price_info.get("amount") or "1.00"
                
                try:
                    is_price_zero = float(final_amount) == 0.0
                except (ValueError, TypeError):
                    is_price_zero = str(final_amount) in ["0.00", "0", "0.0"]

                # Si el backend de GOG coló un juego con descuento (no es gratis), lo descartamos inmediatamente
                if not (is_free_flag or is_price_zero):
                    continue
                # --------------------------------------------------------------

                game_url = f"https://www.gog.com/game/{slug}" if slug else "https://www.gog.com/"
                
                # Extraer imagen principal de GOG
                raw_img = product.get("coverHorizontal") or product.get("coverVertical")
                image_url = raw_img.replace("{formatter}", "product_card_v2_mobile_slider_2x") if raw_img else None

                juegos_procesados.append({
                    "id": f"gog_{product_id}",
                    "platform": "gog",
                    "title": title,
                    "url": game_url,
                    "image_url": image_url,
                    "promo_type": "Keep",  # GOG siempre regala licencias completas para siempre
                    "status": "current",   # El catálogo público muestra promociones activas al instante
                    "end_date": None,      # La API de catálogo general no expone la fecha de expiración directamente
                    "estimated_date": None
                })

        except Exception as e:
            self.logger.error(f"❌ Error procesando el JSON de GOG: {e}")

        return juegos_procesados