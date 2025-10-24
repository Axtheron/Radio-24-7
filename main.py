import os
import shutil
import logging
import asyncio
from datetime import datetime
from flask import Flask, jsonify
from threading import Thread


import yt_dlp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("StableAudioBot")

flask_app = Flask("keepalive")

load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", 0))
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "0.7"))

if not TOKEN:
    logger.critical("❌ Discord TOKEN не найден в .env")
    exit(1)

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.message_content = False

bot = commands.Bot(command_prefix="/", intents=intents)
voice_client: discord.VoiceClient | None = None
start_time: datetime | None = None

YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "extract_flat": False,
    "http_headers": {"User-Agent": "Mozilla/5.0"}
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -ac 2 -ar 48000"
}

def check_ffmpeg() -> bool:
    if not shutil.which("ffmpeg"):
        logger.critical("❌ FFmpeg не найден. Установи его в системе!")
        return False
    return True

async def get_voice_channel() -> discord.VoiceChannel | None:
    if not VOICE_CHANNEL_ID:
        return None
    for guild in bot.guilds:
        channel = guild.get_channel(VOICE_CHANNEL_ID)
        if isinstance(channel, discord.VoiceChannel):
            return channel
    return None

async def prepare_source(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get("url")
                if not stream_url:
                    raise RuntimeError("Не удалось извлечь URL потока.")
                return stream_url
        except Exception as e:
            logger.error(f"Ошибка yt_dlp: {e}")
            raise
    return url

async def play_url(vc: discord.VoiceClient, url: str, volume: float = DEFAULT_VOLUME):
    try:
        stream_url = await prepare_source(url)
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS)
        wrapped = discord.PCMVolumeTransformer(source, volume=volume)
        vc.play(wrapped, after=lambda e: logger.error(f"Playback error: {e}") if e else None)
        logger.info(f"▶️ Воспроизводится: {url}")
    except Exception as e:
        logger.error(f"Ошибка воспроизведения {url}: {e}")
        raise

@tasks.loop(minutes=10)
async def keep_alive_loop():
    global voice_client
    try:
        channel = await get_voice_channel()
        if not channel:
            return
        if not voice_client or not voice_client.is_connected():
            voice_client = await channel.connect(reconnect=True)
            logger.info(f"🔄 Переподключился к каналу: {channel.name}")
    except Exception as e:
        logger.error(f"Ошибка в keep_alive_loop: {e}")

@bot.event
async def on_ready():
    global start_time, voice_client
    start_time = datetime.now()
    logger.info(f"✅ Бот {bot.user} онлайн с {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if not check_ffmpeg():
        return

    try:
        await bot.tree.sync()
        logger.info("Slash-команды синхронизированы.")
    except Exception as e:
        logger.warning(f"Не удалось синхронизировать команды: {e}")

    channel = await get_voice_channel()
    if channel:
        try:
            voice_client = await channel.connect(reconnect=True)
            logger.info(f"Подключён к голосовому каналу: {channel.name}")
        except Exception as e:
            logger.error(f"Ошибка авто-подключения: {e}")

    if not keep_alive_loop.is_running():
        keep_alive_loop.start()


@flask_app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": str(bot.user) if bot and getattr(bot, "user", None) else "starting"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

def start_keepalive_thread():
    t = Thread(target=run_flask, daemon=True)
    t.start()


@bot.tree.command(name="play", description="Проигрывает аудио с YouTube или прямой ссылки")
async def slash_play(interaction: discord.Interaction, url: str):
    global voice_client
    await interaction.response.defer()
    if not check_ffmpeg():
        await interaction.followup.send("❌ FFmpeg не найден.")
        return

    if not voice_client or not voice_client.is_connected():
        channel = await get_voice_channel()
        if not channel:
            await interaction.followup.send("❌ Голосовой канал не найден.")
            return
        voice_client = await channel.connect(reconnect=True)

    try:
        await play_url(voice_client, url)
        await interaction.followup.send(f"▶️ Воспроизвожу: {url}")
    except Exception as e:
        await interaction.followup.send("❌ Ошибка при воспроизведении.")
        logger.error(e)

if __name__ == "__main__":
    try:
        bot.run(TOKEN, reconnect=True)
    except Exception as e:
        logger.critical(f"❌ Ошибка запуска бота: {e}")
