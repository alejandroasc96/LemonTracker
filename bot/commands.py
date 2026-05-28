import discord
from discord import app_commands
from discord.ext import commands
import database.manager as db_manager

class SubscriptionDropdown(discord.ui.Select):
    """Menú desplegable interactivo que lista juegos futuros para suscribirse."""
    def __init__(self, upcoming_games: list):
        # Limitar a los primeros 25 juegos (límite estricto de la API de Discord para Selects)
        options = [
            discord.SelectOption(
                label=game["title"][:100], 
                value=game["id"], 
                description=f"Plataforma: {game['platform'].upper()} - Est: {game['estimated_date'] or '?'}"
            )
            for game in upcoming_games[:25]
        ]
        super().__init__(placeholder="Elige un juego para suscribirte...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Manejar la selección del usuario
        game_id = self.values[0]
        user_id = str(interaction.user.id)
        
        # Recuperar título para el mensaje final
        conn = db_manager.get_db_connection()
        row = conn.execute("SELECT title FROM games WHERE id = ?", (game_id,)).fetchone()
        conn.close()
        game_title = row["title"] if row else "Juego desconocido"

        # Registrar suscripción de manera eficiente en DB
        is_new = db_manager.add_subscription(user_id, game_id)
        
        if is_new:
            await interaction.response.send_message(
                f"✅ ¡Suscripción confirmada! Te enviaré un DM automático cuando **{game_title}** pase a estar gratuito.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ Ya estás suscrito a **{game_title}**.",
                ephemeral=True
            )

class SubscriptionView(discord.ui.View):
    """Contenedor de interfaz que aloja el dropdown, con expiración automática para liberar RAM."""
    def __init__(self, upcoming_games: list):
        super().__init__(timeout=60) # Expira en 60 segundos
        self.add_item(SubscriptionDropdown(upcoming_games))


class GameCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="gratis", description="Juegos gratuitos activos.")
    async def gratis(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        active = db_manager.get_active_games()
        
        if not active:
            await interaction.followup.send("No hay juegos libres ahora.", ephemeral=True)
            return

        embeds = []
        # Crear el primer embed principal
        current_embed = discord.Embed(title="🎁 Juegos Gratuitos Activos", color=discord.Color.green())
        
        for i, g in enumerate(active):
            # Cada vez que alcancemos los 25 campos, guardamos el embed actual y abrimos uno nuevo
            if i > 0 and i % 25 == 0:
                embeds.append(current_embed)
                current_embed = discord.Embed(title="🎁 Juegos Gratuitos Activos (Continuación)", color=discord.Color.green())
            
            current_embed.add_field(
                name=g["title"], 
                value=f"• **{g['platform'].upper()}**\n• [Tienda]({g['url']})", 
                inline=False
            )
            
        # Añadir el último embed que quedó en proceso
        embeds.append(current_embed)

        # Discord permite enviar una lista de hasta 10 embeds usando el parámetro 'embeds'
        # Limitamos a [:10] de forma defensiva para evitar superar el límite de mensajes de la API (10 embeds * 25 fields = 250 juegos)
        await interaction.followup.send(embeds=embeds[:10], ephemeral=True)

    @app_commands.command(name="proximos", description="Lista juegos futuros y permite suscribirte para recibir alertas en DM.")
    async def proximos(self, interaction: discord.Interaction):
        """Comando de usuario Efímero con interfaz interactiva."""
        await interaction.response.defer(ephemeral=True)
        
        upcoming_games = db_manager.get_upcoming_games()
        if not upcoming_games:
            await interaction.followup.send("📅 No hay promociones futuras programadas o detectadas en SteamDB en este momento.")
            return

        embed = discord.Embed(
            title="📅 Próximos Juegos Gratuitos (SteamDB)",
            description="Selecciona un juego en el menú desplegable de abajo para que el bot te avise por Mensaje Directo (DM) en cuanto esté disponible.",
            color=discord.Color.blue()
        )
        
        for game in upcoming_games[:10]: # Listar top 10 en texto para no saturar la pantalla
            embed.add_field(
                name=game["title"],
                value=f"• Fecha estimada: {game['estimated_date'] or 'Por confirmar'}",
                inline=False
            )

        # Enviar el embed junto con la vista interactiva para procesar la suscripción sin teclear
        view = SubscriptionView(upcoming_games)
        await interaction.followup.send(embed=embed, view=view)

    # @app_commands.command(name="configurar_canal", description="Cambia el canal donde el bot publicará las alertas automáticas de juegos.")
    # @app_commands.describe(canal="Selecciona el canal de texto para los anuncios.")
    # @app_commands.default_permissions(administrator=True)
    # @app_commands.checks.has_permissions(administrator=True) # Exclusivo para Administradores
    # async def configurar_canal(self, interaction: discord.Interaction, canal: discord.TextChannel):
    #     """Comando Administrativo para enrutar las alertas globales y publicar el estado actual."""
    #     await interaction.response.defer(ephemeral=True)
        
    #     db_manager.save_guild_channel(str(interaction.guild_id), str(canal.id))
        
    #     await interaction.followup.send(
    #         f"⚙️ **Configuración Guardada:** A partir de ahora, las alertas globales se enviarán a {canal.mention}. Generando listado de bienvenida...",
    #         ephemeral=True
    #     )

    #     # Buscar juegos activos en la DB y mandarlos al nuevo canal
    #     active_games = db_manager.get_active_games()
    #     if active_games:
    #         notifier = interaction.client.notifier_service
    #         embeds = [notifier._build_game_embed(game) for game in active_games]
            
    #         # Agrupamos en bloques de 10 (Límite estricto de Discord para embeds en un solo mensaje)
    #         for i in range(0, len(embeds), 10):
    #             await canal.send(
    #                 content="🎉 **[Juegos Gratuitos Actuales]** Aquí tienes los títulos disponibles:" if i == 0 else "",
    #                 embeds=embeds[i:i+10]
    #             )
    @app_commands.command(name="configurar_canal", description="Cambia el canal donde el bot publicará las alertas automáticas de juegos.")
    @app_commands.describe(canal="Selecciona el canal de texto para los anuncios.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configurar_canal(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Comando Administrativo para enrutar las alertas globales."""
        await interaction.response.defer(ephemeral=True)
        
        db_manager.save_guild_channel(str(interaction.guild_id), str(canal.id))
        
        await interaction.followup.send(
            f"⚙️ **Configuración Guardada:** A partir de ahora, las alertas globales se enviarán a {canal.mention}. Generando listados de bienvenida...",
            ephemeral=True
        )

        notifier = interaction.client.notifier_service

        # 1. Enviar Juegos Activos Actuales
        active_games = db_manager.get_active_games()
        if active_games:
            embeds = [notifier._build_game_embed(game) for game in active_games]
            for i in range(0, len(embeds), 10):
                await canal.send(
                    content="🎉 **[Juegos Gratuitos Actuales]** Aquí tienes los títulos disponibles hoy:",
                    embeds=embeds[i:i+10]
                )

        # 2. Enviar Nuevo Formato de Previsiones Futuras (Onboarding inicial)
        upcoming_games = db_manager.get_upcoming_games()
        if upcoming_games:
            embed_upcoming = notifier._build_upcoming_digest_embed(upcoming_games)
            await canal.send(embed=embed_upcoming)

    @configurar_canal.error
    async def configurar_canal_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Captura de errores si un usuario no administrador intenta ejecutar el comando."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 No tienes permisos de `Administrador` para ejecutar este comando.",
                ephemeral=True
            )

    @app_commands.command(name="forzar_scrapers", description="🤖 [Admin] Fuerza la ejecución manual de todos los scrapers.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def forzar_scrapers(self, interaction: discord.Interaction):
        """Llama directamente al servicio orquestador del bot."""
        # Avisamos de inmediato de forma efímera para evitar el timeout de 3 segundos de Discord
        await interaction.response.send_message("⚡ Iniciando ciclo forzado de raspado... Revisa la consola de la Nano Pi.", ephemeral=True)
        
        try:
            # Accedemos al notifier_service desde la instancia del cliente/bot
            await interaction.client.notifier_service.run_scrapers_and_notify()
            await interaction.followup.send("✅ Ciclo de raspado y notificación completado.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error al forzar scrapers: {e}", ephemeral=True)

    @app_commands.command(name="test_tarjeta", description="🎨 [Admin] Envía una tarjeta de prueba con el nuevo diseño visual.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def test_tarjeta(self, interaction: discord.Interaction):
        """Genera un juego ficticio para comprobar que los botones y el Embed se ven perfectos."""
        await interaction.response.defer(ephemeral=True)
        
        # Creamos un diccionario falso (Mock) imitando la estructura de tus scrapers
        juego_falso = {
            "id": "steam_test_999999",
            "platform": "steam",
            "title": "Cyberpunk 2077 (Juego de Prueba)",
            "url": "https://store.steampowered.com/app/1091500/Cyberpunk_2077/",
            "image_url": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1091500/capsule_616x353.jpg",
            "promo_type": "Keep",
            "status": "current",
            "end_date": "2026-12-31T23:59:59Z"
        }
        
        try:
            # Construimos la tarjeta usando los métodos de tu nuevo notifier.py
            notifier = interaction.client.notifier_service
            embed = notifier._build_game_embed(juego_falso)
            
            # Importamos la vista de los botones localmente para el test
            from services.notifier import ClaimGameView
            view = ClaimGameView(juego_falso["url"], juego_falso["platform"])
            
            # Lo enviamos directamente al canal donde se ejecutó el comando para verlo en directo
            await interaction.channel.send(
                content="🧪 **[TEST DE INTERFAZ]** Así es como verán los usuarios las alertas:", 
                embed=embed, 
                view=view
            )
            await interaction.followup.send("✅ Tarjeta de prueba enviada con éxito.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error al generar la tarjeta: {e}", ephemeral=True)

    @app_commands.command(name="forzar_envio", description="🤖 [Admin] Fuerza el envío de todos los juegos activos al canal configurado.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def forzar_envio(self, interaction: discord.Interaction):
        """Comando de depuración para probar el diseño de los mensajes sin esperar alertas globales."""
        await interaction.response.defer(ephemeral=True)
        
        active_games = db_manager.get_active_games()
        if not active_games:
            await interaction.followup.send("❌ No hay juegos activos en la base de datos para enviar.", ephemeral=True)
            return
            
        # Determinar el canal al que debe ir
        channel_id = db_manager.get_guild_alert_channel(str(interaction.guild_id))
        canal = interaction.guild.get_channel(int(channel_id)) if channel_id else interaction.channel
        
        if not canal:
            await interaction.followup.send("❌ No se encontró un canal válido para enviar los mensajes.", ephemeral=True)
            return

        notifier = interaction.client.notifier_service
        embeds = [notifier._build_game_embed(game) for game in active_games]
        
        # Enviar respetando el límite de la API de Discord
        try:
            for i in range(0, len(embeds), 10):
                await canal.send(
                    content="🔧 **[Prueba de Envío Forzado]**" if i == 0 else "", 
                    embeds=embeds[i:i+10]
                )
            await interaction.followup.send(f"✅ Se han enviado {len(active_games)} juegos al canal {canal.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error al enviar los mensajes al canal: {e}", ephemeral=True)

    @app_commands.command(name="simular_dm", description="🤖 [Admin] Simula que un juego al que estás suscrito acaba de salir gratis.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def simular_dm(self, interaction: discord.Interaction):
        """Busca una suscripción activa del usuario y dispara el flujo de MD de forma simulada."""
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        
        # 1. Buscar a qué juego está suscrito el usuario que ejecuta el comando
        conn = db_manager.get_db_connection()
        row = conn.execute('''
            SELECT g.* FROM games g 
            JOIN subscriptions s ON g.id = s.game_id 
            WHERE s.user_id = ? 
            LIMIT 1
        ''', (user_id,)).fetchone()
        conn.close()
        
        if not row:
            await interaction.followup.send(
                "❌ No estás suscrito a ningún juego. Usa `/proximos` primero para suscribirte a uno y vuelve a intentarlo.", 
                ephemeral=True
            )
            return
            
        # 2. Convertir la fila en un diccionario y forzar su estado para engañar al sistema
        juego_simulado = dict(row)
        juego_simulado["status"] = "current"
        
        # Por si el scraper no extrajo bien el promo_type en el upcoming, forzamos 'Keep' para que el Embed quede bonito
        if not juego_simulado.get("promo_type"):
            juego_simulado["promo_type"] = "Keep" 

        # 3. Llamar directamente a la función real del Notifier que procesa y envía los MDs
        try:
            notifier = interaction.client.notifier_service
            
            # Esto enviará el MD a todos los suscritos (incluyéndote a ti) y borrará la suscripción de la base de datos
            await notifier._process_user_subscriptions(juego_simulado)
            
            await interaction.followup.send(
                f"✅ **¡Simulación completada!**\nEl sistema cree que **{juego_simulado['title']}** ya es gratis.\nRevisa tus Mensajes Directos de Discord. (Nota: tu suscripción a este juego ha sido consumida y borrada, exactamente como ocurriría en producción).", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error crítico al intentar enviar el MD: {e}", ephemeral=True)

    @app_commands.command(name="probar_boletin", description="🤖 [Admin] Muestra una vista previa en directo del nuevo boletín bisemanal de Steam.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def probar_boletin(self, interaction: discord.Interaction):
        """Genera y envía el Embed del boletín bisemanal en el canal actual para control de calidad."""
        await interaction.response.defer(ephemeral=True)
        
        # 1. Intentar recuperar juegos próximos reales de la DB
        upcoming_games = db_manager.get_upcoming_games()
        
        # 2. Si la DB está vacía (por ejemplo, tras un reset), creamos datos de prueba
        # para poder evaluar el diseño visual de todos modos.
        if not upcoming_games:
            upcoming_games = [
                {
                    "id": "steam_app_test1",
                    "platform": "steam",
                    "title": "Half-Life 3 (Simulación de Prueba)",
                    "url": "https://store.steampowered.com/",
                    "estimated_date": "Noviembre de 2026",
                    "promo_type": "Keep",
                    "status": "upcoming"
                },
                {
                    "id": "steam_app_test2",
                    "platform": "steam",
                    "title": "Portal 3 (Simulación de Prueba)",
                    "url": "https://store.steampowered.com/",
                    "estimated_date": "Por confirmar",
                    "promo_type": "Keep",
                    "status": "upcoming"
                }
            ]
            aviso_datos = "⚠️ *Nota: Como tu base de datos no tiene juegos próximos indexados en este momento, se están mostrando títulos de prueba.*"
        else:
            aviso_datos = "📊 *Mostrando datos reales extraídos de tu base de datos local.*"

        # 3. Construir la tarjeta usando el servicio notifier
        notifier = interaction.client.notifier_service
        embed_boletin = notifier._build_upcoming_digest_embed(upcoming_games)
        
        try:
            # Enviamos el diseño al canal de texto para verlo al 100% de tamaño
            await interaction.channel.send(
                content=f"🧪 **[TEST DE INTERFAZ]** Vista previa del boletín dominical.\n{aviso_datos}",
                embed=embed_boletin
            )
            await interaction.followup.send("✅ Vista previa generada en el canal.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error al enviar la vista previa: {e}", ephemeral=True)


# Función obligatoria para que discord.py cargue el Cog correctamente
async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))