import os
import sqlite3
from config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    """
    Crea y devuelve una conexión a SQLite con optimizaciones críticas 
    para mitigar el desgaste de la tarjeta microSD.
    """
    # Asegurar que el directorio data/ existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    # Habilitar el acceso por nombre de columna (diccionario)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    
    # --- OPTIMIZACIONES ANTI-DESGASTE ---
    # 1. Modo WAL: Escribe de forma secuencial en un archivo temporal (.wal) 
    # en lugar de bloquear y escribir el archivo principal constantemente.
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # 2. Sincronización Normal: El sistema operativo decide el volcado físico 
    # sin pausar la CPU en cada transacción. Es ideal para SBCs.
    cursor.execute("PRAGMA synchronous=NORMAL;")
    
    # 3. Cache en memoria incrementado (en páginas de 4KB, aprox 8MB de caché)
    cursor.execute("PRAGMA cache_size=-2000;")
    
    return conn

def init_db():
    """Inicializa la estructura unificada de la base de datos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla única para unificar Steam, Epic y GOG resolviendo desajustes previos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            image_url TEXT,
            promo_type TEXT NOT NULL, -- 'Keep', 'Weekend', 'F2P'
            status TEXT NOT NULL,     -- 'current', 'upcoming'
            end_date TEXT,
            estimated_date TEXT,
            last_notified TEXT       -- ISO Timestamp de cuándo se envió a Discord
        )
    ''')
    
    # Tabla de configuraciones del servidor (Canal de alertas personalizado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            alert_channel_id TEXT NOT NULL
        )
    ''')
    
    # Tabla para las suscripciones de usuarios a juegos futuros
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id TEXT,
            game_id TEXT,
            PRIMARY KEY (user_id, game_id)
        )
    ''')
    
    conn.commit()
    conn.close()