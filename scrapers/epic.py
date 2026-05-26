import json
from typing import List, Dict, Any
from scrapers.base import BaseScraper

class EpicScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="EpicScraper")
        # Endpoint estático oficial e inmune a problemas de DNS locales
        self.url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions?locale=es-ES&country=ES&allowCountries=ES"

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
                price_info = item.get("price", {}).get("totalPrice", {})
                promotions = item.get("promotions")
                
                if not promotions:
                    continue

                promo_activa = promotions.get("promotionalOffers", [])
                promo_futura = promotions.get("upcomingPromotionalOffers", [])

                status = None
                end_date = None
                estimated_date = None

                # 1. VALIDAR PROMOCIONES ACTIVAS (Juegos gratis HOY)
                if promo_activa and len(promo_activa) > 0:
                    offers = promo_activa[0].get("promotionalOffers", [])
                    for offer in offers:
                        discount_pct = offer.get("discountSetting", {}).get("discountPercent")
                        # CORRECCIÓN CRÍTICA: Es gratis si el descuento es 100%, 0% (tarifa plana), o si el precio final es 0€
                        if discount_pct in [0, 100] or price_info.get("discountPrice") == 0:
                            status = "current"
                            end_date = offer.get("endDate")
                            break

                # 2. VALIDAR PROMOCIONES FUTURAS (Próximo jueves / Cajas Misteriosas)
                if not status and promo_futura and len(promo_futura) > 0:
                    offers = promo_futura[0].get("upcomingPromotionalOffers", []) or promo_futura[0].get("promotionalOffers", [])
                    for offer in offers:
                        discount_pct = offer.get("discountSetting", {}).get("discountPercent")
                        if discount_pct in [0, 100]:
                            status = "upcoming"
                            estimated_date = offer.get("startDate")
                            break

                # Si no es una promoción gratuita válida, la ignoramos completamente
                if not status:
                    continue

                # Construir la URL de la tienda
                slug = item.get("productSlug") or item.get("urlSlug")
                game_url = f"https://store.epicgames.com/es-ES/p/{slug}" if slug else "https://store.epicgames.com/"

                # Extraer la mejor imagen disponible (añadimos VaultClosed para las cajas misteriosas)
                image_url = None
                for img in item.get("keyImages", []):
                    if img.get("type") in ["Thumbnail", "DieselStoreFrontWide", "VaultClosed"]:
                        image_url = img.get("url")
                        break

                juegos_procesados.append({
                    "id": f"epic_{item.get('id')}",
                    "platform": "epic",
                    "title": title,
                    "url": game_url,
                    "image_url": image_url,
                    "promo_type": "Keep",  # Las promociones semanales de Epic siempre son para conservar
                    "status": status,
                    "end_date": end_date,
                    "estimated_date": estimated_date
                })

        except Exception as e:
            self.logger.error(f"❌ Error procesando el JSON de Epic: {e}")

        return juegos_procesados