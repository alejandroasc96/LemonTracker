from bs4 import BeautifulSoup
from typing import List, Dict, Any
from scrapers.base import BaseScraper

class SteamScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="SteamScraper")
        self.url = "https://steamdb.info/upcoming/free/"

    def clasificar_promo(self, panel_text: str) -> str:
        """Determina con precisión el tipo de promoción analizando el texto indexado."""
        text_lower = panel_text.lower()
        if "keep" in text_lower:
            return "Keep"      # Gratis para siempre
        if "weekend" in text_lower:
            return "Weekend"   # Fin de semana gratuito
        return "F2P"           # Free to play / Otro

    def extraer(self) -> List[Dict[str, Any]]:
        html = self.fetch_html(self.url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        juegos_procesados = []

        # =========================================================
        # 1. JUEGOS ACTUALES (Promociones Activas)
        # =========================================================
        panels = soup.select('div.panel-sale.app-history-row')
        for panel in panels:
            game_id = panel.get('data-appid') or '0'
            sub_id = panel.get('data-subid') or '0'
            
            # Omitir CS2 / Herramientas de SteamDB redundantes
            if game_id == "730" and sub_id == "14":
                continue
                
            title_elem = panel.select_one('.panel-sale-name a')
            if not title_elem:
                continue
                
            title = title_elem.text.strip()
            if "steamdb.info" in title.lower():
                continue

            # Construcción de IDs únicos y URLs limpias
            if game_id != "0":
                game_url = f"https://store.steampowered.com/app/{game_id}/"
                db_id = f"steam_app_{game_id}"
            else:
                game_url = f"https://store.steampowered.com/sub/{sub_id}/"
                db_id = f"steam_sub_{sub_id}"

            img_elem = panel.select_one('img.sale-image')
            image_url = img_elem.get('src') if img_elem else None

            # CORRECCIÓN DE DETECCIÓN: Analizamos todo el texto del bloque del juego
            promo_type = self.clasificar_promo(panel.text)

            # Extraer fecha de expiración
            end_date = None
            time_divs = panel.select('div.panel-sale-time')
            for div in time_divs:
                if "Expires:" in div.text:
                    rel_time = div.select_one('relative-time')
                    if rel_time:
                        end_date = rel_time.get('datetime') or rel_time.text.strip()

            juegos_procesados.append({
                "id": db_id,
                "platform": "steam",
                "title": title,
                "url": game_url,
                "image_url": image_url,
                "promo_type": promo_type,
                "status": "current",
                "end_date": end_date,
                "estimated_date": None
            })

        # =========================================================
        # 2. FUTUROS JUEGOS (Próximas Promociones)
        # =========================================================
        upcoming_links = soup.select('ul.upcoming-list li a')
        for item in upcoming_links:
            full_text = item.text.strip()
            href = item.get('href') or ''
            
            if ":" in full_text:
                estimated_date, game_title = full_text.split(":", 1)
            else:
                estimated_date, game_title = "Por confirmar", full_text

            url_parts = [p for p in href.split('/') if p]
            if len(url_parts) >= 2:
                id_type, item_id = url_parts[0], url_parts[1]
                game_url = f"https://store.steampowered.com/{id_type}/{item_id}/"
                db_id = f"steam_{id_type}_{item_id}"
            else:
                db_id = f"steam_unk_{href.replace('/', '_')}"
                game_url = f"https://steamdb.info{href}"

            juegos_procesados.append({
                "id": db_id,
                "platform": "steam",
                "title": game_title.strip(),
                "url": game_url,
                "image_url": None,
                "promo_type": "Keep",  # La mayoría de los listados a futuro apuntan a Keep Free
                "status": "upcoming",
                "end_date": None,
                "estimated_date": estimated_date.strip()
            })

        return juegos_procesados