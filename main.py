import os
import logging
import discord
from discord.ext import tasks
from dotenv import load_dotenv
import aiohttp
from aiohttp import web
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Bot")

load_dotenv()
TOKEN = os.getenv("TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", "0"))

if not TOKEN:
    logger.critical("❌ Discord TOKEN не найден")
    exit(1)
if not VOICE_CHANNEL_ID:
    logger.critical("❌ VOICE_CHANNEL_ID не найден")
    exit(1)

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)
voice_client = None

@tasks.loop(minutes=10)
async def keep_alive():
    global voice_client
    try:
        channel = bot.get_channel(VOICE_CHANNEL_ID)
        if not isinstance(channel, discord.VoiceChannel):
            logger.error("❌ Канал не найден")
            return
        if not voice_client or not voice_client.is_connected():
            voice_client = await channel.connect(reconnect=True)
            logger.info(f"✅ Подключён к {channel.name}")
        else:
            logger.info(f"🔄 Уже в канале {channel.name}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.event
async def on_ready():
    logger.info(f"✅ Бот {bot.user} готов")
    if not keep_alive.is_running():
        keep_alive.start()

async def handle_keepalive(request):
    return web.Response(text="Bot is alive!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle_keepalive)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🔄 HTTP-сервер запущен на порту {port}")

async def main():
    try:
        async with aiohttp.ClientSession() as session:  # Создаём сессию для aiohttp
            await asyncio.gather(
                start_server(),
                bot.start(TOKEN)
            )
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")

if __name__ == "__main__":
    asyncio.run(main())