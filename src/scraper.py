import os
import sqlite3
import time
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

DB_PATH = "data/games.db"

def init_db():
    # 🔥 Asegura que GitHub Actions no falle si la carpeta 'data' no se ha creado aún
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
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

def obtener_html_con_navegador():
    """Descarga el HTML usando DrissionPage bajo pantalla virtual para saltarse el 403."""
    print("Abriendo navegador optimizado (DrissionPage) para evadir Cloudflare...")
    options = ChromiumOptions()
    options.headless(False)  # Obligatorio Falso para que Xvfb emule la pantalla humana
    
    # Optimizaciones de bajo consumo de recursos para GitHub Actions
    options.set_argument('--disable-gpu')
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-dev-shm-usage')
    options.set_argument('--blink-settings=imagesEnabled=false')  # No carga imágenes para ahorrar RAM
    options.set_argument('--mute-audio')
    options.set_argument('--disable-extensions')
    
    try:
        page = ChromiumPage(options)
        url = "https://steamdb.info/upcoming/free/"
        page.get(url)
        
        print(f"Página cargada: '{page.title}'. Esperando renderizado antibot...")
        time.sleep(8)  # Tiempo prudencial para superar el reto visual de Cloudflare
        
        html_bruto = page.html
        page.quit()
        return html_bruto
    except Exception as e:
        print(f"Error crítico al conectar con la web mediante navegador emulado: {e}")
        return None

def procesar_html_con_soup(html_content):
    if not html_content:
        print("El HTML está vacío o no se pudo descargar. Cancelando procesamiento.")
        return

    print("Analizando el código fuente con BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM current_games")
    cursor.execute("DELETE FROM upcoming_games")

    # =========================================================
    # TU SECCIÓN 1: JUEGOS ACTUALES (Mantenida intacta)
    # =========================================================
    panels = soup.select('div.panel-sale.app-history-row')
    print(f"Soup ha detectado {len(panels)} paneles actuales en el HTML.")

    for panel in panels:
        game_id = panel.get('data-appid') or '0'
        sub_id = panel.get('data-subid') or '0'
        
        if game_id == "730" and sub_id == "14":
            continue  # Filtro de la plantilla interna de SteamDB
            
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
    # TU SECCIÓN 2: FUTUROS JUEGOS (Mantenida intacta)
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
    print("¡Base de datos actualizada con éxito mediante BeautifulSoup y DrissionPage!")

if __name__ == "__main__":
    init_db()
    # Cambiamos la descarga ligera por la descarga emulada que supera Cloudflare
    html_obtenido = obtener_html_con_navegador()
    procesar_html_con_soup(html_obtenido)