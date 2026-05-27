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
        self.scrapers = [SteamScraper(), EpicScraper(), GogScraper()]

    async def run_scrapers_and_notify(self):
        """Orquestador principal del ciclo de raspado y distribución de alertas."""
        print("🔍 [Notifier] Iniciando ciclo de actualización de plataformas...")
        
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

        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM games")
        previous_states = {row["id"]: row["status"] for row in cursor.fetchall()}
        conn.close()

        db_manager.save_games_batch(all_scraped_games)

        pending_global_games = db_manager.get_games_pending_notification()
        # pending_global_games = [g for g in all_scraped_games if g["status"] == "current"] # Para probar el proceso automático de alertas globales sin esperar a que se cumplan las condiciones de notificación basadas en tiempo
        if pending_global_games:
            await self._distribute_channel_alerts(pending_global_games)

        for game in all_scraped_games:
            if game["status"] == "current" and previous_states.get(game["id"]) == "upcoming":
                await self._process_user_subscriptions(game)

        print("✅ [Notifier] Ciclo de notificaciones completado con éxito.")

    async def _distribute_channel_alerts(self, games: List[Dict[str, Any]]):
        """Envía las alertas de nuevos juegos a los canales correspondientes."""
        for game in games:
            embed = self._build_game_embed(game)
            
            for guild in self.bot.guilds:
                channel_id = db_manager.get_guild_alert_channel(str(guild.id))
                
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
            
            db_manager.update_notification_time(game["id"])

    async def _process_user_subscriptions(self, game: Dict[str, Any]):
        """Detecta usuarios suscritos a un juego futuro que ya está libre y les envía un DM."""
        user_ids = db_manager.get_subscribers_for_game(game["id"])
        if not user_ids:
            return

        embed = self._build_game_embed(game)
        embed.title = f"🔔 ¡Disponibilidad Gratuita!: {game['title']}"
        
        for u_id in user_ids:
            try:
                user = await self.bot.fetch_user(int(u_id))
                if user:
                    await user.send(embed=embed)
                    db_manager.delete_subscription(u_id, game["id"])
            except discord.Forbidden:
                print(f"🔒 El usuario {u_id} tiene los DMs cerrados. No se pudo notificar.")
            except Exception as e:
                print(f"❌ Error al enviar DM al usuario {u_id}: {e}")

    def _build_game_embed(self, game: Dict[str, Any]) -> discord.Embed:
        """Construye una tarjeta (Embed) adaptando el texto y los colores según la promoción."""
        
        platform_icons = {
            "steam": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Steam_icon_logo.svg/512px-Steam_icon_logo.svg.png",
            "epic": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Epic_Games_logo.svg/512px-Epic_Games_logo.svg.png",
            "gog": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/GOG.com_logo.svg/512px-GOG.com_logo.svg.png"
        }
        
        # --- CONFIGURACIÓN DINÁMICA DE PROMO (COLORES Y TEXTOS) ---
        if game["promo_type"] == "Keep":
            badge = "🟢 **Free to keep**"
            embed_color = 0x2ECC71  # Verde Esmeralda brillante para el borde
            descripcion_dinamica = (
                "¡Consigue este juego gratis ahora y **pásatelo a tu biblioteca permanente**! "
                "Será tuyo para siempre sin coste alguno."
            )
            tipo_promo_field = "🆓 Conservarlo para siempre"
        else:
            badge = "🟠 **Play for free**"
            embed_color = 0xE67E22  # Naranja vivo brillante para el borde
            descripcion_dinamica = (
                "¡Este título está disponible para **jugar gratis por tiempo limitado**! "
                "Disfruta del acceso completo al juego antes de que expire el periodo de prueba."
            )
            tipo_promo_field = "⏳ Fin de semana / Prueba gratuita"

        # Configuración final del Embed
        embed = discord.Embed(
            title=game["title"],
            url=game["url"], 
            description=(
                f"{badge}\n\n"
                f"{descripcion_dinamica}\n\n"
                f"🔗 **[Ver oferta directamente en la tienda]({game['url']})**"
            ),
            color=embed_color  # El color de la tarjeta ahora representa visualmente la urgencia/tipo de oferta
        )
        
        if game["platform"] in platform_icons:
            embed.set_thumbnail(url=platform_icons[game["platform"]])
            
        if game.get("image_url"):
            embed.set_image(url=game["image_url"])
            
        # Añadimos los datos en formato tabla abajo
        embed.add_field(name="Tipo de Promoción", value=tipo_promo_field, inline=True)
        embed.add_field(name="Plataforma", value=game["platform"].capitalize(), inline=True)
        
        if game.get("end_date"):
            try:
                dt = datetime.fromisoformat(game["end_date"].replace("Z", "+00:00"))
                embed.add_field(name="Finaliza el", value=f"📅 {dt.strftime('%d/%m/%Y %H:%M UTC')}", inline=False)
            except:
                embed.add_field(name="Finaliza el", value=f"📅 {game['end_date']}", inline=False)
                
        embed.set_footer(
            text="Game Notifier Bot • Alertas automáticas", 
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        return embed