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

TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"
BOT_LOGO_URL = "https://user55725.cn.imgto.link/public/20261113/fd75766042207998416adf8f-1000482026.avif"
MAX_UPLOAD_LIMIT = 48 * 1024 * 1024  # 48 MB Safe limit for direct Telegram upload
STATS_FILE = "stats.json"

# Track active download cancellations: {job_id: bool}
ACTIVE_CANCELS = {}

# ---------------------------------------------------------------------------
# 2. 18+ Witty & Engaging English Loading Messages
# ---------------------------------------------------------------------------
FUNNY_QUOTES = [
    "☕ Grab a cup of coffee! The server hamsters are running on overdrive...",
    "🐢 Move aside turtle, supersonic download packets incoming!",
    "🚀 Even Elon Musk's Falcon 9 is jealous of our packet speed!",
    "🥷 Sneaking past platform security guards like a cyber ninja...",
    "🧙‍♂️ Chanting digital spells: Abracadabra, pixels assemble right now!",
    "🍿 Getting the popcorn ready, your video is almost cooked!",
    "🏎️ Burning digital rubber on the information superhighway!",
    "🤖 Teaching platform algorithms some manners so they release your clip...",
    "💎 Polishing every frame so your video sparkles in crisp 60 FPS!",
    "🍕 Moving faster than someone who just heard 'free pizza in the lobby'!",
    "⚡ Our servers are drinking double-shot espressos right now...",
    "📦 Wrestling the high-definition stream into a neat package...",
    "🛸 Beaming down cosmic media packets straight to your chat...",
    "🎪 Juggling bits and bytes like a circus acrobat on a unicycle...",
    "🎯 Locking on target: Direct video delivery in 3... 2... 1...",
    "🎸 Shredding through server firewalls like an electric guitar solo!",
    "🏊‍♂️ Diving deep into the data ocean to fish out your video...",
    "🔋 Charging hyper-drive capacitors to maximum velocity!"
]

# ---------------------------------------------------------------------------
# 3. Persistent Database
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
# 4. Render 24/7 Keep-Alive HTTP Server
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
# 5. Media Scrapers & Sanitizers (YouTube, Facebook, Instagram, TikTok)
# ---------------------------------------------------------------------------
def sanitize_url(url: str) -> str:
    """Sanitizes YouTube, Facebook, and Instagram tracking redirects."""
    # YouTube / Shorts Sanitization
    if "youtube.com" in url or "youtu.be" in url:
        url = re.sub(r'(\?|\&)si=[^&]*', '', url)
        url = re.sub(r'(\?|\&)feature=[^&]*', '', url)
        # Convert /shorts/ID to standard /watch?v=ID for broad extractor support
        url = url.replace("/shorts/", "/watch?v=")
        return url

    # Facebook / Instagram Redirect Expansion
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

def scrape_facebook_layer1(url: str) -> str:
    """Layer 1: FDown Gateway Scraper (Bypasses Meta IP blocks)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
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
    except Exception as e:
        logger.warning(f"Facebook Layer 1 error: {e}")
    return None

def scrape_facebook_layer2(url: str) -> str:
    """Layer 2: Direct Mobile Stream Regex Scraper."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
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
    except Exception as e:
        logger.warning(f"Facebook Layer 2 error: {e}")
    return None

def download_stream_to_file(stream_url: str, save_path: str, job_id: str) -> bool:
    """Downloads extracted direct media stream with cancel hook support."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with requests.get(stream_url, headers=headers, stream=True, timeout=35) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if ACTIVE_CANCELS.get(job_id):
                        return False
                    if chunk:
                        f.write(chunk)
        return os.path.exists(save_path) and os.path.getsize(save_path) > 1000
    except Exception as e:
        logger.warning(f"Stream download error: {e}")
        return False

def download_tiktok_tikwm(url: str, save_path: str, job_id: str) -> bool:
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            v_url = res["data"]["play"]
            return download_stream_to_file(v_url, save_path, job_id)
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# 6. High-Precision yt-dlp Engine with Anti-Bot Spoofing & Live Progress
# ---------------------------------------------------------------------------
class DownloadCancelledException(Exception):
    pass

def download_with_ytdlp(url: str, output_path: str, job_id: str, progress_callback=None):
    """
    Permanent YouTube & Multi-Platform fix:
    - Android/iOS/mweb client spoofing eliminates 'Sign in to confirm' errors.
    - Captures live progress data and passes to callback for Telegram UI updates.
    """
    def hook(d):
        if ACTIVE_CANCELS.get(job_id):
            raise DownloadCancelledException("Download cancelled by user.")
        if progress_callback and d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            progress_callback(downloaded, total, speed, eta)

    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'progress_hooks': [hook],
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
# 7. Live Dynamic Progress UI Builder
# ---------------------------------------------------------------------------
def make_progress_bar(pct: float) -> str:
    filled = int(pct // 8.33)  # 12 blocks
    empty = 12 - filled
    return "█" * filled + "░" * empty

def format_live_progress_text(downloaded: int, total: int, speed: float, eta: int, quote: str) -> str:
    pct = (downloaded / total * 100) if total > 0 else 0.0
    bar = make_progress_bar(pct)
    
    dl_mb = downloaded / (1024 * 1024)
    tot_mb = total / (1024 * 1024) if total > 0 else 0.0
    spd_mb = speed / (1024 * 1024) if speed > 0 else 0.0
    
    eta_str = f"{int(eta)}s" if eta else "Calculating..."
    size_str = f"{dl_mb:.1f} / {tot_mb:.1f} MB" if tot_mb > 0 else f"{dl_mb:.1f} MB"

    return (
        "⚡ <b>NAHID VIDEO DOWNLOADER PRO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📥 <b>Status:</b> <i>Downloading Media...</i>\n"
        f"📊 <b>Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n"
        f"💾 <b>Size:</b> <code>{size_str}</code>\n"
        f"🚀 <b>Speed:</b> <code>{spd_mb:.1f} MB/s</code> | ⏳ <b>ETA:</b> <code>{eta_str}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>\"{quote}\"</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <i>Engine: Multi-Tier Turbo Gateway</i>"
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
# 8. Global UI Keyboards & Menus (100% Professional English)
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
# 9. Command Handlers
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
        "• <b>YouTube</b> (Shorts & Standard Videos)\n"
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
        "🟢 <b>Server Status:</b> <code>Online 24/7 (Turbo)</code>\n"
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
# 10. Interactive Button Callbacks
# ---------------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    # Cancel Download Button Handler
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

    # Legacy & Current Button Resolver
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
            "3. Videos under <b>50 MB</b> will be delivered straight into this chat.\n"
            "4. Large videos (>50 MB up to 500 MB) generate a high-speed direct download link."
        )
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_admin":
        context.user_data["feedback_mode"] = False
        if user.id == ADMIN_ID:
            stats_text = (
                "🛠️ <b>Master Developer Control Panel</b>\n\n"
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
# 11. Core Message Handler (YouTube Fix, Live Progress & Multi-Tier Engines)
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

    # User Feedback Routing (Direct to Admin 8815124111)
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

    # Extract URL
    urls = re.findall(r'(https?://\S+)', raw_text)

    # Smart Non-link Auto-Delete & 5-Second Warning
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

    # Delete User's Link Instantly to keep chat spotless
    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]
    job_id = uuid.uuid4().hex[:8]
    ACTIVE_CANCELS[job_id] = False

    # Send Initial Live Progress Card
    initial_quote = random.choice(FUNNY_QUOTES)
    initial_text = format_live_progress_text(0, 0, 0, 0, initial_quote)
    proc_msg = await send_banner_safe(
        chat_id=chat_id, 
        caption=initial_text, 
        reply_markup=build_cancel_keyboard(job_id), 
        context=context
    )

    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    # Live Throttled UI Progress Updater
    loop = asyncio.get_running_loop()
    last_update = {'time': 0, 'quote': initial_quote}

    def sync_progress_hook(downloaded, total, speed, eta):
        now = time.time()
        # Update at most once every 2.0 seconds to prevent Telegram flood limits
        if now - last_update['time'] >= 2.0:
            last_update['time'] = now
            last_update['quote'] = random.choice(FUNNY_QUOTES)
            card_text = format_live_progress_text(downloaded, total, speed, eta, last_update['quote'])
            
            async def update_ui():
                try:
                    if proc_msg.photo:
                        await proc_msg.edit_caption(
                            caption=card_text, 
                            parse_mode=ParseMode.HTML, 
                            reply_markup=build_cancel_keyboard(job_id)
                        )
                    else:
                        await proc_msg.edit_text(
                            text=card_text, 
                            parse_mode=ParseMode.HTML, 
                            reply_markup=build_cancel_keyboard(job_id)
                        )
                except Exception:
                    pass

            asyncio.run_coroutine_threadsafe(update_ui(), loop)

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        cleaned_url = sanitize_url(target_url)
        download_success = False
        direct_stream_url = None

        # -------------------------------------------------------------------
        # 1. YOUTUBE EXTRACTION ENGINE (Permanent Anti-Bot Fix)
        # -------------------------------------------------------------------
        if "youtube.com" in cleaned_url or "youtu.be" in cleaned_url:
            try:
                await loop.run_in_executor(
                    None, 
                    download_with_ytdlp, 
                    cleaned_url, 
                    output_template, 
                    job_id, 
                    sync_progress_hook
                )
                download_success = True
            except DownloadCancelledException:
                return
            except Exception as e:
                logger.warning(f"YouTube primary error: {e}")

        # -------------------------------------------------------------------
        # 2. FACEBOOK EXTRACTION ENGINE (Quad-Layer Bypasses)
        # -------------------------------------------------------------------
        elif "facebook.com" in target_url or "fb.watch" in target_url:
            # Layer 1: FDown Scraper
            stream_l1 = await loop.run_in_executor(None, scrape_facebook_layer1, cleaned_url)
            if stream_l1 and not ACTIVE_CANCELS.get(job_id):
                direct_stream_url = stream_l1
                fb_file = str(temp_dir / "fb_video.mp4")
                download_success = await loop.run_in_executor(None, download_stream_to_file, stream_l1, fb_file, job_id)

            # Layer 2: Mobile Native Regex
            if not download_success and not ACTIVE_CANCELS.get(job_id):
                stream_l2 = await loop.run_in_executor(None, scrape_facebook_layer2, cleaned_url)
                if stream_l2:
                    direct_stream_url = stream_l2
                    fb_file = str(temp_dir / "fb_video.mp4")
                    download_success = await loop.run_in_executor(None, download_stream_to_file, stream_l2, fb_file, job_id)

            # Layer 3: yt-dlp fallback
            if not download_success and not ACTIVE_CANCELS.get(job_id):
                try:
                    await loop.run_in_executor(
                        None, 
                        download_with_ytdlp, 
                        cleaned_url, 
                        output_template, 
                        job_id, 
                        sync_progress_hook
                    )
                    download_success = True
                except DownloadCancelledException:
                    return
                except Exception as e:
                    logger.warning(f"FB yt-dlp fallback error: {e}")

        # -------------------------------------------------------------------
        # 3. INSTAGRAM, TIKTOK, TWITTER & OTHERS
        # -------------------------------------------------------------------
        else:
            # TikTok TikWM Fallback First
            if "tiktok.com" in cleaned_url or "douyin.com" in cleaned_url:
                tiktok_file = str(temp_dir / "tiktok_video.mp4")
                download_success = await loop.run_in_executor(None, download_tiktok_tikwm, cleaned_url, tiktok_file, job_id)

            # Primary Multi-platform Engine
            if not download_success and not ACTIVE_CANCELS.get(job_id):
                try:
                    await loop.run_in_executor(
                        None, 
                        download_with_ytdlp, 
                        cleaned_url, 
                        output_template, 
                        job_id, 
                        sync_progress_hook
                    )
                    download_success = True
                except DownloadCancelledException:
                    return
                except Exception as e:
                    logger.warning(f"Universal engine error: {e}")

        # If user cancelled during processing
        if ACTIVE_CANCELS.get(job_id):
            return

        downloaded_files = glob.glob(f"{temp_dir}/*")

        # Files <= 48 MB delivered in Telegram Chat with player streaming
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

        # Extraction Failed Notification
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
        err_msg = "⚠️ <b>Error processing video.</b> Please verify your URL and try again."
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=err_msg, parse_mode=ParseMode.HTML)
            else:
                await proc_msg.edit_text(text=err_msg, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=err_msg, parse_mode=ParseMode.HTML)

    finally:
        ACTIVE_CANCELS.pop(job_id, None)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# 12. Main Bootstrap Engine
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

    logger.info("Nahid Video Downloader Pro is 100% ONLINE and READY!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()