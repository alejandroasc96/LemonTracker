import logging
from typing import Optional
from config import DEFAULT_HEADERS

try:
    from curl_cffi import requests
except ImportError:
    requests = None

# Configuración básica de logs para monitorear en la Nano Pi sin llenar el disco
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class BaseScraper:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)

    def fetch_html(self, url: str) -> Optional[str]:
        """Realiza una petición HTTP camuflada usando curl_cffi."""
        if requests is None:
            self.logger.error("La librería 'curl_cffi' no está instalada o no es compatible.")
            return None

        self.logger.info(f"📡 Solicitando datos de {url}...")
        try:
            # impersonate="chrome" imita el handshake TLS/HTTP2 exacto de un navegador real
            response = requests.get(url, headers=DEFAULT_HEADERS, impersonate="chrome", timeout=30)
            
            if response.status_code == 200:
                self.logger.info("✅ Datos obtenidos correctamente.")
                return response.text
            else:
                self.logger.warning(f"⚠️ Código de respuesta inesperado: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"❌ Error crítico en la petición: {e}")
            return None