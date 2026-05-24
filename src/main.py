from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI(title="SteamDB Data API")

# Habilitar CORS para que cualquier aplicación externa pueda consultar tu API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "data/games.db"

def get_games_from_db(status_filter: str, promo_filter: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if promo_filter:
        cursor.execute("SELECT * FROM steam_games WHERE status = ? AND promo_type = ?", (status_filter, promo_filter))
    else:
        cursor.execute("SELECT * FROM steam_games WHERE status = ?", (status_filter,))
        
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ENDPOINT 1: Juegos actualmente gratuitos (Promociones activas tipo 'Keep')
@app.get("/api/games/current/free")
def get_current_free():
    return get_games_from_db(status_filter="current", promo_filter="Keep")

# ENDPOINT 2: Fines de semana gratuitos / Free to play temporales activos ('Weekend')
@app.get("/api/games/current/f2p")
def get_current_f2p():
    return get_games_from_db(status_filter="current", promo_filter="Weekend")

# ENDPOINT 3: Futuros juegos gratuitos (Próximas promociones detectadas)
@app.get("/api/games/upcoming")
def get_upcoming_games():
    return get_games_from_db(status_filter="upcoming")