# JohnBotJovi.py
import os
import sys
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mafiabot")

# --- Cargar variables de entorno ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    log.critical("No se encontró DISCORD_TOKEN en las variables de entorno. Abortando.")
    sys.exit(1)

# --- Configurar intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # recuerda activar en el Developer Portal si es necesario

# --- Inicializar bot (Pycord) ---
bot = discord.Bot(intents=intents, debug_guilds=None)  # debug_guilds=None por defecto

# --- Evento on_ready ---
@bot.event
async def on_ready():
    log.info(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    try:
        # Opcional: sincronizar globalmente (cuidado con errores si hay nombres duplicados)
        await bot.sync_commands()
        log.info("Slash commands sincronizados correctamente.")
    except Exception as e:
        log.exception("Error al sincronizar comandos: %s", e)

# --- Cargar cogs automáticamente ---
cogs_dir = "./cogs"
for filename in os.listdir(cogs_dir):
    if not filename.endswith(".py"):
        continue
    module_name = f"cogs.{filename[:-3]}"
    try:
        bot.load_extension(module_name)
        log.info("📦 Módulo cargado: %s", filename)
    except Exception as e:
        log.exception("Error cargando cog %s: %s", module_name, e)

# --- Ejecutar bot ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        log.info("Interrupción por teclado, cerrando.")
    except Exception as e:
        log.exception("Error ejecutando el bot: %s", e)

