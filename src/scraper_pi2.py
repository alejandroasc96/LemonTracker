import os
import time
from bs4 import BeautifulSoup

# Intentamos importar curl_cffi de forma segura
try:
    from curl_cffi import requests
except ImportError:
    requests = None

def obtener_html_con_curl_cffi():
    if requests is None:
        print("❌ Error: La librería 'curl_cffi' no está instalada o no es compatible con la arquitectura de esta Pi.")
        return None

    print("📡 Iniciando petición ligera con curl_cffi (Modo supervivencia sin entorno gráfico)...")
    url = "https://steamdb.info/upcoming/free/"
    
    # Headers para mimetizarnos junto con la suplantación de TLS/HTTP2
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        # 'impersonate="chrome"' imita el handshake TLS exacto de Chrome para saltar el antibot básico de Cloudflare
        response = requests.get(url, headers=headers, impersonate="chrome", timeout=30)
        
        if response.status_code == 200:
            print("✅ HTML obtenido con éxito.")
            return response.text
        else:
            print(f"❌ Error: Código de estado {response.status_code} (Cloudflare podría haber bloqueado la petición)")
            return None
            
    except Exception as e:
        print(f"❌ Error crítico en curl_cffi: {e}")
        return None

def extraer_juegos(html_content):
    if not html_content:
        print("No hay HTML para procesar. Devolviendo listas vacías.")
        return {"current": [], "upcoming": []}

    print("Analizando el código fuente con BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    current_games = []
    upcoming_games = []

    # =========================================================
    # JUEGOS ACTUALES
    # =========================================================
    panels = soup.select('div.panel-sale.app-history-row')
    for panel in panels:
        game_id = panel.get('data-appid') or '0'
        sub_id = panel.get('data-subid') or '0'
        
        if game_id == "730" and sub_id == "14":
            continue
            
        title_elem = panel.select_one('.panel-sale-name a')
        if not title_elem:
            continue
            
        title = title_elem.text.strip()
        if "steamdb.info" in title.lower():
            continue

        if game_id != "0":
            game_url = f"https://store.steampowered.com/app/{game_id}/"
            db_id = game_id
        else:
            game_url = f"https://store.steampowered.com/sub/{sub_id}/"
            db_id = f"sub_{sub_id}"

        img_elem = panel.select_one('img.sale-image')
        image_url = img_elem.get('src') if img_elem else "N/A"

        cat_elem = panel.select_one('div.cat')
        cat_text = cat_elem.text.strip() if cat_elem else ""
        promo_type = "Keep Free" if "Keep" in cat_text.lower() else "Free to Play"

        end_date = "N/A"
        time_divs = panel.select('div.panel-sale-time')
        for div in time_divs:
            if "Expires:" in div.text:
                rel_time = div.select_one('relative-time')
                if rel_time:
                    end_date = rel_time.get('datetime') or rel_time.text.strip()

        current_games.append({
            "id": db_id, "title": title, "url": game_url, 
            "image_url": image_url, "promo_type": promo_type, "end_date": end_date
        })

    # =========================================================
    # FUTUROS JUEGOS
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
            db_id = f"{id_type}_{item_id}"
        else:
            db_id = href
            game_url = f"https://steamdb.info{href}"

        upcoming_games.append({
            "id": db_id, "title": game_title.strip(), 
            "estimated_date": estimated_date.strip(), "url": game_url
        })

    return {"current": current_games, "upcoming": upcoming_games}

if __name__ == "__main__":
    html = obtener_html_con_curl_cffi()
    juegos = extraer_juegos(html)
    
    print(f"Encontrados {len(juegos['current'])} juegos actuales y {len(juegos['upcoming'])} futuros.")