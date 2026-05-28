from typing import List, Dict, Set, Any, Optional
from database.connection import get_db_connection
from datetime import datetime, timedelta

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
    Guarda TODOS los juegos en lote, pero aplica la Regla de Exclusión de 14 días
    únicamente a los juegos gratuitos actuales ('current').
    """
    if not games_list:
        return []

    new_games_to_notify = []
    now = datetime.utcnow()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        for game in games_list:
            cursor.execute("SELECT last_notified FROM games WHERE id = ?", (game["id"],))
            row = cursor.fetchone()

            debe_notificar = False
            last_notified_val = row["last_notified"] if row else None
            
            # 1. Lógica de decisión de notificación SOLO para juegos activos
            if game.get("status") == "current":
                if row is None:
                    debe_notificar = True
                elif row["last_notified"]:
                    last_notified_date = datetime.fromisoformat(row["last_notified"])
                    if (now - last_notified_date) > timedelta(days=14):
                        debe_notificar = True

            # Si pasa el filtro, lo añadimos a la lista de envíos y actualizamos su timestamp
            if debe_notificar:
                new_games_to_notify.append(game)
                last_notified_val = now.isoformat()

            # 2. Guardamos SIEMPRE el juego (sea current o upcoming)
            cursor.execute("""
                INSERT INTO games (id, platform, title, url, image_url, promo_type, status, end_date, estimated_date, last_notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET 
                    status=excluded.status, 
                    end_date=excluded.end_date,
                    estimated_date=excluded.estimated_date,
                    last_notified=excluded.last_notified
            """, (game["id"], game["platform"], game["title"], game["url"], game.get("image_url"), 
                  game["promo_type"], game["status"], game.get("end_date"), game.get("estimated_date"), last_notified_val))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en base de datos al guardar lote: {e}")
    finally:
        conn.close()

    return new_games_to_notify

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