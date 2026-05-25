import sqlite3
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions
import time

DB_PATH = "data/games.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS current_games (
            id TEXT PRIMARY KEY, title TEXT, url TEXT, image_url TEXT, promo_type TEXT, end_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upcoming_games (
            id TEXT PRIMARY KEY, title TEXT, estimated_date TEXT, url TEXT
        )
    ''')
    conn.commit()
    conn.close()

def obtener_html_bruto():
    print("Abriendo navegador optimizado para bajo consumo de RAM...")
    options = ChromiumOptions()
    options.headless(False) # Obligatorio Falso para Cloudflare
    
    # 🚀 OPTIMIZACIONES EXTREMAS PARA RASPBERRY PI ZERO (AHORRO DE RAM)
    options.set_argument('--disable-gpu')                # Desactiva la gráfica virtual
    options.set_argument('--no-sandbox')                 # Evita restricciones de permisos en Linux
    options.set_argument('--disable-dev-shm-usage')      # Fuerza a Chrome a usar la RAM normal, no la compartida corta
    options.set_argument('--blink-settings=imagesEnabled=false') # ❌ NO CARGAR IMÁGENES (Ahorra un 50% de RAM)
    options.set_argument('--mute-audio')                 # Desactiva el sistema de sonido
    options.set_argument('--disable-extensions')         # No carga extensiones de Chrome
    options.set_argument('--disable-plugins')            # No carga plugins (pdf, flash, etc)
    options.set_argument('--memory-pressure-thresholds=1') # Fuerza la liberación de RAM agresiva
    
    page = ChromiumPage(options)
    html_bruto = ""
    
    try:
        page.get("https://steamdb.info/upcoming/free/")
        print(f"Página cargada: '{page.title}'. Esperando renderizado...")
        time.sleep(6) 
        html_bruto = page.html
    except Exception as e:
        print(f"Error al descargar el HTML: {e}")
    finally:
        page.quit()
        
    return html_bruto

def procesar_html_con_soup(html_content):
    if not html_content:
        print("El HTML está vacío. No se puede procesar.")
        return

    print("Analizando el código fuente con BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM current_games")
    cursor.execute("DELETE FROM upcoming_games")

    # =========================================================
    # SECCIÓN 1: JUEGOS ACTUALES (SOUP SOBRE HTML EN BRUTO)
    # =========================================================
    panels = soup.select('div.panel-sale.app-history-row')
    print(f"Soup ha detectado {len(panels)} paneles actuales en el HTML.")

    for panel in panels:
        game_id = panel.get('data-appid') or '0'
        sub_id = panel.get('data-subid') or '0'
        
        if game_id == "730" and sub_id == "14":
            continue # Filtro de la plantilla de SteamDB
            
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

        cursor.execute('''
            INSERT OR REPLACE INTO current_games (id, title, url, image_url, promo_type, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (db_id, title, game_url, image_url, promo_type, end_date))

    # =========================================================
    # SECCIÓN 2: FUTUROS JUEGOS (SOUP SOBRE HTML EN BRUTO)
    # =========================================================
    upcoming_links = soup.select('ul.upcoming-list li a')
    print(f"Soup ha detectado {len(upcoming_links)} futuros juegos en el HTML.")

    for item in upcoming_links:
        full_text = item.text.strip()
        href = item.get('href') or ''
        
        if ":" in full_text:
            estimated_date, game_title = full_text.split(":", 1)
            estimated_date = estimated_date.strip()
            game_title = game_title.strip()
        else:
            estimated_date = "Por confirmar"
            game_title = full_text

        url_parts = [p for p in href.split('/') if p]
        if len(url_parts) >= 2:
            id_type = url_parts[0]
            item_id = url_parts[1]
            game_url = f"https://store.steampowered.com/{id_type}/{item_id}/"
            db_id = f"{id_type}_{item_id}"
        else:
            db_id = href
            game_url = f"https://steamdb.info{href}"

        cursor.execute('''
            INSERT OR REPLACE INTO upcoming_games (id, title, estimated_date, url)
            VALUES (?, ?, ?, ?)
        ''', (db_id, game_title, estimated_date, game_url))

    conn.commit()
    conn.close()
    print("¡Base de datos actualizada con éxito mediante BeautifulSoup!")

if __name__ == "__main__":
    init_db()
    html_obtenido = obtener_html_bruto()
    procesar_html_con_soup(html_obtenido)