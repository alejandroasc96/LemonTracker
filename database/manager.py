from typing import List, Dict, Set, Any, Optional
from database.connection import get_db_connection
from datetime import datetime

def get_cached_game_ids() -> Set[str]:
    """Carga rápidamente todos los IDs existentes en RAM para el Diff-Caching."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM games")
    ids = {row["id"] for row in cursor.fetchall()}
    conn.close()
    return ids

def save_games_batch(games_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Guarda juegos en lote utilizando transacciones atómicas.
    Retorna únicamente los juegos que son NUEVOS para proceder a notificar.
    """
    if not games_list:
        return []

    cached_ids = get_cached_game_ids()
    new_games_detected = []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Iniciamos una transacción explícita
        cursor.execute("BEGIN TRANSACTION;")
        
        for game in games_list:
            # Si el juego ya existe, hacemos un update silencioso por si cambió la fecha de fin,
            # pero no lo clasificamos como 'nuevo juego a notificar' a menos que cambie su estado.
            if game["id"] not in cached_ids:
                new_games_detected.append(game)
                
            cursor.execute('''
                INSERT INTO games (id, platform, title, url, image_url, promo_type, status, end_date, estimated_date)
                VALUES (:id, :platform, :title, :url, :image_url, :promo_type, :status, :end_date, :estimated_date)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    end_date=excluded.end_date,
                    estimated_date=excluded.estimated_date
            ''', game)
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en la transacción de guardado: {e}")
        new_games_detected = []
    finally:
        conn.close()
        
    return new_games_detected

def update_notification_time(game_id: str):
    """Registra la marca de tiempo actual al enviar la notificación."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()
    cursor.execute("UPDATE games SET last_notified = ? WHERE id = ?", (now_str, game_id))
    conn.commit()
    conn.close()

def get_active_games() -> List[Dict[str, Any]]:
    """Recupera los juegos actualmente gratuitos en el sistema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM games WHERE status = 'current'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_games_pending_notification() -> List[Dict[str, Any]]:
    """
    Busca juegos activos que requieran notificación:
    - Nunca notificados (last_notified IS NULL)
    - O notificados hace más de 14 días.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Usamos modificadores de tiempo nativos de SQLite para no procesar fechas en Python
    cursor.execute('''
        SELECT * FROM games 
        WHERE status = 'current' 
          AND (last_notified IS NULL OR datetime(last_notified) < datetime('now', '-14 days'))
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_subscribers_for_game(game_id: str) -> List[str]:
    """Obtiene la lista de IDs de usuarios de Discord suscritos a un juego."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM subscriptions WHERE game_id = ?", (game_id,))
    users = [row["user_id"] for row in cursor.fetchall()]
    conn.close()
    return users

def delete_subscription(user_id: str, game_id: str):
    """Elimina una suscripción una vez que ya se ha notificado al usuario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ? AND game_id = ?", (user_id, game_id))
    conn.commit()
    conn.close()

def get_guild_alert_channel(guild_id: str) -> str | None:
    """Obtiene el canal personalizado de un servidor."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT alert_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row["alert_channel_id"] if row else None

def get_upcoming_games() -> List[Dict[str, Any]]:
    """Recupera los juegos futuros guardados en el sistema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM games WHERE status = 'upcoming'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_subscription(user_id: str, game_id: str) -> bool:
    """Inserta una suscripción de usuario. Retorna True si es nueva."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO subscriptions (user_id, game_id) VALUES (?, ?)", (user_id, game_id))
        conn.commit()
        # changes indica si se insertó la fila (1) o se ignoró (0)
        return conn.changes > 0
    except Exception as e:
        print(f"❌ Error al añadir suscripción: {e}")
        return False
    finally:
        conn.close()

def save_guild_channel(guild_id: str, channel_id: str):
    """Guarda o actualiza el canal de alertas exclusivo de un servidor."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO guild_settings (guild_id, alert_channel_id)
        VALUES (?, ?)
    ''', (guild_id, channel_id))
    conn.commit()
    conn.close()