import sqlite3
from DrissionPage import ChromiumPage, ChromiumOptions
import time

DB_PATH = "data/games.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS steam_games (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            start_date TEXT,
            end_date TEXT,
            promo_type TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def scrape_steamdb():
    print("Iniciando navegador (modo visible para asegurar carga)...")
    options = ChromiumOptions()
    # Lo ponemos en False temporalmente para que veas en tu pantalla cómo abre la web y extrae los datos
    options.headless(False) 
    
    page = ChromiumPage(options)
    
    try:
        page.get("https://steamdb.info/upcoming/free/")
        print("Esperando 5 segundos a que el JavaScript de SteamDB dibuje los juegos...")
        time.sleep(5) 
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM steam_games")

        # ==========================================
        # 1. CAPTURAR JUEGOS ACTUALES
        # ==========================================
        print("Buscando paneles de juegos actuales...")
        # DrissionPage usa '.' para clases, igual que CSS
        panels = page.eles('css:div.panel-sale.app-history-row')
        print(f"Se han encontrado {len(panels)} paneles en la pantalla.")

        for panel in panels:
            game_id = panel.attr('data-appid') or '0'
            sub_id = panel.attr('data-subid') or '0'
            
            # Filtro de seguridad para la plantilla oculta de SteamDB
            if game_id == "730" and sub_id == "14":
                continue
                
            # Extraemos el título
            title_elem = panel.ele('css:.panel-sale-name a')
            if not title_elem:
                continue
            title = title_elem.text.strip()
            
            if "steamdb.info" in title.lower():
                continue

            # URLs
            if game_id != "0":
                game_url = f"https://store.steampowered.com/app/{game_id}/"
                db_id = game_id
            else:
                game_url = f"https://store.steampowered.com/sub/{sub_id}/"
                db_id = f"sub_{sub_id}"

            # Tipo de promo
            cat_elem = panel.ele('css:div.cat')
            cat_text = cat_elem.text.strip() if cat_elem else ""
            promo_type = "Keep" if "Keep" in cat_text else "Weekend"

            # Fechas (DrissionPage lee el texto renderizado final, saltándose el Shadow DOM)
            time_elems = panel.eles('css:relative-time')
            start_date = time_elems[0].text.strip() if len(time_elems) >= 1 else "N/A"
            end_date = time_elems[1].text.strip() if len(time_elems) >= 2 else "N/A"

            cursor.execute('''
                INSERT OR REPLACE INTO steam_games (id, title, url, start_date, end_date, promo_type, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (db_id, title, game_url, start_date, end_date, promo_type, "current"))

        # ==========================================
        # 2. CAPTURAR FUTUROS JUEGOS
        # ==========================================
        print("Buscando lista de futuros juegos...")
        upcoming_list = page.ele('css:ul.upcoming-list')
        
        if upcoming_list:
            items = upcoming_list.eles('css:li a')
            print(f"Se han encontrado {len(items)} futuros juegos.")
            for item in items:
                title = item.text.strip()
                href = item.attr('href') or ''
                
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
                    INSERT OR REPLACE INTO steam_games (id, title, url, start_date, end_date, promo_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (db_id, title, game_url, "N/A", "N/A", "Upcoming", "upcoming"))

        conn.commit()
        conn.close()
        print("¡Base de datos guardada con éxito!")

    except Exception as e:
        print(f"Ocurrió un error durante el scraping: {e}")
    finally:
        page.quit()

if __name__ == "__main__":
    init_db()
    scrape_steamdb()