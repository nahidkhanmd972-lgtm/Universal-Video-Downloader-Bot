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
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("NahidDownloaderPro")

# Credentials & Config
TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "youtube-media-downloader.p.rapidapi.com")
GENERIC_API_HOST = os.getenv("GENERIC_API_HOST", "")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8815124111"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "NahidDevOfficial")

# Custom 3D Animated Logo URL provided by user
BOT_LOGO_URL = os.getenv(
    "BOT_LOGO_URL",
    "https://user55725.cn.imgto.link/public/20261113/3b13a0dfe6eaa21ad1c15b4f-1000483594.avif"
)

MAX_UPLOAD_LIMIT = 48 * 1024 * 1024  # 48 MB Safe Limit
STATS_FILE = "stats.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

ACTIVE_CANCELS = {}
JOB_PROGRESS = {}

# ---------------------------------------------------------------------------
# 2. 20 Witty Fun Quotes (Dynamic Loading Messages)
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
    "💎 Polishing every frame so your video sparkles in crisp clarity!",
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
# 3. Multi-Language Support (English, Bengali, Malay)
# ---------------------------------------------------------------------------
LANG_NAMES = {
    "en": "🇬🇧 English", "bn": "🇧🇩 বাংলা", "ms": "🇲🇾 Melayu"
}

L10N = {
    "en": {
        "welcome": (
            "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
            "⚡ <b>The Ultimate Global Media Downloader</b>\n"
            "Drop any public video link from YouTube, Facebook, Instagram, or TikTok to download instantly!\n\n"
            "👇 <i>Use the dashboard below or send any link:</i>"
        ),
        "btn_profile": "👤 My Profile", "btn_stats": "📊 Live Statistics", "btn_guide": "ℹ️ User Guide",
        "btn_lang": "🌐 Language", "btn_feedback": "✍️ Feedback", "btn_admin": "💬 Admin",
        "btn_back": "🔙 Back", "btn_cancel": "❌ Cancel", "btn_dl": "📥 Direct High-Speed Download",
        "btn_portal": "🌐 Open Web Portal",
        "stats": "📊 <b>Global Stats</b>\n\n👥 Users: <code>{users:,}</code>\n📥 Processed: <code>{downloads:,}</code>\n🟢 Status: <code>Online 24/7</code>",
        "guide": "📌 <b>Quick Guide:</b>\n1. Send any video link.\n2. Under 50MB comes directly to chat.\n3. Large files generate a fast direct download link.",
        "choose_lang": "🌐 <b>Choose your language:</b>",
        "lang_changed": "✅ <b>Language updated successfully!</b>",
        "feedback_prompt": "✍️ <b>Send Feedback</b>\nType your message below for the admin:",
        "feedback_ok": "✅ <b>Thank you!</b> Message sent to admin.",
        "invalid": "🚨 <b>Hey! This isn't a chatroom! 😂</b>\nPlease send a valid <b>YouTube, Facebook, TikTok, or Instagram</b> link!",
        "delivered": "🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>Large Video File Detected!</b>\nTelegram restricts uploads over 50MB. Click below to download directly:",
        "failed": "❌ <b>Extraction Failed!</b>\nThe video may be private or restricted. Try the backup web portal below:",
        "cancelled": "❌ <b>Download Cancelled!</b>", "status": "Downloading High-Speed Media...",
    },
    "bn": {
        "welcome": (
            "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀\n\n"
            "⚡ YouTube, Facebook, Instagram বা TikTok-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠান।\n\n👇 নিচের মেনু ব্যবহার করুন বা লিংক পেস্ট করুন।"
        ),
        "btn_profile": "👤 আমার প্রোফাইল", "btn_stats": "📊 লাইভ পরিসংখ্যান", "btn_guide": "ℹ️ ব্যবহারবিধি",
        "btn_lang": "🌐 ভাষা", "btn_feedback": "✍️ মতামত", "btn_admin": "💬 অ্যাডমিন",
        "btn_back": "🔙 ফিরে যান", "btn_cancel": "❌ বাতিল", "btn_dl": "📥 সরাসরি ডাউনলোড করুন",
        "btn_portal": "🌐 ওয়েব পোর্টাল",
        "stats": "📊 <b>লাইভ পরিসংখ্যান</b>\n\n👥 ব্যবহারকারী: <code>{users:,}</code>\n📥 ডাউনলোড: <code>{downloads:,}</code>\n🟢 সার্ভার: <code>Online 24/7</code>",
        "guide": "📌 <b>ব্যবহারবিধি</b>\n১. যেকোনো ভিডিওর লিংক দিন।\n২. ৫০MB-এর কম হলে চ্যাটেই পাবেন।\n৩. বড় হলে ডাইরেক্ট ডাউনলোড বাটন আসবে।",
        "choose_lang": "🌐 <b>আপনার ভাষা বেছে নিন:</b>",
        "lang_changed": "✅ <b>ভাষা পরিবর্তন হয়েছে!</b>",
        "feedback_prompt": "✍️ <b>মতামত লিখুন</b>\nআপনার মেসেজ সরাসরি অ্যাডমিনের কাছে যাবে:",
        "feedback_ok": "✅ <b>ধন্যবাদ!</b> অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "invalid": "🚨 <b>আরে ভাই! সঠিক ভিডিও লিংক পাঠান! 😂</b>",
        "delivered": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>ভিডিও ফাইলের সাইজ বড়!</b>\nনিচের বাটনে ক্লিক করে সরাসরি ডাউনলোড করে নিন:",
        "failed": "❌ <b>ভিডিও আনা যায়নি!</b>\nভিডিওটি প্রাইভেট বা রেস্ট্রিক্টেড হতে পারে। নিচের ওয়েব পোর্টাল ট্রাই করুন:",
        "cancelled": "❌ <b>ডাউনলোড বাতিল করা হয়েছে!</b>", "status": "ডাউনলোড হচ্ছে...",
    },
    "ms": {
        "welcome": (
            "Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀\n\n"
            "⚡ Hantar pautan video dari YouTube, Facebook, Instagram atau TikTok.\n\n👇 Hantar pautan di bawah:"
        ),
        "btn_profile": "👤 Profil Saya", "btn_stats": "📊 Statistik", "btn_guide": "ℹ️ Panduan",
        "btn_lang": "🌐 Bahasa", "btn_feedback": "✍️ Maklum Balas", "btn_admin": "💬 Admin",
        "btn_back": "🔙 Kembali", "btn_cancel": "❌ Batal", "btn_dl": "📥 Muat Turun Pantas",
        "btn_portal": "🌐 Portal Web",
        "stats": "📊 <b>Statistik</b>\n\n👥 Pengguna: <code>{users:,}</code>\n📥 Muat Turun: <code>{downloads:,}</code>",
        "guide": "📌 <b>Panduan:</b> Hantar pautan video untuk muat turun segera.",
        "choose_lang": "🌐 <b>Pilih bahasa anda:</b>",
        "lang_changed": "✅ <b>Bahasa ditukar!</b>",
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas:</b>",
        "feedback_ok": "✅ <b>Terima kasih!</b>",
        "invalid": "🚨 Sila hantar pautan video yang sah!",
        "delivered": "🎬 <b>Video Berjaya Dimuat Turun!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>Fail Besar!</b> Sila muat turun melalui pautan di bawah:",
        "failed": "❌ <b>Gagal memuat turun!</b> Sila cuba portal web:",
        "cancelled": "❌ <b>Dibatalkan.</b>", "status": "Sedang dimuat turun...",
    }
}

# ---------------------------------------------------------------------------
# 4. Persistent Database Handler
# ---------------------------------------------------------------------------
def load_db():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {
                    "total_downloads": d.get("total_downloads", 0),
                    "unique_users": set(d.get("unique_users", [])),
                    "user_langs": d.get("user_langs", {})
                }
        except Exception:
            pass
    return {"total_downloads": 0, "unique_users": set(), "user_langs": {}}

def save_db():
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "total_downloads": DB["total_downloads"],
                "unique_users": list(DB["unique_users"]),
                "user_langs": DB["user_langs"]
            }, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to persist DB: {e}")

DB = load_db()

def get_lang(uid: int) -> str:
    return DB["user_langs"].get(str(uid), "en")

def tr(uid: int, key: str) -> str:
    return L10N.get(get_lang(uid), {}).get(key) or L10N["en"].get(key, "")

# ---------------------------------------------------------------------------
# 5. Render / Bot-Hosting 24/7 Keep-Alive HTTP Daemon
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
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

# ---------------------------------------------------------------------------
# 6. URL Processing & Fallbacks
# ---------------------------------------------------------------------------
def is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def extract_youtube_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", url)
    return m.group(1) if m else None

def sanitize_youtube_url(url: str) -> str:
    vid = extract_youtube_id(url)
    return f"https://www.youtube.com/watch?v={vid}" if vid else url

def clean_social_url(url: str) -> str:
    return url.split("?")[0].strip()

def get_web_portal_link(url: str) -> str:
    if is_youtube(url):
        return f"https://ssyoutube.com/watch?v={extract_youtube_id(url) or ''}"
    if "facebook.com" in url or "fb.watch" in url:
        return f"https://fdown.net/download.php?URLz={url}"
    if "instagram.com" in url:
        return "https://fastdl.app/"
    if "tiktok.com" in url:
        return "https://snaptik.app/"
    return url

# ---------------------------------------------------------------------------
# 7. RapidAPI & Scraper Gateways
# ---------------------------------------------------------------------------
def rapidapi_youtube_links(url: str) -> list:
    vid = extract_youtube_id(url)
    if not (RAPIDAPI_KEY and vid):
        return []
    try:
        r = requests.get(
            f"https://{RAPIDAPI_HOST}/v2/video/details",
            params={"videoId": vid},
            headers={"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST},
            timeout=25,
        )
        if r.status_code == 200:
            items = (r.json().get("videos") or {}).get("items") or []
            items = [i for i in items if i.get("url") and i.get("hasAudio", True)]
            return [i["url"] for i in items]
    except Exception as e:
        logger.warning(f"RapidAPI YT Error: {e}")
    return []

def generic_api_link(url: str):
    if not (RAPIDAPI_KEY and GENERIC_API_HOST):
        return None
    try:
        endpoint = f"https://{GENERIC_API_HOST}/"
        headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": GENERIC_API_HOST, "Content-Type": "application/json"}
        r = requests.post(endpoint, json={"url": url}, headers=headers, timeout=15)
        if r.status_code != 200:
            r = requests.get(endpoint, params={"url": url}, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("download_url") or data.get("url") or data.get("video")
    except Exception as e:
        logger.warning(f"Generic API Error: {e}")
    return None

def tikwm_link(url: str):
    try:
        res = requests.get("https://tikwm.com/api/", params={"url": url}, timeout=10).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# 8. Adaptive Downloader & Stream Engine
# ---------------------------------------------------------------------------
class DownloadCancelledException(Exception):
    pass

def download_stream_with_progress(stream_url: str, save_path: str, job_id: str) -> str:
    try:
        with requests.get(stream_url, headers={"User-Agent": UA}, stream=True, timeout=35) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            if total_size > MAX_UPLOAD_LIMIT:
                return "big"
            downloaded = 0
            start_time = time.time()
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 512):
                    if ACTIVE_CANCELS.get(job_id):
                        return "fail"
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_UPLOAD_LIMIT:
                        return "big"
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    eta = (total_size - downloaded) / speed if speed > 0 and total_size > downloaded else 0
                    JOB_PROGRESS[job_id] = {"downloaded": downloaded, "total": total_size, "speed": speed, "eta": eta}
        return "ok" if os.path.exists(save_path) and os.path.getsize(save_path) > 1000 else "fail"
    except Exception:
        return "fail"

def download_with_ytdlp(url: str, output_path: str, job_id: str):
    def hook(d):
        if ACTIVE_CANCELS.get(job_id):
            raise DownloadCancelledException("Cancelled")
        if d["status"] == "downloading":
            JOB_PROGRESS[job_id] = {
                "downloaded": d.get("downloaded_bytes") or 0,
                "total": d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
                "speed": d.get("speed") or 0,
                "eta": d.get("eta") or 0,
            }

    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "progress_hooks": [hook],
        "http_headers": {"User-Agent": UA},
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb"]}},
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)

def fetch_direct_stream_url(url: str):
    opts = {
        "format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True, "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb"]}},
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("url") or (info.get("requested_formats") and info["requested_formats"][0].get("url"))

# ---------------------------------------------------------------------------
# 9. UI & Progress Formatter
# ---------------------------------------------------------------------------
def format_live_progress