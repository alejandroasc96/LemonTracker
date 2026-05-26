import discord
from discord.ext import commands, tasks
from config import SCRAPE_INTERVAL_SECONDS
from services.notifier import NotifierService

class GameNotifierBot(commands.Bot):
    def __init__(self):
        # Intenciones básicas: No necesitamos leer mensajes (Message Content Intent),
        # lo que ahorra un consumo enorme de ancho de banda y RAM en la Pi.
        intents = discord.Intents.default()
        intents.guilds = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.notifier_service = NotifierService(self)

    async def setup_hook(self):
        """Paso inicial de discord.py para cargar comandos y tareas en segundo plano."""
        # Cargar el archivo de comandos (Cog) que crearemos en el siguiente paso
        await self.load_extension("bot.commands")
        
        # Iniciar el bucle asíncrono periódico de raspado de datos
        self.scrape_loop.start()

    async def on_ready(self):
        print(f"🤖 [Bot] Conectado con éxito como {self.user}")
        
        # Sincronizar los comandos de barra globalmente con Discord
        try:
            print("🔄 Sincronizando comandos globales (/)...")
            synced = await self.tree.sync()
            print(f"✅ Se han sincronizado {len(synced)} comandos globales de barra.")
        except Exception as e:
            print(f"❌ Error sincronizando comandos: {e}")

        # Establecer presencia/estado estático ligero
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="ofertas de juegos")
        )

    @tasks.loop(seconds=SCRAPE_INTERVAL_SECONDS)
    async def scrape_loop(self):
        """Bucle en segundo plano que se ejecuta de forma controlada y asíncrona."""
        # Esperar a que el bot esté completamente listo internamente antes de raspar
        await self.wait_until_ready()
        try:
            await self.notifier_service.run_scrapers_and_notify()
        except Exception as e:
            print(f"❌ Error en la ejecución del bucle del scraper: {e}")