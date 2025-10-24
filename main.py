import os
import logging
import asyncio
from datetime import datetime
from discord.ext import commands, tasks
from dotenv import load_dotenv
import discord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("StableAudioBot")

load_dotenv()
TOKEN = os.getenv("TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", 0))

if not TOKEN:
    logger.critical("❌ Discord TOKEN не найден в .env")
    exit(1)
if not VOICE_CHANNEL_ID:
    logger.critical("❌ VOICE_CHANNEL_ID не найден в .env")
    exit(1)

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)
voice_client: discord.VoiceClient | None = None

async def get_voice_channel() -> discord.VoiceChannel | None:
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if isinstance(channel, discord.VoiceChannel):
        return channel
    logger.error("❌ Голосовой канал не найден")
    return None

@tasks.loop(minutes=10)
async def keep_alive_loop():
    global voice_client
    try:
        channel = await get_voice_channel()
        if not channel:
            return
        if not voice_client or not voice_client.is_connected():
            voice_client = await channel.connect(reconnect=True)
            logger.info(f"🔄 Подключён к голосовому каналу: {channel.name}")
        else:
            logger.info(f"✅ Бот уже в канале: {channel.name}")
    except Exception as e:
        logger.error(f"Ошибка в keep_alive_loop: {e}")

@bot.event
async def on_ready():
    logger.info(f"✅ Бот {bot.user} онлайн с {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if not keep_alive_loop.is_running():
        keep_alive_loop.start()

if __name__ == "__main__":
    try:
        bot.run(TOKEN, reconnect=True)
    except Exception as e:
        logger.critical(f"❌ Ошибка запуска бота: {e}")