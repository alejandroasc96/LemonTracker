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

    async def scrape_and_update(self, platform_filter: str = None):
        """
        Ejecuta los scrapers (todos o uno específico según el filtro) y actualiza la BD.
        Gracias al Diff-Caching, si no hay novedades reales, no se desgastará la MicroSD.
        """
        target = platform_filter.lower() if platform_filter else "todas"
        print(f"🔍 [Notifier] Iniciando ciclo de raspado para plataforma: {target}...")
        
        all_scraped_games = []
        for scraper in self.scrapers:
            # Si se pasa un filtro específico (ej. "epic"), ignoramos los demás scrapers
            if platform_filter and platform_filter.lower() not in scraper.name.lower():
                continue
                
            try:
                games = scraper.extraer()
                all_scraped_games.extend(games)
            except Exception as e:
                print(f"❌ Error ejecutando {scraper.name}: {e}")

        if not all_scraped_games:
            print(f"⚠️ [Notifier] No se recuperaron juegos para {target} en este ciclo.")
            return

        # Para las suscripciones inmediatas por mensaje directo, necesitamos el estado previo en RAM
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM games")
        previous_states = {row["id"]: row["status"] for row in cursor.fetchall()}
        conn.close()

        # Guardar en lote (aquí actúa el Diff-Caching y la optimización SQLite)
        db_manager.save_games_batch(all_scraped_games)

        # Traspaso inmediato de 'upcoming' a 'current' para usuarios con suscripción por DM
        for game in all_scraped_games:
            if game["status"] == "current" and previous_states.get(game["id"]) == "upcoming":
                await self._process_user_subscriptions(game)

        print(f"✅ [Notifier] Raspado de {target} completado y guardado localmente.")

    async def send_pending_alerts(self):
        """Revisa la base de datos de manera independiente y despacha las alertas globales pendientes."""
        print("🔔 [Notifier] Comprobando cola de alertas globales pendientes en los canales...")
        
        pending_global_games = db_manager.get_games_pending_notification()
        if pending_global_games:
            await self._distribute_channel_alerts(pending_global_games)
            print(f"✅ [Notifier] {len(pending_global_games)} alertas globales enviadas con éxito.")
        else:
            print("📭 [Notifier] No hay alertas globales pendientes por notificar en este bloque horaria.")

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
            color=embed_color  # El color de la tarjeta representa visualmente el tipo de oferta
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
    
    def _build_upcoming_digest_embed(self, upcoming_games: List[Dict[str, Any]]) -> discord.Embed:
        """Construye una tarjeta informativa limpia y exclusiva para los próximos juegos estimados de Steam."""
        embed = discord.Embed(
            title="⏳ Próximas Previsiones de Juegos Gratuitos",
            description=(
                "Estos son los títulos detectados en la base de datos de SteamDB que planean futuras promociones.\n"
                "⚠️ *Las fechas son estimadas por la comunidad y pueden variar.*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            ),
            color=0x1b2838  # Azul oscuro mate de Steam
        )
        
        # Filtrar solo juegos de Steam y limitar a un Top 8 para mantenerlo compacto
        steam_upcoming = [g for g in upcoming_games if g["platform"] == "steam"][:8]
        
        if not steam_upcoming:
            embed.description += "\n📭 No hay previsiones de Steam detectadas en este ciclo.\n"
        else:
            for game in steam_upcoming:
                fecha_est = game.get("estimated_date") or "Por confirmar"
                embed.description += f"### 🎮 {game['title']} - {fecha_est}\n"
                
        embed.description += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                
        # Bloque de llamada a la acción en la parte inferior
        embed.add_field(
            name="🔔 ¿Quieres que el bot te avise automáticamente?",
            value="Si quieres que te envíe un **Mensaje Directo (DM)** en cuanto cualquiera de estos títulos pase a estar disponible, simplemente usa el comando **`/proximos`** y selecciónalo en el menú desplegable.",
            inline=False
        )
        
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Steam_icon_logo.svg/512px-Steam_icon_logo.svg.png")
        embed.set_footer(text="Boletín Bisemanal de Previsiones • Game Notifier Bot")
        return embed

    async def check_and_send_biweekly_digest(self):
        """Comprueba si hoy es domingo y distribuye el boletín si pasaron 14 días desde el último envío."""
        now = datetime.utcnow()
        
        # En Python, el domingo es el día 6 de la semana (0=Lunes, ..., 6=Domingo)
        if now.weekday() != 6:
            return

        upcoming_games = db_manager.get_upcoming_games()
        if not upcoming_games:
            return

        embed = self._build_upcoming_digest_embed(upcoming_games)
        
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT guild_id, alert_channel_id, last_upcoming_report FROM guild_settings")
        guilds_data = cursor.fetchall()
        conn.close()

        for row in guilds_data:
            guild_id = row["guild_id"]
            channel_id = row["alert_channel_id"]
            last_report_str = row["last_upcoming_report"]

            debe_enviar = False
            if not last_report_str:
                debe_enviar = True
            else:
                last_report = datetime.fromisoformat(last_report_str)
                # Margen de seguridad de 13 días para evitar variaciones de minutos del reloj
                if (now - last_report).days >= 13:
                    debe_enviar = True

            if debe_enviar:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue
                
                channel = guild.get_channel(int(channel_id)) if channel_id else guild.system_channel
                if channel:
                    try:
                        await channel.send(embed=embed)
                        db_manager.update_guild_upcoming_report_time(guild_id, now.isoformat())
                        print(f"📅 [Boletín] Boletín bisemanal enviado al servidor: {guild.name}")
                    except Exception as e:
                        print(f"❌ Error al enviar boletín dominical a {guild.name}: {e}")