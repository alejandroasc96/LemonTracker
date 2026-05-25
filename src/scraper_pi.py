import os
import time
import platform
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

def obtener_html_con_navegador():
    print("Iniciando Chromium...")
    options = ChromiumOptions()
    
    # Detectar el sistema operativo
    sistema = platform.system()
    
    if sistema == "Windows":
        print("💻 Entorno Windows detectado. Usando configuración estándar.")
        options.headless(False) # Ponlo en True si no quieres ver cómo se abre en tu PC
        # En Windows no necesitamos banderas extremas de supervivencia
        options.set_argument('--mute-audio')
        
    else:
        print("🍓 Entorno Linux/Raspberry detectado. Modo supervivencia activado.")
        options.headless(True)
        # Optimizaciones EXTREMAS para la Pi Zero W
        options.set_argument('--disable-gpu')
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-dev-shm-usage')
        options.set_argument('--single-process')
        options.set_argument('--disable-background-networking')
        options.set_argument('--disable-extensions')
        options.set_argument('--mute-audio')
        options.set_argument('--blink-settings=imagesEnabled=false')
        options.set_argument('--disk-cache-dir=/dev/shm/chromium-cache')

    try:
        page = ChromiumPage(options)
        url = "https://steamdb.info/upcoming/free/"
        
        page.get(url, timeout=30)
        print(f"Página cargada. Esperando renderizado antibot de Cloudflare...")
        
        # En Windows puede ser más rápido, en la Pi necesita más tiempo
        tiempo_espera = 5 if sistema == "Windows" else 15
        time.sleep(tiempo_espera) 
        
        html_bruto = page.html
        page.quit()
        return html_bruto
    except Exception as e:
        print(f"Error crítico en Chromium: {e}")
        try:
            page.quit()
        except:
            pass
        return None

def extraer_juegos(html_content):
    if not html_content:
        print("No hay HTML para procesar. Devolviendo listas vacías.")
        # FIX: Las llaves ahora coinciden con el final de la función
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
    html = obtener_html_con_navegador()
    juegos = extraer_juegos(html)
    
    print(f"Encontrados {len(juegos['current'])} juegos actuales y {len(juegos['upcoming'])} futuros.")