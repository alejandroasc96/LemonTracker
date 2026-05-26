import sys
from database.connection import init_db
from bot.client import GameNotifierBot
from config import DISCORD_TOKEN

def main():
    """Punto de entrada principal del ciclo de vida de la aplicación."""
    print("🚀 [System] Iniciando Game Notifier Bot...")
    
    # 1. Inicializar la Base de Datos y aplicar PRAGMAs anti-desgaste (Modo WAL)
    try:
        print("💾 Inicializando base de datos SQLite optimizada...")
        init_db()
        print("✅ Base de datos lista y verificada.")
    except Exception as e:
        print(f"❌ Error crítico al inicializar la base de datos: {e}")
        sys.exit(1)

    # 2. Validar credenciales básicas
    if DISCORD_TOKEN == "TU_TOKEN_AQUI" or not DISCORD_TOKEN:
        print("❌ Error: No se ha configurado un DISCORD_TOKEN válido en el archivo .env o config.py")
        sys.exit(1)

    # 3. Instanciar e iniciar el Bot de Discord
    # El método .run() es bloqueante, maneja internamente el loop asíncrono
    # y la reconexión automática ante caídas de red.
    bot = GameNotifierBot()
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 [System] Apagado ordenado recibido desde la terminal. Cerrando procesos...")
    except Exception as e:
        print(f"❌ Error crítico durante la ejecución del bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()