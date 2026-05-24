import sqlite3

DB_PATH = "data/games.db"

def mostrar_juegos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Ver juegos actuales
    print("=== JUEGOS ACTUALES EN LA BD ===")
    cursor.execute("SELECT title, promo_type, end_date, image_url FROM current_games")
    actuales = cursor.fetchall()
    for juego in actuales:
        print(f"🎮 [{juego[1]}] {juego[0]}")
        print(f"   ⏳ Expira: {juego[2]}")
        print(f"   🖼️ Imagen: {juego[3]}\n")
        
    print("="*40 + "\n")
    
    # 2. Ver futuros juegos
    print("=== PRÓXIMOS JUEGOS EN LA BD ===")
    cursor.execute("SELECT title, estimated_date FROM upcoming_games")
    futuros = cursor.fetchall()
    for juego in futuros:
        print(f"⏳ [{juego[1]}] -> {juego[0]}")
        
    conn.close()

if __name__ == "__main__":
    mostrar_juegos()