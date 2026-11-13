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

# Credentials & APIs
TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY") or os.getenv("X-RapidAPI-Key", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST") or os.getenv("X-RapidAPI-Host", "all-in-one-media-downloader-api.p.rapidapi.com")

ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"
BOT_LOGO_URL = "https://user55725.cn.imgto.link/public/20261113/fd75766042207998416adf8f-1000482026.avif"
MAX_UPLOAD_LIMIT = 48 * 1024 * 1024  # 48 MB Safe limit for direct Telegram upload
STATS_FILE = "stats.json"

ACTIVE_CANCELS = {}
JOB_PROGRESS = {}

# ---------------------------------------------------------------------------
# 2. Multi-Language System (English [Default], বাংলা, Bahasa Melayu)
# ---------------------------------------------------------------------------
STRINGS = {
    "en": {
        "welcome": (
            "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
            "⚡ <b>The Ultimate Global Media Downloader</b>\n"
            "Drop any public video link from YouTube, Facebook, Instagram, or TikTok to download instantly in Full HD!\n\n"
            "🌐 <b>Platforms Supported:</b>\n"
            "• <b>YouTube</b> (Shorts, Long Songs & Standard Videos)\n"
            "• <b>Facebook</b> (Reels, Watch, Long Videos)\n"
            "• <b>Instagram</b> (Reels, Posts & Stories)\n"
            "• <b>TikTok</b> (Watermark-free Full HD)\n"
            "• <b>X/Twitter, Pinterest, Threads</b> & 1000+ more.\n\n"
            "👇 <i>Use the dashboard below or click <b>[ ☰ Menu ]</b>:</i>"
        ),
        "btn_profile": "👤 My Profile",
        "btn_stats": "📊 Live Statistics",
        "btn_guide": "ℹ️ User Guide",
        "btn_lang": "🌐 Change Language",
        "btn_feedback": "✍️ Feedback / Report",
        "btn_admin": "💬 Contact Admin",
        "btn_back": "🔙 Back to Menu",
        "btn_master": "🛠️ Admin Master Panel",
        "stats": (
            "📊 <b>Nahid Video Downloader — Global Stats</b>\n\n"
            "👥 <b>Total Active Users:</b> <code>{users:,}</code>\n"
            "📥 <b>Total Media Processed:</b> <code>{downloads:,}</code>\n"
            "🟢 <b>Server Status:</b> <code>Online 24/7 (Turbo)</code>\n"
            "⚡ <b>Engine Health:</b> <code>Dual-Delivery Active</code>"
        ),
        "profile": (
            "👤 <b>User Account Overview</b>\n\n"
            "• <b>Name:</b> {name}\n"
            "• <b>User ID:</b> <code>{user_id}</code>\n"
            "• <b>Language:</b> 🇬🇧 Global English\n"
            "• <b>Access Tier:</b> <code>Unlimited Turbo Access</code>"
        ),
        "guide": (
            "📌 <b>Quick User Manual:</b>\n\n"
            "1. Copy any video URL from YouTube, Facebook, Instagram, or TikTok.\n"
            "2. Paste it directly into this chat.\n"
            "3. Media under <b>50 MB</b> will be delivered in chat.\n"
            "4. Large media over <b>50 MB</b> generates a fast direct download button."
        ),
        "lang_select": "🌐 <b>Select Your Preferred Language:</b>",
        "lang_changed": "✅ <b>Language successfully changed to English! 🇬🇧</b>",
        "feedback_prompt": "✍️ <b>Send Feedback & Suggestions</b>\nType your message below. It will be sent directly to the admin:",
        "feedback_success": "✅ <b>Thank you!</b> Your message has been forwarded directly to the admin.",
        "nonsense_warn": "🚨 <b>Hey! This isn't a chatroom for nonsense! 😂</b>\nPlease send a valid <b>YouTube, Facebook, TikTok, or Instagram</b> link!",
        "delivered": "🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{admin}",
        "large_file": (
            "📦 <b>Video Ready for Download!</b>\n\n"
            "Due to file size (> 50 MB) or platform restrictions, your video stream has been prepared in Full HD on our high-speed gateway.\n\n"
            "👇 Click the button below to download directly to your device:"
        ),
        "btn_dl": "📥 Direct High-Speed Download (Full HD)",
        "quotes": [
            "Brewing your HD video like a fine cup of artisan espresso... ☕🎬",
            "Wrestling the media stream away from platform security... 🤼‍♂️💨",
            "Summoning digital sorcery: Abracadabra, pixels assemble! 🧙‍♂️✨",
            "Even Elon Musk's Falcon 9 is jealous of our packet speed! 🚀🔥",
            "Polishing every frame so your video sparkles in 60 FPS! ✨💎",
            "Dodging server traffic jams to deliver your file fast! 🏎️💨"
        ]
    },
    "bn": {
        "welcome": (
            "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>বিশ্বমানের অল-ইন-ওয়ান ভিডিও ডাউনলোডার</b>\n"
            "YouTube, Facebook, Instagram বা TikTok-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠিয়ে দিন—কয়েক সেকেন্ডেই ফুল এইচডি ভিডিও হাজির হবে!\n\n"
            "🌐 <b>সাপোর্টেড:</b> YouTube Shorts ও বড় গান, Facebook Reels, TikTok (ওয়াটারমার্ক ছাড়া), Instagram ও ১০০০+ সাইট।\n\n"
            "👇 <i>নিচের ড্যাশবোর্ড বা <b>[ ☰ Menu ]</b> বাটন ব্যবহার করুন:</i>"
        ),
        "btn_profile": "👤 আমার প্রোফাইল",
        "btn_stats": "📊 লাইভ পরিসংখ্যান",
        "btn_guide": "ℹ️ ব্যবহারবিধি",
        "btn_lang": "🌐 ভাষা পরিবর্তন",
        "btn_feedback": "✍️ মতামত / সমস্যা",
        "btn_admin": "💬 অ্যাডমিন যোগাযোগ",
        "btn_back": "🔙 ফিরে যান",
        "btn_master": "🛠️ অ্যাডমিন প্যানেল",
        "stats": (
            "📊 <b>লাইভ পরিসংখ্যান</b>\n\n"
            "👥 <b>মোট ব্যবহারকারী:</b> <code>{users:,} জন</code>\n"
            "📥 <b>মোট ডাউনলোড:</b> <code>{downloads:,} টি</code>\n"
            "🟢 <b>সার্ভার:</b> <code>Online 24/7 (সুপারফাস্ট)</code>"
        ),
        "profile": (
            "👤 <b>ইউজার প্রোফাইল</b>\n\n"
            "• <b>নাম:</b> {name}\n"
            "• <b>আইডি:</b> <code>{user_id}</code>\n"
            "• <b>ভাষা:</b> 🇧🇩 বাংলা\n"
            "• <b>অ্যাক্সেস:</b> <code>আনলিমিটেড ফ্রি</code>"
        ),
        "guide": (
            "📌 <b>সহজ ব্যবহারবিধি:</b>\n\n"
            "১. যেকোনো ভিডিওর লিংক কপি করে সরাসরি চ্যাটে পাঠিয়ে দিন।\n"
            "২. ৫০MB-এর ভেতরের ভিডিও সরাসরি চ্যাটে প্লে হবে।\n"
            "৩. ৫০MB-এর বড় ভিডিওর জন্য হাই-স্পিড ডাইরেক্ট ডাউনলোড বাটন তৈরি হয়ে যাবে।"
        ),
        "lang_select": "🌐 <b>আপনার পছন্দের ভাষা বেছে নিন:</b>",
        "lang_changed": "✅ <b>ভাষা সফলভাবে বাংলায় পরিবর্তন করা হয়েছে! 🇧🇩</b>",
        "feedback_prompt": "✍️ <b>মতামত বা সমস্যার বিবরণ দিন</b>\nআপনার মেসেজটি নিচে লিখে পাঠান। এটি সরাসরি অ্যাডমিনের কাছে চলে যাবে:",
        "feedback_success": "✅ <b>ধন্যবাদ!</b> আপনার মতামতটি সফলভাবে অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "nonsense_warn": "🚨 <b>আরে ভাই! এটা আড্ডাবাজির জায়গা না! 😂</b>\nকাজের মতো <b>ইউটিউব, ফেসবুক, টিকটক বা ইনস্টাগ্রাম</b> লিংক পাঠান!",
        "delivered": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large_file": (
            "📦 <b>ভিডিও ডাউনলোডের জন্য প্রস্তুত!</b>\n\n"
            "ভিডিওটির সাইজ বড় হওয়ায় (> ৫০ MB) অথবা প্ল্যাটফর্ম রেস্ট্রিকশনের কারণে হাই-স্পিড গেটওয়েতে ফুল এইচডি লিংক প্রস্তুত করা হয়েছে।\n\n"
            "👇 নিচের বাটনে চাপ দিয়ে সরাসরি আপনার ফোনে নামিয়ে নিন:"
        ),
        "btn_dl": "📥 সরাসরি ফুল এইচডি ডাউনলোড করুন",
        "quotes": [
            "এক কাপ চা খেয়ে একটু হাসুন! সার্ভারের তো প্রায় ঘাম ছুটে গেছে... ☕🎬",
            "ধরো ধরো! ভিডিও চোর লিংক নিয়ে রকেটের বেগে দৌড় দিয়েছে... 🏃‍♂️💨",
            "জাদুকরী মন্ত্র পড়া চলছে: আব্রাবি-কা-ডাব্রা, ভিডিও হাজির হও! 🧙‍♂️✨",
            "বানর নাচ দেখতে দেখতেই ভিডিও ডাউনলোড হয়ে যাবে, একটু চিল করুন! 🐒🍿"
        ]
    },
    "ms": {
        "welcome": (
            "Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>Pemuat Turun Media Global Terpantas</b>\n"
            "Hantarkan sebarang pautan video dari YouTube, Facebook, Instagram, atau TikTok untuk muat turun terus dalam Full HD!\n\n"
            "🌐 <b>Disokong:</b> YouTube, Facebook, Instagram, TikTok, X/Twitter & 1000+ laman web.\n\n"
            "👇 <i>Gunakan menu di bawah atau klik <b>[ ☰ Menu ]</b>:</i>"
        ),
        "btn_profile": "👤 Profil Saya",
        "btn_stats": "📊 Statistik Langsung",
        "btn_guide": "ℹ️ Cara Penggunaan",
        "btn_lang": "🌐 Tukar Bahasa",
        "btn_feedback": "✍️ Maklum Balas",
        "btn_admin": "💬 Hubungi Admin",
        "btn_back": "🔙 Kembali",
        "btn_master": "🛠️ Panel Admin",
        "stats": (
            "📊 <b>Statistik Langsung</b>\n\n"
            "👥 <b>Pengguna:</b> <code>{users:,}</code>\n"
            "📥 <b>Dimuat Turun:</b> <code>{downloads:,}</code>\n"
            "🟢 <b>Status:</b> <code>Dalam Talian 24/7</code>"
        ),
        "profile": (
            "👤 <b>Profil Pengguna</b>\n\n"
            "• <b>Nama:</b> {name}\n"
            "• <b>ID Telegram:</b> <code>{user_id}</code>\n"
            "• <b>Bahasa:</b> 🇲🇾 Bahasa Melayu\n"
            "• <b>Akses:</b> <code>Akses Tanpa Had</code>"
        ),
        "guide": (
            "📌 <b>Panduan Pengguna:</b>\n\n"
            "1. Salin pautan video dari YouTube, FB, Insta, atau TikTok.\n"
            "2. Hantar terus ke sembang ini.\n"
            "3. Fail <50 MB dihantar terus ke sembang.\n"
            "4. Fail >50 MB menjana butang muat turun pantas terus."
        ),
        "lang_select": "🌐 <b>Pilih Bahasa Pilihan Anda:</b>",
        "lang_changed": "✅ <b>Bahasa berjaya ditukar kepada Bahasa Melayu! 🇲🇾</b>",
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas</b>\nTaipkan mesej anda di bawah untuk dihantar terus kepada admin:",
        "feedback_success": "✅ <b>Terima kasih!</b> Maklum balas anda telah dihantar kepada admin.",
        "nonsense_warn": "🚨 <b>Hei! Ini bukan tempat borak kosong! 😂</b>\nSila hantarkan pautan <b>YouTube, Facebook, TikTok atau Instagram</b> yang sah!",
        "delivered": "🎬 <b>Video Berjaya Dihantar!</b>\n📥 Dikuasakan oleh @{admin}",
        "large_file": (
            "📦 <b>Fail Video Sedia Dimuat Turun!</b>\n\n"
            "Disebabkan saiz fail (> 50 MB) atau sekatan pelayan, aliran media telah disediakan pada pelayan pantas kami.\n\n"
            "👇 Klik butang di bawah untuk memuat turun kualiti penuh terus:"
        ),
        "btn_dl": "📥 Muat Turun Kualiti Penuh",
        "quotes": [
            "Tunggu sebentar! Pelayan kami sedang memproses video anda... ☕⚡",
            "Menyelinap mengambil video daripada sekatan keselamatan... 🥷📦",
            "Menggilap setiap piksel supaya video anda berkilat dalam HD! ✨💎"
        ]
    }
}

# ---------------------------------------------------------------------------
# 3. Persistent Database Handler
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

def get_user_lang(user_id: int) -> str:
    # Default is English
    return DB["user_langs"].get(str(user_id), "en")

def set_user_lang(user_id: int, lang: str):
    DB["user_langs"][str(user_id)] = lang
    save_db()

def tr(user_id: int, key: str) -> str:
    lang = get_user_lang(user_id)
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, ""))

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
# 5. URL Sanitizers & Web Portals
# ---------------------------------------------------------------------------
def clean_youtube_url(url: str) -> str:
    url = re.sub(r'(\?|\&)si=[^&]*', '', url)
    url = re.sub(r'(\?|\&)feature=[^&]*', '', url)
    url = url.replace("/shorts/", "/watch?v=")
    return url

def clean_social_url(url: str) -> str:
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

def get_web_portal_link(url: str) -> str:
    """Generates direct browser gateway when datacenter IPs are blocked."""
    clean = url.strip()
    if "youtube.com" in clean or "youtu.be" in clean:
        clean_yt = clean_youtube_url(clean)
        return f"https://ssyoutube.com/en177AU/{clean_yt}"
    elif "facebook.com" in clean or "fb.watch" in clean:
        clean_fb = clean_social_url(clean)
        return f"https://fdown.net/download.php?URLz={clean_fb}"
    elif "instagram.com" in clean:
        return "https://fastdl.app/"
    elif "tiktok.com" in clean:
        return "https://snaptik.app/"
    return clean

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
        logger.warning(f"Stream download notice: {e}")
        return False

# ---------------------------------------------------------------------------
# 7. Specialized Scrapers & RapidAPI Gateway
# ---------------------------------------------------------------------------
def scrape_facebook_layer1(url: str) -> str:
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
    if not RAPIDAPI_KEY:
        return False
    try:
        endpoint = f"https://{RAPIDAPI_HOST}/"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json"
        }
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
# 8. Adaptive yt-dlp Engine
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
                'player_client': ['android', 'ios'],
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
            'youtube': {'player_client': ['android', 'ios']}
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url') or (info.get('requested_formats') and info['requested_formats'][0].get('url'))

# ---------------------------------------------------------------------------
# 9. Live Sound Wave Equalizer
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
    
    eta_str = f"{int(eta)}s" if eta > 0 else "..."
    size_str = f"{dl_mb:.1f} / {tot_mb:.1f} MB" if tot_mb > 0 else f"{dl_mb:.1f} MB"

    return (
        "🎛️ <b>NAHID MEDIA ENGINE — TURBO STREAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📥 <b>Status:</b> <i>Downloading High-Speed Media...</i>\n"
        f"🎚️ <b>Equalizer:</b> <code>{wave_bars}</code>\n"
        "🔊 <b>Frequency:</b> <code>ılı.lıllılı.ıllı.lıllılı</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Buffer:</b> <code>[{bar}] {pct:.1f}%</code>\n"
        f"💾 <b>Size:</b> <code>{size_str}</code> | 🚀 <b>Speed:</b> <code>{spd_mb:.1f} MB/s</code>\n"
        f"⏳ <b>ETA:</b> <code>{eta_str}</code>\n"
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
# 10. Keyboards & Menu System
# ---------------------------------------------------------------------------
def build_main_menu(user_id: int):
    keyboard = [
        [
            InlineKeyboardButton(tr(user_id, "btn_profile"), callback_data="btn_profile"),
            InlineKeyboardButton(tr(user_id, "btn_stats"), callback_data="btn_stats")
        ],
        [
            InlineKeyboardButton(tr(user_id, "btn_guide"), callback_data="btn_guide"),
            InlineKeyboardButton(tr(user_id, "btn_lang"), callback_data="btn_lang")
        ],
        [
            InlineKeyboardButton(tr(user_id, "btn_feedback"), callback_data="btn_feedback"),
            InlineKeyboardButton(tr(user_id, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")
        ]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton(tr(user_id, "btn_master"), callback_data="btn_admin")])
    return InlineKeyboardMarkup(keyboard)

def build_lang_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English (Global Default)", callback_data="setlang_en")],
        [InlineKeyboardButton("🇧🇩 বাংলা (Bengali)", callback_data="setlang_bn")],
        [InlineKeyboardButton("🇲🇾 Bahasa Melayu (Malay)", callback_data="setlang_ms")],
        [InlineKeyboardButton("🔙 Back / ফিরে যান", callback_data="btn_home")]
    ])

# ---------------------------------------------------------------------------
# 11. Command Handlers
# ---------------------------------------------------------------------------
async def set_menu_commands(application):
    commands = [
        BotCommand("start", "🚀 Start / Refresh Main Dashboard"),
        BotCommand("lang", "🌐 Change Language / ভাষা / Bahasa"),
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

    welcome_text = tr(user.id, "welcome").format(name=user.first_name)
    try:
        await update.message.delete()
    except Exception:
        pass
    await send_banner_safe(update.effective_chat.id, welcome_text, build_main_menu(user.id), context)

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(tr(user.id, "lang_select"), reply_markup=build_lang_menu(), parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    text = tr(user.id, "stats").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    text = tr(user.id, "profile").format(name=f"{user.first_name} {user.last_name or ''}".strip(), user_id=user.id)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = True
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel / বাতিল", callback_data="btn_home")]])
    await update.message.reply_text(tr(user.id, "feedback_prompt"), reply_markup=cancel_kb, parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    kb = [[InlineKeyboardButton(tr(user.id, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(f"👨‍💻 <b>Support:</b> @{ADMIN_USERNAME}", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# ---------------------------------------------------------------------------
# 12. Interactive Button Callbacks
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

    # Language Switcher
    if data.startswith("setlang_"):
        new_lang = data.replace("setlang_", "")
        set_user_lang(user.id, new_lang)
        welcome_text = tr(user.id, "welcome").format(name=user.first_name)
        banner_text = f"{tr(user.id, 'lang_changed')}\n\n{welcome_text}"
        try:
            await query.edit_message_caption(caption=banner_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))
        except Exception:
            await query.edit_message_text(text=banner_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))
        return

    legacy_map = {
        "my_profile": "btn_profile", "help_guide": "btn_guide", "admin_panel": "btn_admin",
        "back_home": "btn_home", "menu_home": "btn_home"
    }
    data = legacy_map.get(data, data)
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_back"), callback_data="btn_home")]])

    if data == "btn_lang":
        context.user_data["feedback_mode"] = False
        try:
            await query.edit_message_caption(caption=tr(user.id, "lang_select"), parse_mode=ParseMode.HTML, reply_markup=build_lang_menu())
        except Exception:
            await query.edit_message_text(text=tr(user.id, "lang_select"), parse_mode=ParseMode.HTML, reply_markup=build_lang_menu())

    elif data == "btn_feedback":
        context.user_data["feedback_mode"] = True
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel / বাতিল", callback_data="btn_home")]])
        try:
            await query.edit_message_caption(caption=tr(user.id, "feedback_prompt"), parse_mode=ParseMode.HTML, reply_markup=cancel_kb)
        except Exception:
            await query.edit_message_text(text=tr(user.id, "feedback_prompt"), parse_mode=ParseMode.HTML, reply_markup=cancel_kb)

    elif data == "btn_stats":
        context.user_data["feedback_mode"] = False
        text = tr(user.id, "stats").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"])
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_profile":
        context.user_data["feedback_mode"] = False
        text = tr(user.id, "profile").format(name=f"{user.first_name} {user.last_name or ''}".strip(), user_id=user.id)
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_guide":
        context.user_data["feedback_mode"] = False
        text = tr(user.id, "guide")
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
        welcome_text = tr(user.id, "welcome").format(name=user.first_name)
        try:
            await query.edit_message_caption(caption=welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))
        except Exception:
            await query.edit_message_text(text=welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))

# ---------------------------------------------------------------------------
# 13. Message Handler & Zero-Failure Dual Delivery
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
            tr(user.id, "feedback_success"),
            reply_markup=build_main_menu(user.id),
            parse_mode=ParseMode.HTML
        )
        return

    # Extract Video Links
    urls = re.findall(r'(https?://\S+)', raw_text)

    # Non-link Auto-Delete & 5-Second Warning
    if not urls:
        try:
            await message.delete()
        except Exception:
            pass

        warn_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text=tr(user.id, "nonsense_warn"), 
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

    user_quotes = STRINGS.get(get_user_lang(user.id), STRINGS["en"])["quotes"]
    initial_quote = random.choice(user_quotes)
    initial_text = format_live_progress_text(0, 0, 0, 0, initial_quote, 0)

    proc_msg = await send_banner_safe(
        chat_id=chat_id, 
        caption=initial_text, 
        reply_markup=build_cancel_keyboard(job_id), 
        context=context
    )

    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    # Live Fluctuating Equalizer Loop (Every 1.5s)
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
            cur_quote = random.choice(user_quotes)
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
        cleaned_url = clean_youtube_url(target_url) if is_youtube else clean_social_url(target_url)

        # -------------------------------------------------------------------
        # 1. YOUTUBE EXTRACTION ENGINE (Anti-Bot + RapidAPI Gateway)
        # -------------------------------------------------------------------
        if is_youtube:
            # Step 1: RapidAPI Universal Gateway (Fastest & Never blocked)
            if RAPIDAPI_KEY and not ACTIVE_CANCELS.get(job_id):
                yt_file = str(temp_dir / "yt_video.mp4")
                download_success = await loop.run_in_executor(
                    None, 
                    download_via_rapidapi, 
                    cleaned_url, 
                    yt_file, 
                    job_id
                )

            # Step 2: Native App Client Spoofing (Android/iOS)
            if not download_success and not ACTIVE_CANCELS.get(job_id):
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
                    logger.warning(f"YouTube yt-dlp notice: {e}")

        # -------------------------------------------------------------------
        # 2. FACEBOOK EXTRACTION ENGINE (FDown + Mobile Scraper + RapidAPI)
        # -------------------------------------------------------------------
        elif "facebook.com" in target_url or "fb.watch" in target_url:
            # Layer 1: FDown Gateway Scraper
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
                except Exception:
                    pass

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
                except Exception:
                    pass

        # Stop active progress loop
        loop_active = False
        progress_task.cancel()

        if ACTIVE_CANCELS.get(job_id):
            return

        downloaded_files = glob.glob(f"{temp_dir}/*")

        # 1. Files <= 48 MB delivered in Telegram Chat with player streaming
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
                        caption=tr(user.id, "delivered").format(admin=ADMIN_USERNAME),
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

        # 2. Large Files (>48 MB up to 500 MB) or IP restrictions: Direct High-Speed Download Button
        if not direct_stream_url:
            direct_stream_url = await loop.run_in_executor(None, fetch_direct_stream_url, cleaned_url)

        # 3. ZERO-FAILURE FALLBACK: Never show extraction error! Generate Web Portal Link
        if not direct_stream_url:
            direct_stream_url = get_web_portal_link(target_url)

        DB["total_downloads"] += 1
        save_db()
        kb = [[InlineKeyboardButton(tr(user.id, "btn_dl"), url=direct_stream_url)]]
        large_caption = tr(user.id, "large_file")
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await proc_msg.edit_text(text=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    except Exception as exc:
        logger.error(f"Execution Error: {exc}", exc_info=True)
        loop_active = False
        progress_task.cancel()
        
        # Zero-Failure Fallback: Even on unexpected crash, give the download portal!
        portal_url = get_web_portal_link(target_url)
        kb = [[InlineKeyboardButton(tr(user.id, "btn_dl"), url=portal_url)]]
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=tr(user.id, "large_file"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await proc_msg.edit_text(text=tr(user.id, "large_file"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=tr(user.id, "large_file"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

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
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming_message))

    logger.info("Nahid Video Downloader Pro (Zero-Failure Edition) is LIVE!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
