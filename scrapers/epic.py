import json
from typing import List, Dict, Any
from scrapers.base import BaseScraper

class EpicScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="EpicScraper")
        # API interna de ofertas y juegos gratuitos de Epic
        self.url = "https://store-site-backend-eats.ak.epicgames.com/freeGamesPromotions?locale=es-ES&country=ES&allowCountries=ES"

    def extraer(self) -> List[Dict[str, Any]]:
        raw_response = self.fetch_html(self.url)
        if not raw_response:
            return []

        juegos_procesados = []
        try:
            data = json.loads(raw_response)
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
            
            for item in elements:
                title = item.get("title")
                # Si el precio original es 0 de forma permanente, suele ser un F2P genérico, 
                # nosotros buscamos promociones temporales del 100% de descuento.
                price_info = item.get("price", {}).get("totalPrice", {})
                promotions = item.get("promotions")
                
                if not promotions:
                    continue

                # Identificar si la promoción está activa hoy o es futura
                promo_activa = promotions.get("promotionalOffers", [])
                promo_futura = promotions.get("upcomingPromotionalOffers", [])
                
                status = None
                end_date = None
                estimated_date = None
                
                if promo_activa:
                    offers = promo_activa[0].get("promotionalOffers", [])
                    for offer in offers:
                        if offer.get("discountSetting", {}).get("discountPercentage") == 0:
                            status = "current"
                            end_date = offer.get("endDate")
                            break
                            
                if not status and promo_futura:
                    offers = promo_futura[0].get("promotionalOffers", [])
                    for offer in offers:
                        if offer.get("discountSetting", {}).get("discountPercentage") == 0:
                            status = "upcoming"
                            estimated_date = offer.get("startDate")
                            break

                # Si no encontramos ninguna promoción válida de coste 0%, ignoramos el juego
                if not status:
                    continue

                # Construcción de la URL de la tienda
                slug = item.get("productSlug") or item.get("urlSlug")
                game_url = f"https://store.epicgames.com/es-ES/p/{slug}" if slug else "https://store.epicgames.com/"

                # Extraer miniatura (buscamos la imagen tipo Thumbnail o DieselStoreFrontWide)
                image_url = None
                for img in item.get("keyImages", []):
                    if img.get("type") in ["Thumbnail", "DieselStoreFrontWide"]:
                        image_url = img.get("url")
                        break

                juegos_procesados.append({
                    "id": f"epic_{item.get('id')}",
                    "platform": "epic",
                    "title": title,
                    "url": game_url,
                    "image_url": image_url,
                    "promo_type": "Keep",  # Epic siempre regala en modalidad "Para siempre"
                    "status": status,
                    "end_date": end_date,
                    "estimated_date": estimated_date
                })

        except Exception as e:
            self.logger.error(f"❌ Error procesando el JSON de Epic: {e}")

        return juegos_procesados