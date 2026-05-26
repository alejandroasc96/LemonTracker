import discord
from datetime import datetime
from typing import List, Dict, Any
from scrapers.steam import SteamScraper
from scrapers.epic import EpicScraper
from scrapers.gog import GogScraper
import database.manager as db_manager
from config import DEFAULT_ALERT_CHANNEL_ID

class NotifierService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        # Instanciamos los scrapers reutilizando sus configuraciones
        self.scrapers = [SteamScraper(), EpicScraper(), GogScraper()]

    async def run_scrapers_and_notify(self):
        """Orquestador principal del ciclo de raspado y distribución de alertas."""
        print("🔍 [Notifier] Iniciando ciclo de actualización de plataformas...")
        
        # 1. Ejecutar todos los scrapers recopilando la información en memoria
        all_scraped_games = []
        for scraper in self.scrapers:
            try:
                games = scraper.extraer()
                all_scraped_games.extend(games)
            except Exception as e:
                print(f"❌ Error ejecutando {scraper.name}: {e}")

        if not all_scraped_games:
            print("⚠️ [Notifier] No se recuperaron juegos en este ciclo.")
            return

        # 2. Obtener el estado de los juegos en la DB ANTES de guardar los nuevos cambios
        # Esto nos permite saber si un juego era 'upcoming' antes de volverse 'current'
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM games")
        previous_states = {row["id"]: row["status"] for row in cursor.fetchall()}
        conn.close()

        # 3. Guardar en bloque aplicando Diff-Caching
        db_manager.save_games_batch(all_scraped_games)

        # 4. Procesar notificaciones globales en canales (Regla de los 14 días)
        pending_global_games = db_manager.get_games_pending_notification()
        if pending_global_games:
            await self._distribute_channel_alerts(pending_global_games)

        # 5. Procesar Suscripciones por Mensaje Directo (DM)
        # Un juego califica si su estado anterior era 'upcoming' y el scraper lo movió a 'current'
        for game in all_scraped_games:
            if game["status"] == "current" and previous_states.get(game["id"]) == "upcoming":
                await self._process_user_subscriptions(game)

        print("✅ [Notifier] Ciclo de notificaciones completado con éxito.")

    async def _distribute_channel_alerts(self, games: List[Dict[str, Any]]):
        """Envía las alertas de nuevos juegos a los canales correspondientes."""
        for game in games:
            embed = self._build_game_embed(game)
            
            # Enviar a todos los servidores donde el bot está presente
            for guild in self.bot.guilds:
                # Comprobar si el servidor tiene un canal configurado de forma personalizada
                channel_id = db_manager.get_guild_alert_channel(str(guild.id))
                
                # Si no tiene, recurrir al canal por defecto de la configuración o al 'system_channel'
                if not channel_id:
                    channel_id = DEFAULT_ALERT_CHANNEL_ID
                    
                channel = guild.get_channel(int(channel_id)) if channel_id else guild.system_channel
                
                if channel:
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        print(f"🚫 Permisos insuficientes en el servidor {guild.name} para el canal {channel.id}")
                    except Exception as e:
                        print(f"❌ Error enviando alerta a servidor {guild.name}: {e}")
            
            # Actualizar la marca de tiempo en la base de datos para activar el bloqueo de 14 días
            db_manager.update_notification_time(game["id"])

    async def _process_user_subscriptions(self, game: Dict[str, Any]):
        """Detecta usuarios suscritos a un juego futuro que ya está libre y les envía un DM."""
        user_ids = db_manager.get_subscribers_for_game(game["id"])
        if not user_ids:
            return

        embed = self._build_game_embed(game)
        embed.title = f"🔔 ¡Un juego de tu lista de deseos ya está disponible gratis!: {game['title']}"
        embed.color = discord.Color.gold()

        print(f"🚀 [Suscripciones] Notificando por DM a {len(user_ids)} usuarios sobre {game['title']}...")
        
        for u_id in user_ids:
            try:
                user = await self.bot.fetch_user(int(u_id))
                if user:
                    await user.send(embed=embed)
                    # Limpieza para no duplicar en el futuro
                    db_manager.delete_subscription(u_id, game["id"])
            except discord.Forbidden:
                print(f"🔒 El usuario {u_id} tiene los DMs cerrados. No se pudo notificar.")
            except Exception as e:
                print(f"❌ Error al enviar DM al usuario {u_id}: {e}")

    def _build_game_embed(self, game: Dict[str, Any]) -> discord.Embed:
        """Construye un Embed limpio, estandarizado y visualmente atractivo."""
        # Colores temáticos por plataforma
        colors = {
            "steam": discord.Color.blue(),
            "epic": discord.Color.dark_gray(),
            "gog": discord.Color.purple()
        }
        
        embed = discord.Embed(
            title=game["title"],
            url=game["url"],
            description=f"🎁 ¡Juego gratuito disponible en **{game['platform'].upper()}**!",
            color=colors.get(game["platform"], discord.Color.green()),
            timestamp=datetime.utcnow()
        )
        
        # Tipo de promoción destacado
        tipo_promo = "Gratis para siempre (Keep Free)" if game["promo_type"] == "Keep" else "Fin de semana gratuito (Weekend Trial)"
        embed.add_field(name="Tipo de promoción", value=tipo_promo, inline=True)
        
        # Fecha de vencimiento si existe
        if game.get("end_date"):
            try:
                # Formatear la fecha ISO para hacerla amigable
                dt = datetime.fromisoformat(game["end_date"].replace("Z", "+00:00"))
                fecha_formato = dt.strftime("%d/%m/%Y a las %H:%M UTC")
                embed.add_field(name="Finaliza el", value=f"📅 {fecha_formato}", inline=True)
            except:
                embed.add_field(name="Finaliza el", value=f"📅 {game['end_date']}", inline=True)
                
        if game.get("image_url"):
            embed.set_image(url=game["image_url"])
            
        embed.set_footer(text=f"Game Notifier Bot • {game['platform'].capitalize()}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        return embed