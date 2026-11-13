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
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from telegram.request import HTTPXRequest

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("NahidDownloaderPro")

TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "youtube-media-downloader.p.rapidapi.com")
GENERIC_API_HOST = os.getenv("GENERIC_API_HOST", "")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8815124111"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "NahidDevOfficial")
BOT_LOGO_URL = os.getenv(
    "BOT_LOGO_URL",
    "https://user55725.cn.imgto.link/public/20261113/fd75766042207998416adf8f-1000482026.avif",
)
MAX_UPLOAD_LIMIT = 48 * 1024 * 1024
LONG_VIDEO_SECONDS = 600  # YouTube videos longer than this get an HD direct link
STATS_FILE = "stats.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

ACTIVE_CANCELS = {}
JOB_PROGRESS = {}

FUNNY_QUOTES = [
    "☕ Grab a coffee! Our server hamsters are on nitro overdrive...",
    "🐢 Move aside turtle! Supersonic packets incoming!",
    "🚀 Even a Falcon 9 would envy this transfer speed!",
    "🥷 Sneaking past platform guards like a cyber ninja...",
    "🧙‍♂️ Abracadabra, pixels assemble!",
    "🍿 Popcorn ready, your video is almost cooked!",
    "🏎️ Burning rubber on the data superhighway!",
    "💎 Polishing every frame until it sparkles!",
    "🍕 Faster than 'free pizza in the lobby'!",
    "⚡ Our cloud servers are on double espresso...",
    "📦 Wrapping your stream into a clean MP4...",
    "🛸 Beaming media packets straight to your chat...",
    "🎯 Locking on target: delivery in 3... 2... 1...",
    "🔋 Charging hyper-drive capacitors to max...",
    "🏁 Almost at the finish line! Finalizing...",
]

# ---------------------------------------------------------------------------
# Languages: English (default), Bengali, Malay. Missing keys fall back to English.
# ---------------------------------------------------------------------------
LANG_NAMES = {"en": "🇬🇧 English", "bn": "🇧🇩 বাংলা", "ms": "🇲🇾 Melayu"}

EN = {
    "welcome": (
        "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
        "⚡ Send any public video link and I will download it in HD.\n\n"
        "🌐 <b>Supported:</b> YouTube, Facebook, Instagram, TikTok, X/Twitter and more.\n\n"
        "👇 <i>Paste a link or use the menu below:</i>"
    ),
    "btn_profile": "👤 My Profile", "btn_stats": "📊 Live Statistics", "btn_guide": "ℹ️ User Guide",
    "btn_lang": "🌐 Language", "btn_feedback": "✍️ Feedback / Report", "btn_admin": "💬 Contact Admin",
    "btn_back": "🔙 Back to Menu", "btn_master": "🛠️ Admin Master Panel", "btn_cancel": "❌ Cancel",
    "btn_dl": "📥 Direct HD Download", "btn_portal": "🌐 Open Web Download Portal",
    "stats": (
        "📊 <b>Global Stats</b>\n\n"
        "👥 <b>Total Users:</b> <code>{users:,}</code>\n"
        "📥 <b>Total Downloads:</b> <code>{downloads:,}</code>\n"
        "🟢 <b>Server:</b> <code>Online 24/7</code>"
    ),
    "profile": (
        "👤 <b>My Profile</b>\n\n"
        "• <b>Name:</b> {name}\n• <b>User ID:</b> <code>{user_id}</code>\n• <b>Language:</b> {lang}"
    ),
    "guide": (
        "📌 <b>Quick Guide</b>\n\n"
        "1. Copy a video link (YouTube, Facebook, Instagram, TikTok).\n"
        "2. Paste it here.\n"
        "3. Small videos (under 50 MB) are sent right in the chat.\n"
        "4. Big videos get a direct HD download link."
    ),
    "choose_lang": "🌐 <b>Choose your language:</b>",
    "lang_changed": "✅ <b>Language changed!</b>",
    "feedback_prompt": "✍️ <b>Send Feedback</b>\nType your message below. It goes straight to the admin:",
    "feedback_ok": "✅ <b>Thank you!</b> Your message was sent to the admin.",
    "invalid": "🚨 <b>Please send a valid YouTube, Facebook, Instagram or TikTok link!</b>",
    "delivered": "🎬 <b>Video delivered!</b>\n📥 Powered by @{admin}",
    "large": "📦 <b>Large video (over 50 MB)</b>\n\nTelegram limits bot uploads. Tap below to download in HD:",
    "failed": "❌ <b>Extraction failed!</b>\n\nThe video may be private, age-restricted or removed. Try the web portal below:",
    "cancelled": "❌ <b>Download cancelled.</b>",
    "status": "Downloading...",
}

L10N = {
    "bn": {
        "welcome": "👋 স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>!\n\n⚡ YouTube, Facebook, Instagram বা TikTok-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠান, আমি HD-তে নামিয়ে দেব।\n\n👇 নিচের মেনু ব্যবহার করুন বা লিংক পেস্ট করুন।",
        "btn_profile": "👤 আমার প্রোফাইল", "btn_stats": "📊 পরিসংখ্যান", "btn_guide": "ℹ️ ব্যবহারবিধি",
        "btn_lang": "🌐 ভাষা", "btn_feedback": "✍️ মতামত / সমস্যা", "btn_admin": "💬 অ্যাডমিন",
        "btn_back": "🔙 ফিরে যান", "btn_cancel": "❌ বাতিল", "btn_dl": "📥 সরাসরি HD ডাউনলোড",
        "btn_portal": "🌐 ওয়েব ডাউনলোড পোর্টাল",
        "stats": "📊 <b>পরিসংখ্যান</b>\n\n👥 ব্যবহারকারী: <code>{users:,}</code>\n📥 ডাউনলোড: <code>{downloads:,}</code>\n🟢 সার্ভার: <code>Online 24/7</code>",
        "profile": "👤 <b>আমার প্রোফাইল</b>\n\n• <b>নাম:</b> {name}\n• <b>ইউজার আইডি:</b> <code>{user_id}</code>\n• <b>ভাষা:</b> {lang}",
        "guide": "📌 <b>ব্যবহারবিধি</b>\n\n১. ভিডিওর লিংক কপি করুন।\n২. এখানে পেস্ট করুন।\n৩. ৫০MB-এর কম হলে চ্যাটেই ভিডিও পাবেন।\n৪. বড় ভিডিওর জন্য ডাইরেক্ট HD লিংক পাবেন।",
        "choose_lang": "🌐 <b>আপনার ভাষা বেছে নিন:</b>", "lang_changed": "✅ <b>ভাষা পরিবর্তন হয়েছে!</b>",
        "feedback_prompt": "✍️ <b>মতামত লিখুন</b>\nআপনার মেসেজ সরাসরি অ্যাডমিনের কাছে যাবে:",
        "feedback_ok": "✅ <b>ধন্যবাদ!</b> অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "invalid": "🚨 <b>সঠিক YouTube, Facebook, Instagram বা TikTok লিংক পাঠান!</b>",
        "delivered": "🎬 <b>ভিডিও পাঠানো হয়েছে!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>ভিডিও বড় (৫০MB-এর বেশি)</b>\n\nনিচের বাটনে চাপ দিয়ে HD-তে ডাউনলোড করুন:",
        "failed": "❌ <b>ভিডিও আনা যায়নি!</b>\n\nভিডিওটি প্রাইভেট বা মুছে ফেলা হতে পারে। ওয়েব পোর্টাল চেষ্টা করুন:",
        "cancelled": "❌ <b>ডাউনলোড বাতিল হয়েছে।</b>", "status": "ডাউনলোড হচ্ছে...",
    },
    "ms": {
        "welcome": "👋 Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n⚡ Hantar pautan video awam dari YouTube, Facebook, Instagram atau TikTok untuk muat turun dalam HD.\n\n👇 Tampal pautan atau guna menu di bawah.",
        "btn_profile": "👤 Profil Saya", "btn_stats": "📊 Statistik", "btn_guide": "ℹ️ Panduan",
        "btn_lang": "🌐 Bahasa", "btn_feedback": "✍️ Maklum Balas", "btn_admin": "💬 Hubungi Admin",
        "btn_back": "🔙 Kembali", "btn_cancel": "❌ Batal", "btn_dl": "📥 Muat Turun HD Terus",
        "btn_portal": "🌐 Portal Muat Turun Web",
        "stats": "📊 <b>Statistik</b>\n\n👥 Pengguna: <code>{users:,}</code>\n📥 Muat turun: <code>{downloads:,}</code>\n🟢 Pelayan: <code>Online 24/7</code>",
        "profile": "👤 <b>Profil Saya</b>\n\n• <b>Nama:</b> {name}\n• <b>ID:</b> <code>{user_id}</code>\n• <b>Bahasa:</b> {lang}",
        "guide": "📌 <b>Panduan</b>\n\n1. Salin pautan video.\n2. Tampal di sini.\n3. Video bawah 50 MB dihantar dalam sembang.\n4. Video besar mendapat pautan HD terus.",
        "choose_lang": "🌐 <b>Pilih bahasa anda:</b>", "lang_changed": "✅ <b>Bahasa ditukar!</b>",
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas</b>\nTaip mesej anda di bawah:",
        "feedback_ok": "✅ <b>Terima kasih!</b> Mesej dihantar kepada admin.",
        "invalid": "🚨 <b>Sila hantar pautan YouTube, Facebook, Instagram atau TikTok yang sah!</b>",
        "delivered": "🎬 <b>Video dihantar!</b>\n📥 Dikuasakan oleh @{admin}",
        "large": "📦 <b>Video besar (lebih 50 MB)</b>\n\nTekan butang untuk muat turun HD:",
        "failed": "❌ <b>Video tidak dapat diambil!</b>\n\nCuba portal web di bawah:",
        "cancelled": "❌ <b>Dibatalkan.</b>", "status": "Sedang memuat turun...",
    },
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def load_db():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {
                    "total_downloads": d.get("total_downloads", 0),
                    "unique_users": set(d.get("unique_users", [])),
                    "user_langs": d.get("user_langs", {}),
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
                "user_langs": DB["user_langs"],
            }, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to persist DB: {e}")

DB = load_db()

def get_lang(uid: int) -> str:
    return DB["user_langs"].get(str(uid), "en")

def tr(uid: int, key: str) -> str:
    return L10N.get(get_lang(uid), {}).get(key) or EN.get(key, "")

# ---------------------------------------------------------------------------
# Keep-alive server
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nahid Video Downloader Pro - Active")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

# ---------------------------------------------------------------------------
# URL helpers
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
    clean = url.split("?")[0].strip()
    if any(k in url for k in ["facebook.com/share", "fb.watch", "facebook.com/reel"]):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15"},
                allow_redirects=True, timeout=8,
            )
            resolved = r.url.split("?")[0]
            if "facebook.com" in resolved:
                return resolved
        except Exception:
            pass
    return clean if clean.startswith("http") else url

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
# Stream downloader -> "ok" | "big" | "fail"
# ---------------------------------------------------------------------------
def download_stream_with_progress(stream_url: str, save_path: str, job_id: str) -> str:
    try:
        with requests.get(stream_url, headers={"User-Agent": UA}, stream=True, timeout=40) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            if total_size > MAX_UPLOAD_LIMIT:
                return "big"
            downloaded = 0
            start = time.time()
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
                    el = time.time() - start
                    speed = downloaded / el if el > 0 else 0
                    eta = (total_size - downloaded) / speed if speed > 0 and total_size > downloaded else 0
                    JOB_PROGRESS[job_id] = {"downloaded": downloaded, "total": total_size, "speed": speed, "eta": eta}
        return "ok" if os.path.exists(save_path) and os.path.getsize(save_path) > 1000 else "fail"
    except Exception as e:
        logger.warning(f"Stream download error: {e}")
        return "fail"

# ---------------------------------------------------------------------------
# Scrapers / APIs
# ---------------------------------------------------------------------------
def rapidapi_youtube(url: str) -> dict:
    """Returns {"small": [urls <=480p], "hd": best url <=1080p, "duration": seconds}."""
    empty = {"small": [], "hd": None, "duration": 0}
    vid = extract_youtube_id(url)
    if not (RAPIDAPI_KEY and vid):
        return empty
    try:
        r = requests.get(
            f"https://{RAPIDAPI_HOST}/v2/video/details",
            params={"videoId": vid},
            headers={"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST},
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning(f"RapidAPI YouTube status {r.status_code}: {r.text[:200]}")
            return empty
        j = r.json()
        items = (j.get("videos") or {}).get("items") or []
        items = [i for i in items if i.get("url") and i.get("hasAudio", True)]
        h = lambda i: int(i.get("height") or 0)
        small = sorted([i for i in items if 0 < h(i) <= 480], key=h, reverse=True)
        hd_pool = sorted([i for i in items if h(i) <= 1080], key=h, reverse=True) or sorted(items, key=h)
        try:
            duration = int(j.get("lengthSeconds") or 0)
        except Exception:
            duration = 0
        return {
            "small": [i["url"] for i in small],
            "hd": hd_pool[0]["url"] if hd_pool else None,
            "duration": duration,
        }
    except Exception as e:
        logger.warning(f"RapidAPI YouTube error: {e}")
        return empty

def generic_api_link(url: str):
    if not (RAPIDAPI_KEY and GENERIC_API_HOST):
        return None
    try:
        endpoint = f"https://{GENERIC_API_HOST}/"
        headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": GENERIC_API_HOST, "Content-Type": "application/json"}
        r = requests.post(endpoint, json={"url": url}, headers=headers, timeout=20)
        if r.status_code != 200:
            r = requests.get(endpoint, params={"url": url}, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            dl = data.get("download_url") or data.get("url") or data.get("video")
            if not dl and data.get("medias"):
                dl = data["medias"][0].get("url")
            return dl
    except Exception as e:
        logger.warning(f"Generic API error: {e}")
    return None

def scrape_facebook_layer1(url: str):
    try:
        headers = {"User-Agent": UA, "Referer": "https://fdown.net/", "Origin": "https://fdown.net",
                   "Content-Type": "application/x-www-form-urlencoded"}
        res = requests.post("https://fdown.net/download.php", data={"URLz": url}, headers=headers, timeout=12)
        if res.status_code == 200:
            for pid in ("hdlink", "sdlink"):
                m = re.search(rf'id=["\']{pid}["\'][^>]*href=["\']([^"\']+)["\']', res.text)
                if m:
                    return m.group(1).replace("&amp;", "&")
    except Exception:
        pass
    return None

def scrape_facebook_layer2(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)",
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        html = requests.get(url, headers=headers, allow_redirects=True, timeout=10).text
        patterns = [
            r'"browser_native_hd_url":"(https:[^"]+)"', r'"browser_native_sd_url":"(https:[^"]+)"',
            r'"playable_url_quality_hd":"(https:[^"]+)"', r'"playable_url":"(https:[^"]+)"',
            r'hd_src:"([^"]+)"', r'sd_src:"([^"]+)"',
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                raw = m.group(1).replace("\\/", "/").replace("&amp;", "&")
                try:
                    raw = json.loads(f'"{raw}"')
                except Exception:
                    pass
                if raw.startswith("http"):
                    return raw
    except Exception:
        pass
    return None

def tikwm_link(url: str):
    try:
        res = requests.get("https://tikwm.com/api/", params={"url": url}, timeout=12).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# yt-dlp
# ---------------------------------------------------------------------------
class DownloadCancelledException(Exception):
    pass

def download_with_ytdlp(url: str, output_path: str, job_id: str, is_yt: bool = False):
    def hook(d):
        if ACTIVE_CANCELS.get(job_id):
            raise DownloadCancelledException("cancelled")
        if d["status"] == "downloading":
            JOB_PROGRESS[job_id] = {
                "downloaded": d.get("downloaded_bytes") or 0,
                "total": d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
                "speed": d.get("speed") or 0, "eta": d.get("eta") or 0,
            }

    if is_yt:
        fmt = ("bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
               "best[height<=480][ext=mp4]/best[height<=480]/best")
    else:
        fmt = "b[ext=mp4]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best"

    opts = {
        "format": fmt, "outtmpl": output_path, "merge_output_format": "mp4",
        "quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30,
        "progress_hooks": [hook], "max_filesize": MAX_UPLOAD_LIMIT,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb"]}},
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)

def fetch_direct_stream_url(url: str):
    opts = {
        "format": "best[height<=1080][ext=mp4]/best[ext=mp4]/best",
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb"]}},
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("url") or (info.get("requested_formats") and info["requested_formats"][0].get("url"))

# ---------------------------------------------------------------------------
# Progress UI
# ---------------------------------------------------------------------------
EQUALIZER_WAVES = [" ▂▃▅▆▇█▇▆▅▃▂ ", "▃▅▆▇██▇▆▅▃▂  ", "▆▇██▇▆▅▄▃▂ ▂▃", "▇██▇▆▅▃▂ ▂▃▅▆", "▅▃▂ ▂▃▅▆▇██▇▆"]

def make_progress_bar(pct: float) -> str:
    filled = max(0, min(12, int(pct // 8.33)))
    return "█" * filled + "░" * (12 - filled)

def format_live_progress_text(uid, downloaded, total, speed, eta, quote, frame_idx) -> str:
    pct = min(99.9, (downloaded / total * 100)) if total > 0 else 0.0
    dl_mb = downloaded / (1024 * 1024)
    tot_mb = total / (1024 * 1024) if total > 0 else 0.0
    spd = speed / (1024 * 1024) if speed > 0 else 0.0
    eta_str = f"{int(eta)}s" if eta and eta > 0 else "..."
    size_str = f"{dl_mb:.1f} / {tot_mb:.1f} MB" if tot_mb > 0 else f"{dl_mb:.1f} MB"
    return (
        "🎛️ <b>NAHID MEDIA ENGINE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <b>Status:</b> <i>{tr(uid, 'status')}</i>\n"
        f"🎚️ <code>{EQUALIZER_WAVES[frame_idx % len(EQUALIZER_WAVES)]}</code>\n"
        f"📊 <code>[{make_progress_bar(pct)}] {pct:.1f}%</code>\n"
        f"💾 <code>{size_str}</code>\n"
        f"🚀 <code>{spd:.1f} MB/s</code> | ⏳ <code>{eta_str}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>{quote}</i>"
    )

def build_cancel_keyboard(uid: int, job_id: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_cancel"), callback_data=f"cancel_{job_id}")]])

async def send_banner_safe(chat_id, caption, reply_markup=None, context=None):
    try:
        return await context.bot.send_photo(chat_id=chat_id, photo=BOT_LOGO_URL, caption=caption,
                                            reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception:
        return await context.bot.send_message(chat_id=chat_id, text=caption,
                                              reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def edit_any(msg, text, kb=None):
    try:
        if msg.photo:
            await msg.edit_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await msg.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return True
    except Exception as e:
        logger.warning(f"edit_any failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def build_main_menu(uid: int):
    kb = [
        [InlineKeyboardButton(tr(uid, "btn_profile"), callback_data="btn_profile"),
         InlineKeyboardButton(tr(uid, "btn_stats"), callback_data="btn_stats")],
        [InlineKeyboardButton(tr(uid, "btn_guide"), callback_data="btn_guide"),
         InlineKeyboardButton(tr(uid, "btn_lang"), callback_data="btn_lang")],
        [InlineKeyboardButton(tr(uid, "btn_feedback"), callback_data="btn_feedback"),
         InlineKeyboardButton(tr(uid, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")],
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton(tr(uid, "btn_master"), callback_data="btn_admin")])
    return InlineKeyboardMarkup(kb)

def build_lang_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton(n, callback_data=f"setlang_{c}") for c, n in LANG_NAMES.items()]])

def profile_text(user):
    return tr(user.id, "profile").format(
        name=f"{user.first_name} {user.last_name or ''}".strip(),
        user_id=user.id, lang=LANG_NAMES.get(get_lang(user.id), "English"),
    )

def stats_text(uid):
    return tr(uid, "stats").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"])

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
async def set_menu_commands(application):
    cmds = [
        BotCommand("start", "🚀 Start / Main Menu"), BotCommand("lang", "🌐 Change Language"),
        BotCommand("stats", "📊 Statistics"), BotCommand("profile", "👤 My Profile"),
        BotCommand("feedback", "✍️ Send Feedback"), BotCommand("admin", "💬 Contact Admin"),
    ]
    try:
        await application.bot.set_my_commands(cmds)
    except Exception:
        pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # New users start in English automatically
    if str(user.id) not in DB["user_langs"]:
        DB["user_langs"][str(user.id)] = "en"
    DB["unique_users"].add(user.id)
    save_db()
    context.user_data["feedback_mode"] = False
    try:
        await update.message.delete()
    except Exception:
        pass
    await send_banner_safe(update.effective_chat.id, tr(user.id, "welcome").format(name=user.first_name),
                           build_main_menu(user.id), context)

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(tr(update.effective_user.id, "choose_lang"),
                                    reply_markup=build_lang_menu(), parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(stats_text(update.effective_user.id), parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(profile_text(update.effective_user), parse_mode=ParseMode.HTML)

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data["feedback_mode"] = True
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_cancel"), callback_data="btn_home")]])
    await update.message.reply_text(tr(uid, "feedback_prompt"), reply_markup=kb, parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data["feedback_mode"] = False
    kb = [[InlineKeyboardButton(tr(uid, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(f"👨‍💻 <b>Support:</b> @{ADMIN_USERNAME}",
                                    reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data.startswith("cancel_"):
        ACTIVE_CANCELS[data.replace("cancel_", "")] = True
        await edit_any(query.message, tr(user.id, "cancelled"))
        return

    if data.startswith("setlang_"):
        code = data.replace("setlang_", "")
        if code in LANG_NAMES:
            DB["user_langs"][str(user.id)] = code
            DB["unique_users"].add(user.id)
            save_db()
        text = f"{tr(user.id, 'lang_changed')}\n\n{tr(user.id, 'welcome').format(name=user.first_name)}"
        if not await edit_any(query.message, text, build_main_menu(user.id)):
            await context.bot.send_message(user.id, text, reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML)
        return

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_back"), callback_data="btn_home")]])
    context.user_data["feedback_mode"] = False

    if data == "btn_lang":
        await edit_any(query.message, tr(user.id, "choose_lang"), build_lang_menu())
    elif data == "btn_feedback":
        context.user_data["feedback_mode"] = True
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_cancel"), callback_data="btn_home")]])
        await edit_any(query.message, tr(user.id, "feedback_prompt"), kb)
    elif data == "btn_stats":
        await edit_any(query.message, stats_text(user.id), back_kb)
    elif data == "btn_profile":
        await edit_any(query.message, profile_text(user), back_kb)
    elif data == "btn_guide":
        await edit_any(query.message, tr(user.id, "guide"), back_kb)
    elif data == "btn_admin":
        if user.id == ADMIN_ID:
            text = (
                "🛠️ <b>Admin Panel</b>\n\n"
                f"• Users: <code>{len(DB['unique_users'])}</code>\n"
                f"• Downloads: <code>{DB['total_downloads']}</code>\n"
                f"• RapidAPI (YouTube): <code>{'Active' if RAPIDAPI_KEY else 'Disabled'}</code>\n"
                f"• Generic API: <code>{'Active' if GENERIC_API_HOST else 'Not set'}</code>"
            )
            await edit_any(query.message, text, back_kb)
        else:
            await query.answer("Administrator only!", show_alert=True)
    elif data == "btn_home":
        await edit_any(query.message, tr(user.id, "welcome").format(name=user.first_name), build_main_menu(user.id))

# ---------------------------------------------------------------------------
# Main message handler
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

    # Feedback routing
    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False
        name = f"{user.first_name} {user.last_name or ''}".strip()
        handle = f"@{user.username}" if user.username else "No Username"
        admin_text = (
            "📬 <b>New Feedback</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {name}\n🔗 {handle}\n🆔 <code>{user.id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 {raw_text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        await message.reply_text(tr(user.id, "feedback_ok"), reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML)
        return

    urls = re.findall(r"(https?://\S+)", raw_text)

    if not urls:
        try:
            await message.delete()
        except Exception:
            pass
        warn = await context.bot.send_message(chat_id=chat_id, text=tr(user.id, "invalid"), parse_mode=ParseMode.HTML)

        async def del_later(mid):
            await asyncio.sleep(5)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass

        asyncio.create_task(del_later(warn.message_id))
        return

    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]
    job_id = uuid.uuid4().hex[:8]
    ACTIVE_CANCELS[job_id] = False
    JOB_PROGRESS[job_id] = {"downloaded": 0, "total": 0, "speed": 0, "eta": 0}

    initial_text = format_live_progress_text(user.id, 0, 0, 0, 0, random.choice(FUNNY_QUOTES), 0)
    proc_msg = await send_banner_safe(chat_id=chat_id, caption=initial_text,
                                      reply_markup=build_cancel_keyboard(user.id, job_id), context=context)

    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")
    loop_active = True

    async def live_progress_loop():
        last = initial_text
        frame = 0
        while loop_active:
            await asyncio.sleep(2)
            if not loop_active or ACTIVE_CANCELS.get(job_id):
                break
            p = JOB_PROGRESS.get(job_id, {})
            frame += 1
            card = format_live_progress_text(user.id, p.get("downloaded", 0), p.get("total", 0),
                                             p.get("speed", 0), p.get("eta", 0), random.choice(FUNNY_QUOTES), frame)
            if card != last:
                last = card
                await edit_any(proc_msg, card, build_cancel_keyboard(user.id, job_id))

    progress_task = asyncio.create_task(live_progress_loop())
    state = {"direct": None}

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
        loop = asyncio.get_running_loop()
        download_success = False
        out_file = str(temp_dir / "video.mp4")

        yt = is_youtube(target_url)
        cleaned_url = sanitize_youtube_url(target_url) if yt else clean_social_url(target_url)

        async def grab(link) -> bool:
            if not link or ACTIVE_CANCELS.get(job_id):
                return False
            res = await loop.run_in_executor(None, download_stream_with_progress, link, out_file, job_id)
            if res == "big":
                state["direct"] = state["direct"] or link
            return res == "ok"

        async def try_ytdlp(is_yt_flag: bool) -> bool:
            if ACTIVE_CANCELS.get(job_id):
                return False
            for f in glob.glob(f"{temp_dir}/*"):
                try:
                    os.remove(f)
                except Exception:
                    pass
            try:
                await loop.run_in_executor(None, download_with_ytdlp, cleaned_url, output_template, job_id, is_yt_flag)
                return True
            except DownloadCancelledException:
                return False
            except Exception as e:
                logger.warning(f"yt-dlp notice: {e}")
                return False

        # ---------------- YOUTUBE ----------------
        if yt:
            hd_link = None
            long_video = False
            if RAPIDAPI_KEY:
                info = await loop.run_in_executor(None, rapidapi_youtube, cleaned_url)
                hd_link = info["hd"]
                long_video = info["duration"] > LONG_VIDEO_SECONDS
                if long_video and hd_link:
                    state["direct"] = hd_link          # long video -> HD direct link
                else:
                    for lk in info["small"][:3]:       # short video -> send in Telegram
                        if await grab(lk):
                            download_success = True
                            break
                        if state["direct"]:
                            break
                if state["direct"] and hd_link:
                    state["direct"] = hd_link          # always give the HD link, not the SD one
            if not download_success and not state["direct"]:
                download_success = await try_ytdlp(True)

        # ---------------- FACEBOOK ----------------
        elif "facebook.com" in target_url or "fb.watch" in target_url:
            l1 = await loop.run_in_executor(None, scrape_facebook_layer1, cleaned_url)
            download_success = await grab(l1)
            if not download_success and not state["direct"]:
                l2 = await loop.run_in_executor(None, scrape_facebook_layer2, cleaned_url)
                download_success = await grab(l2)
            if not download_success and not state["direct"]:
                g = await loop.run_in_executor(None, generic_api_link, cleaned_url)
                download_success = await grab(g)
            if not download_success and not state["direct"]:
                download_success = await try_ytdlp(False)

        # ---------------- TIKTOK / INSTAGRAM / OTHERS ----------------
        else:
            if "tiktok.com" in cleaned_url or "douyin.com" in cleaned_url:
                tk = await loop.run_in_executor(None, tikwm_link, cleaned_url)
                download_success = await grab(tk)
            if not download_success and not state["direct"]:
                g = await loop.run_in_executor(None, generic_api_link, cleaned_url)
                download_success = await grab(g)
            if not download_success and not state["direct"]:
                download_success = await try_ytdlp(False)

        loop_active = False
        progress_task.cancel()

        if ACTIVE_CANCELS.get(job_id):
            return

        files = [f for f in glob.glob(f"{temp_dir}/*") if os.path.getsize(f) > 1000]

        # Deliver in chat
        if download_success and files and not state["direct"]:
            video_path = files[0]
            if os.path.getsize(video_path) <= MAX_UPLOAD_LIMIT:
                DB["total_downloads"] += 1
                save_db()
                caption = tr(user.id, "delivered").format(admin=ADMIN_USERNAME)
                try:
                    with open(video_path, "rb") as vf:
                        await context.bot.send_video(chat_id=chat_id, video=vf, caption=caption,
                                                     supports_streaming=True, read_timeout=300,
                                                     write_timeout=300, parse_mode=ParseMode.HTML)
                except Exception:
                    with open(video_path, "rb") as vf:
                        await context.bot.send_document(chat_id=chat_id, document=vf, caption=caption,
                                                        read_timeout=300, write_timeout=300,
                                                        parse_mode=ParseMode.HTML)
                try:
                    await proc_msg.delete()
                except Exception:
                    pass
                return

        # Large file -> HD direct link
        direct = state["direct"]
        if not direct:
            try:
                direct = await loop.run_in_executor(None, fetch_direct_stream_url, cleaned_url)
            except Exception:
                direct = None

        if direct and not ACTIVE_CANCELS.get(job_id):
            DB["total_downloads"] += 1
            save_db()
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_dl"), url=direct)]])
            if not await edit_any(proc_msg, tr(user.id, "large"), kb):
                await context.bot.send_message(chat_id, tr(user.id, "large"), reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        # Failed
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_portal"), url=get_web_portal_link(target_url))]])
        if not await edit_any(proc_msg, tr(user.id, "failed"), kb):
            await context.bot.send_message(chat_id, tr(user.id, "failed"), reply_markup=kb, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.error(f"Execution Error: {exc}", exc_info=True)
        loop_active = False
        progress_task.cancel()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_portal"), url=get_web_portal_link(target_url))]])
        if not await edit_any(proc_msg, tr(user.id, "failed"), kb):
            await context.bot.send_message(chat_id, tr(user.id, "failed"), reply_markup=kb, parse_mode=ParseMode.HTML)

    finally:
        loop_active = False
        if not progress_task.done():
            progress_task.cancel()
        ACTIVE_CANCELS.pop(job_id, None)
        JOB_PROGRESS.pop(job_id, None)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.critical("BOT_TOKEN is not configured!")
        return

    threading.Thread(target=run_http_server, daemon=True).start()

    req = HTTPXRequest(connect_timeout=60.0, read_timeout=300.0, write_timeout=300.0, pool_timeout=60.0)
    app = ApplicationBuilder().token(TOKEN).request(req).post_init(set_menu_commands).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming_message))

    logger.info("Nahid Video Downloader Pro is LIVE!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()