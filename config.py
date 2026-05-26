import os
from dotenv import load_dotenv

# Cargar variables desde archivo .env si existe
load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "TU_TOKEN_AQUI")
DEFAULT_ALERT_CHANNEL_ID = os.getenv("DEFAULT_CHANNEL_ID")  # Puede ser None al inicio

# Database Settings
DB_PATH = os.path.join("data", "games.db")

# Scraper Settings (en segundos)
# Ejemplo: Ejecutar scrapers cada 6 horas para no saturar la red ni la CPU
SCRAPE_INTERVAL_SECONDS = 6 * 60 * 60 

# Headers comunes para comportamiento orgánico en peticiones
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}