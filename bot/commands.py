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

    @app_commands.command(name="configurar_canal", description="Cambia el canal donde el bot publicará las alertas automáticas de juegos.")
    @app_commands.describe(canal="Selecciona el canal de texto para los anuncios.")
    @app_commands.checks.has_permissions(administrator=True) # Exclusivo para Administradores
    async def configurar_canal(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Comando Administrativo para enrutar las alertas globales."""
        db_manager.save_guild_channel(str(interaction.guild_id), str(canal.id))
        await interaction.response.send_message(
            f"⚙️ **Configuración Guardada:** A partir de ahora, las alertas globales de juegos gratuitos se enviarán a {canal.mention}.",
            ephemeral=True
        )

    @configurar_canal.error
    async def configurar_canal_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Captura de errores si un usuario no administrador intenta ejecutar el comando."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 No tienes permisos de `Administrador` para ejecutar este comando.",
                ephemeral=True
            )


# Función obligatoria para que discord.py cargue el Cog correctamente
async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))