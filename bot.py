import os
import re
import json
import glob
import time
import uuid
import shutil
import random
import logging
import asyncio
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
import yt_dlp
import static_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

# ---------------------------------------------------------------------------
# 1. System Setup & Static FFmpeg Loader
# ---------------------------------------------------------------------------
try:
    static_ffmpeg.add_paths()
except Exception:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger("NahidDownloaderPro")

# Credentials & API Gateways
TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY") or os.getenv("X-RapidAPI-Key", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST") or os.getenv("X-RapidAPI-Host", "all-in-one-media-downloader-api.p.rapidapi.com")

ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"
BOT_LOGO_URL = "https://user55725.cn.imgto.link/public/20261113/fd75766042207998416adf8f-1000482026.avif"
MAX_UPLOAD_LIMIT = 48 * 1024 * 1024  # 48 MB Safe limit for Telegram Bot API
STATS_FILE = "stats.json"

# Track Active Jobs & Live Cancel Signals
ACTIVE_CANCELS = {}
JOB_PROGRESS = {}

# ---------------------------------------------------------------------------
# 2. 20 Witty & Engaging English Loading Messages
# ---------------------------------------------------------------------------
FUNNY_QUOTES = [
    "☕ Grab a cup of coffee! Our server hamsters are running on nitro overdrive...",
    "🐢 Move aside turtle! Supersonic download packets are arriving at light speed!",
    "🚀 Even Elon Musk's Falcon 9 would be jealous of our transfer velocity!",
    "🥷 Sneaking past platform security guards like a cyber shadow ninja...",
    "🧙‍♂️ Chanting digital sorcery: Abracadabra, pixels assemble right now!",
    "🍿 Getting the popcorn ready, your high-definition video is almost cooked!",
    "🏎️ Burning digital rubber on the high-speed data superhighway!",
    "🤖 Teaching platform algorithms some manners so they release your clip...",
    "💎 Polishing every frame so your video sparkles in crisp 60 FPS clarity!",
    "🍕 Moving faster than someone who just heard 'free pizza in the lobby'!",
    "⚡ Our cloud servers are drinking double-shot espressos right now...",
    "📦 Wrestling the high-definition stream into a clean MP4 package...",
    "🛸 Beaming down cosmic media packets straight into your Telegram chat...",
    "🎪 Juggling bits and bytes like a circus acrobat on a flying unicycle...",
    "🎯 Locking on target: Direct video delivery arriving in 3... 2... 1...",
    "🎸 Shredding through server firewalls like an electric rockstar solo!",
    "🏊‍♂️ Diving deep into the data ocean to fish out your original video...",
    "🔋 Charging hyper-drive capacitors to maximum operational velocity!",
    "🎧 Tuning the audio-video frequencies to studio grade perfection...",
    "🏁 Approaching the finish line! Finalizing the media render..."
]

# ---------------------------------------------------------------------------
# 3. Persistent Database (Survives Restarts)
# ---------------------------------------------------------------------------
def load_db():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {
                    "total_downloads": d.get("total_downloads", 0),
                    "unique_users": set(d.get("unique_users", []))
                }
        except Exception:
            pass
    return {"total_downloads": 0, "unique_users": set()}

def save_db():
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "total_downloads": DB["total_downloads"],
                "unique_users": list(DB["unique_users"])
            }, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to persist DB: {e}")

DB = load_db()

# ---------------------------------------------------------------------------
# 4. Render 24/7 Keep-Alive HTTP Daemon
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nahid Video Downloader Pro - 24/7 Engine Active")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------------------------
# 5. URL Sanitizers & Resolvers
# ---------------------------------------------------------------------------
def sanitize_youtube_url(url: str) -> str:
    """Strips tracking garbage and normalizes Shorts to standard streaming URLs."""
    url = re.sub(r'(\?|\&)si=[^&]*', '', url)
    url = re.sub(r'(\?|\&)feature=[^&]*', '', url)
    url = url.replace("/shorts/", "/watch?v=")
    return url

def clean_social_url(url: str) -> str:
    """Unwraps Facebook & Instagram share trackers to direct canonical links."""
    clean = url.split("?")[0].strip()
    if any(k in url for k in ["facebook.com/share", "fb.watch", "facebook.com/reel"]):
        try:
            r = requests.get(
                url, 
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15"}, 
                allow_redirects=True, 
                timeout=8
            )
            resolved = r.url.split("?")[0]
            if "facebook.com" in resolved:
                return resolved
        except Exception:
            pass
    return clean if clean.startswith("http") else url

# ---------------------------------------------------------------------------
# 6. Stream Downloader with Live Progress Tracking
# ---------------------------------------------------------------------------
def download_stream_with_progress(stream_url: str, save_path: str, job_id: str) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with requests.get(stream_url, headers=headers, stream=True, timeout=40) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 512):
                    if ACTIVE_CANCELS.get(job_id):
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_size - downloaded) / speed if speed > 0 and total_size > downloaded else 0
                        JOB_PROGRESS[job_id] = {
                            "downloaded": downloaded,
                            "total": total_size,
                            "speed": speed,
                            "eta": eta
                        }
        return os.path.exists(save_path) and os.path.getsize(save_path) > 1000
    except Exception as e:
        logger.warning(f"Stream download error: {e}")
        return False

# ---------------------------------------------------------------------------
# 7. Specialized Scrapers & RapidAPI Gateway
# ---------------------------------------------------------------------------
def scrape_facebook_layer1(url: str) -> str:
    """FDown proxy scraper to bypass cloud IP blocks."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://fdown.net/",
            "Origin": "https://fdown.net",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        res = requests.post("https://fdown.net/download.php", data={"URLz": url}, headers=headers, timeout=12)
        if res.status_code == 200:
            html = res.text
            hd = re.search(r'id=["\']hdlink["\'][^>]*href=["\']([^"\']+)["\']', html)
            if hd:
                return hd.group(1).replace("&amp;", "&")
            sd = re.search(r'id=["\']sdlink["\'][^>]*href=["\']([^"\']+)["\']', html)
            if sd:
                return sd.group(1).replace("&amp;", "&")
    except Exception:
        pass
    return None

def scrape_facebook_layer2(url: str) -> str:
    """Direct mobile regex stream scraper."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        res = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        html = res.text
        patterns = [
            r'"browser_native_hd_url":"(https:[^"]+)"',
            r'"browser_native_sd_url":"(https:[^"]+)"',
            r'"playable_url_quality_hd":"(https:[^"]+)"',
            r'"playable_url":"(https:[^"]+)"',
            r'hd_src:"([^"]+)"',
            r'sd_src:"([^"]+)"'
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                raw = m.group(1).encode('utf-8').decode('unicode-escape').replace('\\/', '/').replace('&amp;', '&')
                if raw.startswith("http"):
                    return raw
    except Exception:
        pass
    return None

def download_tiktok_tikwm(url: str, save_path: str, job_id: str) -> bool:
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            v_url = res["data"]["play"]
            return download_stream_with_progress(v_url, save_path, job_id)
    except Exception:
        pass
    return False

def download_via_rapidapi(url: str, save_path: str, job_id: str) -> bool:
    """RapidAPI Universal Gateway Fallback for YouTube, Facebook, and Instagram."""
    if not RAPIDAPI_KEY:
        return False
    try:
        endpoint = f"https://{RAPIDAPI_HOST}/"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json"
        }
        # Try POST first
        r = requests.post(endpoint, json={"url": url}, headers=headers, timeout=20)
        if r.status_code != 200:
            r = requests.get(endpoint, params={"url": url}, headers=headers, timeout=20)

        if r.status_code == 200:
            data = r.json()
            dl_url = data.get("download_url") or data.get("url")
            if not dl_url and "medias" in data and data["medias"]:
                dl_url = data["medias"][0].get("url")
            if not dl_url and "video" in data:
                dl_url = data.get("video")
            if dl_url:
                return download_stream_with_progress(dl_url, save_path, job_id)
    except Exception as e:
        logger.warning(f"RapidAPI execution notice: {e}")
    return False

# ---------------------------------------------------------------------------
# 8. Adaptive yt-dlp Engine with iOS/Android Client Spoofing
# ---------------------------------------------------------------------------
class DownloadCancelledException(Exception):
    pass

def download_with_ytdlp(url: str, output_path: str, job_id: str, is_youtube: bool = False):
    def hook(d):
        if ACTIVE_CANCELS.get(job_id):
            raise DownloadCancelledException("Download cancelled by user.")
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            JOB_PROGRESS[job_id] = {
                "downloaded": downloaded,
                "total": total,
                "speed": speed,
                "eta": eta
            }

    if is_youtube:
        format_selector = (
            'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/'
            'bestvideo[height<=720][filesize_approx<=45M]+bestaudio/'
            'best[height<=480][ext=mp4]/'
            'best[height<=480]/'
            'best'
        )
    else:
        format_selector = (
            'b[ext=mp4]/'
            'bestvideo[height<=720]+bestaudio/'
            'best[height<=720][ext=mp4]/'
            'best'
        )

    ydl_opts = {
        'format': format_selector,
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'progress_hooks': [hook],
        'buffersize': 1024 * 1024,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'mweb'],
                'player_skip': ['webpage', 'configs'],
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.sanitize_info(info)

def fetch_direct_stream_url(url: str):
    ydl_opts = {
        'format': 'best', 
        'quiet': True, 
        'no_warnings': True, 
        'noplaylist': True,
        'extractor_args': {
            'youtube': {'player_client': ['ios', 'android', 'mweb']}
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url') or (info.get('requested_formats') and info['requested_formats'][0].get('url'))

# ---------------------------------------------------------------------------
# 9. Futuristic Sound Wave Equalizer (Live Fluctuating UI)
# ---------------------------------------------------------------------------
EQUALIZER_WAVES = [
    " ▂▃▅▆▇█▇▆▅▃▂ ",
    "▃▅▆▇██▇▆▅▃▂  ",
    "▆▇██▇▆▅▄▃▂ ▂▃",
    "▇██▇▆▅▃▂ ▂▃▅▆",
    "▅▃▂ ▂▃▅▆▇██▇▆"
]

def make_progress_bar(pct: float) -> str:
    filled = max(0, min(12, int(pct // 8.33)))
    empty = 12 - filled
    return "█" * filled + "░" * empty

def format_live_progress_text(downloaded: int, total: int, speed: float, eta: int, quote: str, frame_idx: int) -> str:
    pct = min(99.9, (downloaded / total * 100)) if total > 0 else 0.0
    bar = make_progress_bar(pct)
    wave_bars = EQUALIZER_WAVES[frame_idx % len(EQUALIZER_WAVES)]
    
    dl_mb = downloaded / (1024 * 1024)
    tot_mb = total / (1024 * 1024) if total > 0 else 0.0
    spd_mb = speed / (1024 * 1024) if speed > 0 else 0.0
    
    eta_str = f"{int(eta)}s" if eta > 0 else "Calculating..."
    size_str = f"{dl_mb:.1f} / {tot_mb:.1f} MB" if tot_mb > 0 else f"{dl_mb:.1f} MB"

    return (
        "🎛️ <b>NAHID MEDIA ENGINE — TURBO STREAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📥 <b>Status:</b> <i>Downloading High-Speed Media...</i>\n"
        f"🎚️ <b>Equalizer:</b> <code>{wave_bars}</code>\n"
        "🔊 <b>Frequency:</b> <code>ılı.lıllılı.ıllı.lıllılı</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Buffer:</b> <code>[{bar}] {pct:.1f}%</code>\n"
        f"💾 <b>Size:</b> <code>{size_str}</code>\n"
        f"🚀 <b>Speed:</b> <code>{spd_mb:.1f} MB/s</code> | ⏳ <b>ETA:</b> <code>{eta_str}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>\"{quote}\"</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <i>Engine: Multi-Tier CDN Cloud Gateway</i>"
    )

def build_cancel_keyboard(job_id: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Download", callback_data=f"cancel_{job_id}")]])

async def send_banner_safe(chat_id, caption, reply_markup=None, context=None):
    try:
        return await context.bot.send_photo(
            chat_id=chat_id,
            photo=BOT_LOGO_URL,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    except Exception:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

# ---------------------------------------------------------------------------
# 10. Global UI Dashboard Keyboards (100% Professional English)
# ---------------------------------------------------------------------------
def build_main_menu(user_id: int):
    keyboard = [
        [
            InlineKeyboardButton("👤 My Profile", callback_data="btn_profile"),
            InlineKeyboardButton("📊 Live Statistics", callback_data="btn_stats")
        ],
        [
            InlineKeyboardButton("ℹ️ User Guide", callback_data="btn_guide"),
            InlineKeyboardButton("✍️ Feedback / Report", callback_data="btn_feedback")
        ],
        [
            InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")
        ]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ Admin Master Panel", callback_data="btn_admin")])
    return InlineKeyboardMarkup(keyboard)

# ---------------------------------------------------------------------------
# 11. Command Handlers
# ---------------------------------------------------------------------------
async def set_menu_commands(application):
    commands = [
        BotCommand("start", "🚀 Start / Refresh Main Dashboard"),
        BotCommand("stats", "📊 View Global Bot Statistics"),
        BotCommand("profile", "👤 View Personal Profile"),
        BotCommand("feedback", "✍️ Send Feedback / Report Issue"),
        BotCommand("admin", "💬 Contact Verified Admin")
    ]
    try:
        await application.bot.set_my_commands(commands)
    except Exception:
        pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    DB["unique_users"].add(user.id)
    save_db()
    context.user_data["feedback_mode"] = False

    welcome_text = (
        f"👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{user.first_name}</b>!\n\n"
        "⚡ <b>The Ultimate Global Media Downloader</b>\n"
        "Drop any public video link from YouTube, Facebook, Instagram, or TikTok to download instantly in Full HD!\n\n"
        "🌐 <b>Platforms Supported:</b>\n"
        "• <b>YouTube</b> (Shorts, Long Songs & Standard Videos)\n"
        "• <b>Facebook</b> (Reels, Watch, Long Videos)\n"
        "• <b>Instagram</b> (Reels, Posts & Stories)\n"
        "• <b>TikTok</b> (Watermark-free Full HD)\n"
        "• <b>X/Twitter, Pinterest, Threads</b> & 1000+ more.\n\n"
        "👇 <i>Use the dashboard below or click <b>[ ☰ Menu ]</b>:</i>"
    )
    try:
        await update.message.delete()
    except Exception:
        pass
    await send_banner_safe(update.effective_chat.id, welcome_text, build_main_menu(user.id), context)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    text = (
        "📊 <b>Nahid Video Downloader — Global Stats</b>\n\n"
        f"👥 <b>Total Active Users:</b> <code>{len(DB['unique_users']):,}</code>\n"
        f"📥 <b>Total Media Processed:</b> <code>{DB['total_downloads']:,}</code>\n"
        "🟢 <b>Server Status:</b> <code>Online 24/7 (High-Speed Turbo)</code>\n"
        "⚡ <b>Engine Health:</b> <code>Quad-Layer Anti-Bot Active</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    text = (
        "👤 <b>User Account Overview</b>\n\n"
        f"• <b>Name:</b> {user.first_name} {user.last_name or ''}\n"
        f"• <b>User ID:</b> <code>{user.id}</code>\n"
        "• <b>Language:</b> 🇬🇧 Global English\n"
        "• <b>Access Tier:</b> <code>Unlimited Turbo Access</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = True
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_home")]])
    await update.message.reply_text(
        "✍️ <b>Send Feedback & Suggestions</b>\nType your message below. It will be sent directly to the admin:",
        reply_markup=cancel_kb,
        parse_mode=ParseMode.HTML
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    kb = [[InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(f"👨‍💻 <b>Support:</b> @{ADMIN_USERNAME}", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# ---------------------------------------------------------------------------
# 12. Interactive Button Callbacks (with Legacy Support)
# ---------------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data.startswith("cancel_"):
        job_id = data.replace("cancel_", "")
        ACTIVE_CANCELS[job_id] = True
        try:
            await query.edit_message_caption(
                caption="❌ <b>Download Cancelled!</b>\nThe operation was terminated by user.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.edit_message_text(
                text="❌ <b>Download Cancelled!</b>\nThe operation was terminated by user.",
                parse_mode=ParseMode.HTML
            )
        return

    legacy_map = {
        "my_profile": "btn_profile", "help_guide": "btn_guide", "admin_panel": "btn_admin",
        "back_home": "btn_home", "menu_home": "btn_home"
    }
    data = legacy_map.get(data, data)
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]])

    if data == "btn_feedback":
        context.user_data["feedback_mode"] = True
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_home")]])
        try:
            await query.edit_message_caption(
                caption="✍️ <b>Send Feedback & Suggestions</b>\nType your message below. It will be sent directly to the admin:",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_kb
            )
        except Exception:
            await query.edit_message_text(
                text="✍️ <b>Send Feedback & Suggestions</b>\nType your message below. It will be sent directly to the admin:",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_kb
            )
        return

    elif data == "btn_stats":
        context.user_data["feedback_mode"] = False
        text = (
            "📊 <b>Nahid Video Downloader — Global Stats</b>\n\n"
            f"👥 <b>Total Active Users:</b> <code>{len(DB['unique_users']):,}</code>\n"
            f"📥 <b>Total Media Processed:</b> <code>{DB['total_downloads']:,}</code>\n"
            "🟢 <b>Server Status:</b> <code>Online 24/7 (Turbo)</code>\n"
            "⚡ <b>Engine Health:</b> <code>Quad-Layer Anti-Bot Active</code>"
        )
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_profile":
        context.user_data["feedback_mode"] = False
        text = (
            "👤 <b>User Account Overview</b>\n\n"
            f"• <b>Name:</b> {user.first_name} {user.last_name or ''}\n"
            f"• <b>User ID:</b> <code>{user.id}</code>\n"
            "• <b>Language:</b> 🇬🇧 Global English\n"
            "• <b>Access Tier:</b> <code>Unlimited Turbo Access</code>"
        )
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_guide":
        context.user_data["feedback_mode"] = False
        text = (
            "📌 <b>Quick User Manual:</b>\n\n"
            "1. Copy any video URL from YouTube, Facebook, Instagram, or TikTok.\n"
            "2. Paste it directly into this chat.\n"
            "3. Media under <b>50 MB</b> is delivered in chat with instant streaming.\n"
            "4. Large media over <b>50 MB</b> generates a high-speed direct download link."
        )
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_admin":
        context.user_data["feedback_mode"] = False
        if user.id == ADMIN_ID:
            stats_text = (
                f"🛠️ <b>Master Developer Control Panel</b>\n\n"
                f"• <b>Total Users:</b> <code>{len(DB['unique_users'])}</code>\n"
                f"• <b>Total Downloads:</b> <code>{DB['total_downloads']}</code>\n"
                f"• <b>RapidAPI Gateway:</b> <code>{'Active' if RAPIDAPI_KEY else 'Disabled'}</code>\n"
                "• <b>Server Status:</b> <code>Optimal (24/7 Turbo)</code>"
            )
            try:
                await query.edit_message_caption(caption=stats_text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
            except Exception:
                await query.edit_message_text(text=stats_text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        else:
            await query.answer("Access Restricted: Administrator Only!", show_alert=True)

    elif data == "btn_home":
        context.user_data["feedback_mode"] = False
        welcome_text = (
            f"👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{user.first_name}</b>!\n\n"
            "⚡ <b>The Ultimate Global Media Downloader</b>\n"
            "Drop any public video link from YouTube, Facebook, Instagram, or TikTok to download instantly in Full HD!\n\n"
            "👇 <i>Use the dashboard below or click <b>[ ☰ Menu ]</b>:</i>"
        )
        try:
            await query.edit_message_caption(caption=welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))
        except Exception:
            await query.edit_message_text(text=welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))

# ---------------------------------------------------------------------------
# 13. Message Handler & Live Dynamic Loop
# ---------------------------------------------------------------------------
async def handle_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    raw_text = message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user

    DB["unique_users"].add(user.id)
    save_db()

    # Feedback Routing (Direct to Admin 8815124111)
    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False
        user_name = f"{user.first_name} {user.last_name or ''}".strip()
        user_handle = f"@{user.username}" if user.username else "No Username"
        admin_text = (
            "📬 <b>New User Feedback Received!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>From:</b> {user_name}\n"
            f"🔗 <b>Username:</b> {user_handle}\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Message:</b>\n\n{raw_text}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

        await message.reply_text(
            "✅ <b>Thank you!</b> Your message has been forwarded directly to the admin.",
            reply_markup=build_main_menu(user.id),
            parse_mode=ParseMode.HTML
        )
        return

    # Extract Video Link
    urls = re.findall(r'(https?://\S+)', raw_text)

    # Non-link Auto-Delete & 5-Second Warning
    if not urls:
        try:
            await message.delete()
        except Exception:
            pass

        warn_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="🚨 <b>Hey! This isn't a chatroom for nonsense! 😂</b>\nPlease send a valid <b>YouTube, Facebook, TikTok, or Instagram</b> link!", 
            parse_mode=ParseMode.HTML
        )

        async def delete_warning_later(msg_id: int):
            await asyncio.sleep(5)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass

        asyncio.create_task(delete_warning_later(warn_msg.message_id))
        return

    # Auto-delete user link message instantly
    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]
    job_id = uuid.uuid4().hex[:8]
    ACTIVE_CANCELS[job_id] = False
    JOB_PROGRESS[job_id] = {"downloaded": 0, "total": 0, "speed": 0, "eta": 0}

    initial_quote = random.choice(FUNNY_QUOTES)
    initial_text = format_live_progress_text(0, 0, 0, 0, initial_quote, 0)
    proc_msg = await send_banner_safe(
        chat_id=chat_id, 
        caption=initial_text, 
        reply_markup=build_cancel_keyboard(job_id), 
        context=context
    )

    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    # Live Fluctuating Progress Loop (Every 1.5s)
    loop_active = True
    async def live_progress_loop():
        last_rendered_text = initial_text
        frame = 0
        while loop_active:
            await asyncio.sleep(1.5)
            if not loop_active or ACTIVE_CANCELS.get(job_id):
                break
            
            prog = JOB_PROGRESS.get(job_id, {})
            downloaded = prog.get("downloaded", 0)
            total = prog.get("total", 0)
            speed = prog.get("speed", 0)
            eta = prog.get("eta", 0)
            
            frame += 1
            cur_quote = random.choice(FUNNY_QUOTES)
            updated_card = format_live_progress_text(downloaded, total, speed, eta, cur_quote, frame)

            if updated_card != last_rendered_text:
                last_rendered_text = updated_card
                try:
                    if proc_msg.photo:
                        await proc_msg.edit_caption(
                            caption=updated_card, 
                            parse_mode=ParseMode.HTML, 
                            reply_markup=build_cancel_keyboard(job_id)
                        )
                    else:
                        await proc_msg.edit_text(
                            text=updated_card, 
                            parse_mode=ParseMode.HTML, 
                            reply_markup=build_cancel_keyboard(job_id)
                        )
                except Exception:
                    pass

    progress_task = asyncio.create_task(live_progress_loop())

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        loop = asyncio.get_running_loop()
        download_success = False
        direct_stream_url = None

        is_youtube = ("youtube.com" in target_url or "youtu.be" in target_url)
        cleaned_url = sanitize_youtube_url(target_url) if is_youtube else clean_social_url(target_url)

        # -------------------------------------------------------------------
        # 1. YOUTUBE EXTRACTION ENGINE (Permanent Anti-Bot + RapidAPI)
        # -------------------------------------------------------------------
        if is_youtube:
            # Primary: Native Mobile App Client Spoofing
            try:
                await loop.run_in_executor(
                    None, 
                    download_with_ytdlp, 
                    cleaned_url, 
                    output_template, 
                    job_id, 
                    True
                )
                download_success = True
            except DownloadCancelledException:
                return
            except Exception as e:
                logger.warning(f"YouTube primary engine notice: {e}")

            # Secondary Fallback: RapidAPI Gateway (Instant Bypass)
            if not download_success and RAPIDAPI_KEY and not ACTIVE_CANCELS.get(job_id):
                yt_file = str(temp_dir / "yt_video.mp4")
                download_success = await loop.run_in_executor(
                    None, 
                    download_via_rapidapi, 
                    cleaned_url, 
                    yt_file, 
                    job_id
                )

        # -------------------------------------------------------------------
        # 2. FACEBOOK EXTRACTION ENGINE (Quad-Layer Bypasses)
        # -------------------------------------------------------------------
        elif "facebook.com" in target_url or "fb.watch" in target_url:
            # Layer 1: FDown Scraper
            stream_l1 = await loop.run_in_executor(None, scrape_facebook_layer1, cleaned_url)
            if stream_l1 and not ACTIVE_CANCELS.get(job_id):
                direct_stream_url = stream_l1
                fb_file = str(temp_dir / "fb_video.mp4")
                download_success = await loop.run_in_executor(
                    None, 
                    download_stream_with_progress, 
                    stream_l1, 
                    fb_file, 
                    job_id
                )

            # Layer 2: Mobile Native Regex
            if not download_success and not ACTIVE_CANCELS.get(job_id):
                stream_l2 = await loop.run_in_executor(None, scrape_facebook_layer2, cleaned_url)
                if stream_l2:
                    direct_stream_url = stream_l2
                    fb_file = str(temp_dir / "fb_video.mp4")
                    download_success = await loop.run_in_executor(
                        None, 
                        download_stream_with_progress, 
                        stream_l2, 
                        fb_file, 
                        job_id
                    )

            # Layer 3: RapidAPI Gateway
            if not download_success and RAPIDAPI_KEY and not ACTIVE_CANCELS.get(job_id):
                fb_file = str(temp_dir / "fb_video.mp4")
                download_success = await loop.run_in_executor(
                    None, 
                    download_via_rapidapi, 
                    cleaned_url, 
                    fb_file, 
                    job_id
                )

            # Layer 4: Universal yt-dlp Engine
            if not download_success and not ACTIVE_CANCELS.get(job_id):
                try:
                    await loop.run_in_executor(
                        None, 
                        download_with_ytdlp, 
                        cleaned_url, 
                        output_template, 
                        job_id, 
                        False
                    )
                    download_success = True
                except DownloadCancelledException:
                    return
                except Exception as e:
                    logger.warning(f"FB yt-dlp notice: {e}")

        # -------------------------------------------------------------------
        # 3. TIKTOK, INSTAGRAM, TWITTER & OTHERS
        # -------------------------------------------------------------------
        else:
            # TikTok TikWM Fallback First
            if "tiktok.com" in cleaned_url or "douyin.com" in cleaned_url:
                tiktok_file = str(temp_dir / "tiktok_video.mp4")
                download_success = await loop.run_in_executor(
                    None, 
                    download_tiktok_tikwm, 
                    cleaned_url, 
                    tiktok_file, 
                    job_id
                )

            # RapidAPI Gateway
            if not download_success and RAPIDAPI_KEY and not ACTIVE_CANCELS.get(job_id):
                media_file = str(temp_dir / "media_video.mp4")
                download_success = await loop.run_in_executor(
                    None, 
                    download_via_rapidapi, 
                    cleaned_url, 
                    media_file, 
                    job_id
                )

            # Universal Engine
            if not download_success and not ACTIVE_CANCELS.get(job_id):
                try:
                    await loop.run_in_executor(
                        None, 
                        download_with_ytdlp, 
                        cleaned_url, 
                        output_template, 
                        job_id, 
                        False
                    )
                    download_success = True
                except DownloadCancelledException:
                    return
                except Exception as e:
                    logger.warning(f"Universal engine notice: {e}")

        # Stop active progress loop
        loop_active = False
        progress_task.cancel()

        if ACTIVE_CANCELS.get(job_id):
            return

        downloaded_files = glob.glob(f"{temp_dir}/*")

        # Files <= 48 MB delivered in Telegram Chat with instant streaming
        if download_success and downloaded_files:
            video_path = downloaded_files[0]
            file_size = os.path.getsize(video_path)

            if file_size <= MAX_UPLOAD_LIMIT:
                DB["total_downloads"] += 1
                save_db()
                with open(video_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_file,
                        caption=f"🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{ADMIN_USERNAME}",
                        supports_streaming=True,
                        read_timeout=300,
                        write_timeout=300,
                        parse_mode=ParseMode.HTML
                    )
                try:
                    await proc_msg.delete()
                except Exception:
                    pass
                return

        # Large Files (>48 MB up to 500 MB): Deliver High-Speed Direct Download Link
        if not direct_stream_url:
            direct_stream_url = await loop.run_in_executor(None, fetch_direct_stream_url, cleaned_url)

        if direct_stream_url and not ACTIVE_CANCELS.get(job_id):
            DB["total_downloads"] += 1
            save_db()
            kb = [[InlineKeyboardButton("📥 Direct High-Speed Download (Full HD)", url=direct_stream_url)]]
            large_caption = (
                "📦 <b>Large Video File Detected! (> 50 MB)</b>\n\n"
                "Telegram restricts direct bot uploads over 50MB. Click below to download in original Full HD directly:"
            )
            try:
                if proc_msg.photo:
                    await proc_msg.edit_caption(caption=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await proc_msg.edit_text(text=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        # Extraction Failed
        fail_text = "❌ <b>Extraction Failed!</b>\n\nThe video may be private, age-restricted, or removed by the platform. Please verify the URL!"
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=fail_text, parse_mode=ParseMode.HTML)
            else:
                await proc_msg.edit_text(text=fail_text, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=fail_text, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.error(f"Execution Error: {exc}", exc_info=True)
        loop_active = False
        progress_task.cancel()
        err_msg = "⚠️ <b>Error processing video.</b> Please verify your URL and try again."
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=err_msg, parse_mode=ParseMode.HTML)
            else:
                await proc_msg.edit_text(text=err_msg, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=err_msg, parse_mode=ParseMode.HTML)

    finally:
        loop_active = False
        if not progress_task.done():
            progress_task.cancel()
        ACTIVE_CANCELS.pop(job_id, None)
        JOB_PROGRESS.pop(job_id, None)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# 14. Main Bootstrap Engine
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.critical("BOT_TOKEN is not configured!")
        return

    # Start 24/7 Render Keep-Alive Port Server
    threading.Thread(target=run_http_server, daemon=True).start()

    custom_request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=60.0
    )

    application = ApplicationBuilder().token(TOKEN).request(custom_request).post_init(set_menu_commands).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming_message))

    logger.info("Nahid Video Downloader Pro (Ultimate Edition) is officially LIVE!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()