import os
from dotenv import load_dotenv
from datetime import time
from zoneinfo import ZoneInfo  # Importación clave para ignorar el UTC confuso

# Cargar variables desde archivo .env si existe
load_dotenv()

# Discord & DB Configuration (Mantén tus variables igual)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "TU_TOKEN_AQUI")
DEFAULT_ALERT_CHANNEL_ID = os.getenv("DEFAULT_CHANNEL_ID")
DB_PATH = os.path.join("data", "games.db")

# ================================================================================
# CONFIGURACIÓN DE HORARIOS EN TU HORA LOCAL
# ================================================================================

# 1. Define aquí tu zona horaria real. Ejemplos comunes:
# - "Europe/Madrid" (España)
# - "America/Mexico_City" (México)
# - "America/Bogota" (Colombia/Perú)
# - "America/Argentina/Buenos_Aires" (Argentina)
ZONA_HORARIA_LOCAL = ZoneInfo("Europe/Madrid") 

# 2. Ahora configuras las horas tal cual las ves en el reloj de tu casa:
EPIC_SCRAPE_TIMES = [time(hour=16, minute=1, tzinfo=ZONA_HORARIA_LOCAL)] 
STEAM_SCRAPE_TIMES = [time(hour=0, minute=0, tzinfo=ZONA_HORARIA_LOCAL), time(hour=12, minute=0, tzinfo=ZONA_HORARIA_LOCAL)]
GOG_SCRAPE_TIMES = [time(hour=10, minute=0, tzinfo=ZONA_HORARIA_LOCAL)]

# El despachador de alertas a Discord despertará 4 minutos después de cada raspado
NOTIFICATION_TIMES = [
    time(hour=16, minute=5, tzinfo=ZONA_HORARIA_LOCAL),
    time(hour=0, minute=5, tzinfo=ZONA_HORARIA_LOCAL),
    time(hour=12, minute=5, tzinfo=ZONA_HORARIA_LOCAL),
    time(hour=10, minute=5, tzinfo=ZONA_HORARIA_LOCAL)
]

# El boletín dominical despertará a las 12:00 del mediodía de tu país
BOLETIN_TIME = time(hour=12, minute=0, tzinfo=ZONA_HORARIA_LOCAL)

# Headers comunes
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}