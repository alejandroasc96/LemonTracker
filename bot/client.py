import discord
from discord.ext import commands, tasks
from config import EPIC_SCRAPE_TIMES, STEAM_SCRAPE_TIMES, GOG_SCRAPE_TIMES, NOTIFICATION_TIMES, BOLETIN_TIME
from services.notifier import NotifierService

class GameNotifierBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True  # Optimizado para la Nano Pi
        
        super().__init__(command_prefix="!", intents=intents)
        self.notifier_service = NotifierService(self)

    async def setup_hook(self):
        """Paso inicial de discord.py para cargar comandos e iniciar todas las tareas."""
        await self.load_extension("bot.commands")
        
        # Iniciar bucles con horarios fijos locales
        self.epic_scrape_loop.start()
        self.steam_scrape_loop.start()
        self.gog_scrape_loop.start()
        self.notification_dispatcher_loop.start()
        self.biweekly_loop.start()
        
        # SAlVAGUARDA: Ejecuta un chequeo único asíncrono en segundo plano al arrancar el bot
        self.loop.create_task(self.run_startup_check())

    async def run_startup_check(self):
        """
        Se ejecuta una sola vez al encender el bot.
        Evita el 'punto ciego' si el bot se levanta pasadas las 16:01.
        """
        await self.wait_until_ready()
        print("🚀 [Startup] Bot encendido. Ejecutando actualización inicial preventiva...")
        try:
            # Ejecuta un raspado general de todas las plataformas
            await self.notifier_service.scrape_and_update()
            # Si detecta que hay juegos nuevos que no han sido notificados, los envía inmediatamente
            await self.notifier_service.send_pending_alerts()
            print("✅ [Startup] Actualización inicial completada con éxito.")
        except Exception as e:
            print(f"❌ Error en la comprobación inicial de arranque: {e}")

    async def on_ready(self):
        print(f"🤖 [Bot] Conectado con éxito como {self.user}")
        try:
            synced = await self.tree.sync()
            print(f"✅ Se han sincronizado {len(synced)} comandos globales de barra.")
        except Exception as e:
            print(f"❌ Error sincronizando comandos: {e}")

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="ofertas de juegos")
        )

    # === BUCLES DE RASPADO PROGRAMADOS ===

    @tasks.loop(time=EPIC_SCRAPE_TIMES)
    async def epic_scrape_loop(self):
        await self.wait_until_ready()
        try:
            await self.notifier_service.scrape_and_update(platform_filter="epic")
        except Exception as e:
            print(f"❌ Error crítico en el bucle de raspado de Epic Games: {e}")

    @tasks.loop(time=STEAM_SCRAPE_TIMES)
    async def steam_scrape_loop(self):
        await self.wait_until_ready()
        try:
            await self.notifier_service.scrape_and_update(platform_filter="steam")
        except Exception as e:
            print(f"❌ Error crítico en el bucle de raspado de Steam: {e}")

    @tasks.loop(time=GOG_SCRAPE_TIMES)
    async def gog_scrape_loop(self):
        await self.wait_until_ready()
        try:
            await self.notifier_service.scrape_and_update(platform_filter="gog")
        except Exception as e:
            print(f"❌ Error crítico en el bucle de raspado de GOG: {e}")

    # === BUCLE DE NOTIFICACIONES ===

    @tasks.loop(time=NOTIFICATION_TIMES)
    async def notification_dispatcher_loop(self):
        await self.wait_until_ready()
        try:
            await self.notifier_service.send_pending_alerts()
        except Exception as e:
            print(f"❌ Error crítico en el despachador de notificaciones globales: {e}")

    # === BOLETÍN BISEMANAL ===

    @tasks.loop(time=BOLETIN_TIME)
    async def biweekly_loop(self):
        await self.wait_until_ready()
        try:
            await self.notifier_service.check_and_send_biweekly_digest()
        except Exception as e:
            print(f"❌ Error crítico en el bucle del boletín dominical: {e}")