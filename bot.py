import os
import re
import json
import glob
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
MAX_UPLOAD_LIMIT = 48 * 1024 * 1024
STATS_FILE = "stats.json"

# ---------------------------------------------------------------------------
# 2. Multi-Language Dictionary (Default: Global English)
# ---------------------------------------------------------------------------
STRINGS = {
    "en": {
        "welcome": (
            "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
            "⚡ <b>The Ultimate Global Media Downloader</b>\n"
            "Drop any public video link from Facebook, Instagram, TikTok, or YouTube to download instantly in Full HD!\n\n"
            "🌐 <b>Platforms Supported:</b>\n"
            "• <b>Facebook</b> (Reels, Watch, Long Videos)\n"
            "• <b>Instagram</b> (Reels, Posts & Stories)\n"
            "• <b>TikTok</b> (Watermark-free Full HD)\n"
            "• <b>YouTube</b> (Shorts & Standard Videos)\n"
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
        "btn_master": "🛠️ Admin Panel",
        "stats": (
            "📊 <b>Nahid Video Downloader — Global Stats</b>\n\n"
            "👥 <b>Total Active Users:</b> <code>{users:,}</code>\n"
            "📥 <b>Total Media Processed:</b> <code>{downloads:,}</code>\n"
            "🟢 <b>Server Status:</b> <code>Online 24/7 (Turbo)</code>\n"
            "⚡ <b>Engine Health:</b> <code>Quad-Layer Active</code>"
        ),
        "profile": (
            "👤 <b>User Account Overview</b>\n\n"
            "• <b>Name:</b> {name}\n"
            "• <b>User ID:</b> <code>{user_id}</code>\n"
            "• <b>Active Language:</b> 🇬🇧 Global English\n"
            "• <b>Access Tier:</b> <code>Unlimited Turbo Access</code>"
        ),
        "guide": (
            "📌 <b>Quick User Manual:</b>\n\n"
            "1. Copy any video URL from Facebook, Instagram, TikTok, or YouTube.\n"
            "2. Paste it directly into this chat.\n"
            "3. Videos under <b>50 MB</b> will be delivered in chat.\n"
            "4. Large videos (>50 MB up to 500 MB) generate a high-speed direct download link."
        ),
        "lang_select": "🌐 <b>Select Your Preferred Language:</b>",
        "lang_changed": "✅ <b>Language successfully changed to English! 🇬🇧</b>",
        "feedback_prompt": "✍️ <b>Send Feedback & Suggestions</b>\nType your message below. It will be sent directly to the admin:",
        "feedback_success": "✅ <b>Thank you!</b> Your message has been forwarded directly to the admin.",
        "nonsense_warn": "🚨 <b>Hey! This isn't a chatroom for nonsense! 😂</b>\nPlease send a valid <b>Facebook, TikTok, Instagram, or YouTube</b> link!",
        "delivered": "🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{admin}",
        "large_file": "📦 <b>Large Video File Detected! (> 50 MB)</b>\nTelegram restricts direct bot uploads. Click below to download in original Full HD directly:",
        "btn_dl": "📥 Direct High-Speed Download (Full HD)",
        "failed": "❌ <b>Extraction Failed!</b> Video may be private, age-restricted, or removed by the platform. Please verify the URL!",
        "err": "⚠️ <b>Error processing video.</b> Please verify your URL and try again."
    },
    "bn": {
        "welcome": (
            "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>বিশ্বমানের অল-ইন-ওয়ান ভিডিও ডাউনলোডার</b>\n"
            "Facebook, Instagram, TikTok বা YouTube-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠিয়ে দিন—কয়েক সেকেন্ডেই ফুল এইচডি ভিডিও হাজির হবে!\n\n"
            "🌐 <b>সাপোর্টেড:</b> Facebook, Instagram Reels, TikTok (ওয়াটারমার্ক ছাড়া), YouTube Shorts, Twitter, Pinterest ও ১০০০+ সাইট।\n\n"
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
            "১. FB, Insta, TikTok বা YouTube-এর যেকোনো ভিডিওর লিংক কপি করুন।\n"
            "২. সরাসরি চ্যাটে পাঠিয়ে দিন।\n"
            "৩. ৫০MB-এর ভেতরের ভিডিও সরাসরি চ্যাটে পাবেন।\n"
            "৪. ৫০MB-এর বড় ভিডিওর জন্য হাই-স্পিড ডাইরেক্ট ডাউনলোড লিংক পাবেন।"
        ),
        "lang_select": "🌐 <b>আপনার পছন্দের ভাষা বেছে নিন:</b>",
        "lang_changed": "✅ <b>ভাষা সফলভাবে বাংলায় পরিবর্তন করা হয়েছে! 🇧🇩</b>",
        "feedback_prompt": "✍️ <b>মতামত বা সমস্যার বিবরণ দিন</b>\nআপনার মেসেজটি নিচে লিখে পাঠান। এটি সরাসরি অ্যাডমিনের কাছে চলে যাবে:",
        "feedback_success": "✅ <b>ধন্যবাদ!</b> আপনার মতামতটি সফলভাবে অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "nonsense_warn": "🚨 <b>আরে ভাই! এটা আড্ডাবাজির জায়গা না! 😂</b>\nকাজের মতো <b>ফেসবুক, টিকটক, ইনস্টাগ্রাম বা ইউটিউব</b> লিংক পাঠান!",
        "delivered": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large_file": "📦 <b>ভিডিওর সাইজ বিশাল! (> ৫০ MB)</b>\nটেলিগ্রাম চ্যাটে ৫০MB-এর বড় ফাইল পাঠানো নিষেধ। নিচের বাটনে চাপ দিয়ে সরাসরি হাই-স্পিডে নামিয়ে নিন:",
        "btn_dl": "📥 সরাসরি ফুল এইচডি ডাউনলোড করুন",
        "failed": "❌ <b>ভিডিও নামানো গেল না!</b> ভিডিওটি প্রাইভেট করা, ফ্রেন্ডস-অনলি বা লিংকটি ভুল। সঠিক পাবলিক লিংক দিন!",
        "err": "⚠️ <b>সার্ভারে ত্রুটি হয়েছে।</b> লিংকটি যাচাই করে আবার চেষ্টা করুন।"
    },
    "ms": {
        "welcome": (
            "Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>Pemuat Turun Media Global Terpantas</b>\n"
            "Hantarkan sebarang pautan video dari Facebook, Instagram, TikTok, atau YouTube untuk muat turun terus dalam Full HD!\n\n"
            "🌐 <b>Disokong:</b> Facebook, Instagram, TikTok, YouTube Shorts, X/Twitter & 1000+ laman web.\n\n"
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
            "1. Salin pautan video dari FB, Insta, TikTok, atau YouTube.\n"
            "2. Hantar terus ke sembang ini.\n"
            "3. Fail <50 MB dihantar terus ke sembang.\n"
            "4. Fail >50 MB menjana butang muat turun pantas terus."
        ),
        "lang_select": "🌐 <b>Pilih Bahasa Pilihan Anda:</b>",
        "lang_changed": "✅ <b>Bahasa berjaya ditukar kepada Bahasa Melayu! 🇲🇾</b>",
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas</b>\nTaipkan mesej anda di bawah untuk dihantar terus kepada admin:",
        "feedback_success": "✅ <b>Terima kasih!</b> Maklum balas anda telah dihantar kepada admin.",
        "nonsense_warn": "🚨 <b>Hei! Ini bukan tempat borak kosong! 😂</b>\nSila hantarkan pautan <b>Facebook, TikTok, Instagram atau YouTube</b> yang sah!",
        "delivered": "🎬 <b>Video Berjaya Dihantar!</b>\n📥 Dikuasakan oleh @{admin}",
        "large_file": "📦 <b>Fail Video Besar! (> 50 MB)</b>\nTelegram mengehadkan muat naik bot. Klik butang di bawah untuk muat turun kualiti penuh terus:",
        "btn_dl": "📥 Muat Turun Kualiti Penuh",
        "failed": "❌ <b>Gagal Memuat Turun!</b> Video mungkin ditetapkan sebagai Privasi atau telah dipadamkan.",
        "err": "⚠️ <b>Ralat pemprosesan berlaku.</b> Sila sahkan pautan anda dan cuba lagi."
    }
}

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
    return DB["user_langs"].get(str(user_id), "en")

def set_user_lang(user_id: int, lang: str):
    DB["user_langs"][str(user_id)] = lang
    save_db()

def tr(user_id: int, key: str) -> str:
    lang = get_user_lang(user_id)
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, ""))

# ---------------------------------------------------------------------------
# 4. Render 24/7 Keep-Alive Server
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nahid Video Downloader Pro - 24/7 Active")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------------------------
# 5. Quad-Layer Facebook & Universal Media Engines
# ---------------------------------------------------------------------------
def clean_facebook_url(url: str) -> str:
    """Unwraps Facebook redirects and cleans tracking parameters."""
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
    """Layer 1: FDown Gateway Scraper (Bypasses Cloud IP bans)."""
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
        logger.warning(f"Facebook Layer 1 notice: {e}")
    return None

def scrape_facebook_layer2(url: str) -> str:
    """Layer 2: Direct Mobile Native Stream Regex."""
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
        logger.warning(f"Facebook Layer 2 notice: {e}")
    return None

def download_stream_to_file(stream_url: str, save_path: str) -> bool:
    """Downloads an extracted direct stream MP4 link to disk."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with requests.get(stream_url, headers=headers, stream=True, timeout=35) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return os.path.exists(save_path) and os.path.getsize(save_path) > 1000
    except Exception as e:
        logger.warning(f"Stream download error: {e}")
        return False

def download_tiktok_tikwm(url: str, save_path: str) -> bool:
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            v_url = res["data"]["play"]
            return download_stream_to_file(v_url, save_path)
    except Exception:
        pass
    return False

def download_universal_ytdlp(url: str, output_path: str):
    """Universal yt-dlp Engine configured for merged single-stream formats."""
    ydl_opts = {
        'format': 'b[ext=mp4]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.sanitize_info(info)

def fetch_direct_stream_url(url: str):
    ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url') or (info.get('requested_formats') and info['requested_formats'][0].get('url'))

# ---------------------------------------------------------------------------
# 6. Futuristic Sound Wave Equalizer (উঁচু-নিচু লাইভ অ্যানিমেশন)
# ---------------------------------------------------------------------------
EQUALIZER_WAVES = [
    " ▂▃▅▆▇█▇▆▅▃▂ ",
    "▃▅▆▇██▇▆▅▃▂  ",
    "▆▇██▇▆▅▄▃▂ ▂▃",
    "▇██▇▆▅▃▂ ▂▃▅▆",
    "▅▃▂ ▂▃▅▆▇██▇▆"
]

def format_equalizer_box(step_pct: int, frame_idx: int) -> str:
    """Renders a dynamic equalizer wave with pulsing audio bars."""
    filled = max(1, step_pct // 10)
    progress_bar = "▰" * filled + "▱" * (10 - filled)
    wave_bars = EQUALIZER_WAVES[frame_idx % len(EQUALIZER_WAVES)]

    return (
        "🎛️ <b>NAHID MEDIA ENGINE — TURBO STREAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Status:</b> <i>Fetching High-Speed Media...</i>\n"
        f"🎚️ <b>Equalizer:</b> <code>{wave_bars}</code>\n"
        "🔊 <b>Frequency:</b> <code>ılı.lıllılı.ıllı.lıllılı</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Buffer:</b> <code>[{progress_bar}] {step_pct}%</code>\n"
        "⚡ <i>Engine: Multi-Tier CDN Cloud Gateway</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

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
# 7. UI Keyboards
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
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
    ])

# ---------------------------------------------------------------------------
# 8. Command Handlers
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
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_home")]])
    await update.message.reply_text(tr(user.id, "feedback_prompt"), reply_markup=cancel_kb, parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    kb = [[InlineKeyboardButton(tr(user.id, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(f"👨‍💻 <b>Support:</b> @{ADMIN_USERNAME}", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# ---------------------------------------------------------------------------
# 9. Button Callback Dispatcher
# ---------------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    # Legacy Button Resolver
    legacy_map = {
        "my_profile": "btn_profile", "help_guide": "btn_guide", "admin_panel": "btn_admin",
        "back_home": "btn_home", "menu_home": "btn_home"
    }
    data = legacy_map.get(data, data)
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_back"), callback_data="btn_home")]])

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

    if data == "btn_feedback":
        context.user_data["feedback_mode"] = True
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_home")]])
        try:
            await query.edit_message_caption(caption=tr(user.id, "feedback_prompt"), parse_mode=ParseMode.HTML, reply_markup=cancel_kb)
        except Exception:
            await query.edit_message_text(text=tr(user.id, "feedback_prompt"), parse_mode=ParseMode.HTML, reply_markup=cancel_kb)
        return

    if data == "btn_lang":
        context.user_data["feedback_mode"] = False
        try:
            await query.edit_message_caption(caption=tr(user.id, "lang_select"), parse_mode=ParseMode.HTML, reply_markup=build_lang_menu())
        except Exception:
            await query.edit_message_text(text=tr(user.id, "lang_select"), parse_mode=ParseMode.HTML, reply_markup=build_lang_menu())

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
                f"• <b>Server Status:</b> <code>Optimal (24/7 Turbo)</code>"
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
# 10. Message Handler (Feedback & Quad-Layer Video Engine)
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

        await message.reply_text(tr(user.id, "feedback_success"), reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML)
        return

    # Video Link Protocol
    urls = re.findall(r'(https?://\S+)', raw_text)

    # Non-link Auto-Delete & Funny Warning
    if not urls:
        try:
            await message.delete()
        except Exception:
            pass

        warn_msg = await context.bot.send_message(chat_id=chat_id, text=tr(user.id, "nonsense_warn"), parse_mode=ParseMode.HTML)

        async def delete_warning_later(msg_id: int):
            await asyncio.sleep(5)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass

        asyncio.create_task(delete_warning_later(warn_msg.message_id))
        return

    # Delete User's Link to keep chat pristine
    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]

    # Initial Equalizer Banner
    proc_msg = await send_banner_safe(chat_id=chat_id, caption=format_equalizer_box(20, 0), context=context)

    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    # Live Fluctuating Equalizer Wave Animation Task
    anim_active = True
    async def run_equalizer_animation():
        stages = [(38, 1), (56, 2), (74, 3), (88, 4)]
        for s, frame in stages:
            await asyncio.sleep(1.7)
            if not anim_active:
                break
            try:
                new_box = format_equalizer_box(s, frame)
                if proc_msg.photo:
                    await proc_msg.edit_caption(caption=new_box, parse_mode=ParseMode.HTML)
                else:
                    await proc_msg.edit_text(text=new_box, parse_mode=ParseMode.HTML)
            except Exception:
                pass

    anim_task = asyncio.create_task(run_equalizer_animation())

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        loop = asyncio.get_running_loop()
        download_success = False
        direct_stream_url = None

        # -------------------------------------------------------------------
        # 1. SPECIALIZED FACEBOOK EXTRACTION ENGINE (100% Guaranteed)
        # -------------------------------------------------------------------
        if "facebook.com" in target_url or "fb.watch" in target_url:
            clean_fb = await loop.run_in_executor(None, clean_facebook_url, target_url)

            # Layer 1: FDown Gateway (Bypasses Meta IP Checkpoints)
            stream_l1 = await loop.run_in_executor(None, scrape_facebook_layer1, clean_fb)
            if stream_l1:
                direct_stream_url = stream_l1
                fb_file = str(temp_dir / "fb_video.mp4")
                download_success = await loop.run_in_executor(None, download_stream_to_file, stream_l1, fb_file)

            # Layer 2: Direct Mobile Stream Regex
            if not download_success:
                stream_l2 = await loop.run_in_executor(None, scrape_facebook_layer2, clean_fb)
                if stream_l2:
                    direct_stream_url = stream_l2
                    fb_file = str(temp_dir / "fb_video.mp4")
                    download_success = await loop.run_in_executor(None, download_stream_to_file, stream_l2, fb_file)

            # Layer 3: Optimized Single-Stream yt-dlp for Facebook
            if not download_success:
                try:
                    await loop.run_in_executor(None, download_universal_ytdlp, clean_fb, output_template)
                    download_success = True
                except Exception as e:
                    logger.warning(f"FB yt-dlp error: {e}")

        # -------------------------------------------------------------------
        # 2. UNIVERSAL ENGINE (TikTok, Instagram, YouTube, X, Pinterest)
        # -------------------------------------------------------------------
        if not download_success:
            try:
                await loop.run_in_executor(None, download_universal_ytdlp, target_url, output_template)
                download_success = True
            except Exception:
                pass

        # TikTok TikWM Fallback
        if not download_success and ("tiktok.com" in target_url or "douyin.com" in target_url):
            tiktok_file = str(temp_dir / "tiktok_video.mp4")
            download_success = await loop.run_in_executor(None, download_tiktok_tikwm, target_url, tiktok_file)

        downloaded_files = glob.glob(f"{temp_dir}/*")

        anim_active = False
        anim_task.cancel()

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

        # Large Files (>48 MB up to 500 MB): Deliver High-Speed Direct Download Link
        if not direct_stream_url:
            direct_stream_url = await loop.run_in_executor(None, fetch_direct_stream_url, target_url)

        if direct_stream_url:
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
            return

        # Extraction Failed Notification
        fail_text = tr(user.id, "failed")
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=fail_text, parse_mode=ParseMode.HTML)
            else:
                await proc_msg.edit_text(text=fail_text, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=fail_text, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.error(f"Execution Error: {exc}", exc_info=True)
        anim_active = False
        anim_task.cancel()
        err_msg = tr(user.id, "err")
        try:
            if proc_msg.photo:
                await proc_msg.edit_caption(caption=err_msg, parse_mode=ParseMode.HTML)
            else:
                await proc_msg.edit_text(text=err_msg, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=err_msg, parse_mode=ParseMode.HTML)

    finally:
        anim_active = False
        if not anim_task.done():
            anim_task.cancel()
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# 11. Main Bootstrap Engine
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

    logger.info("Nahid Video Downloader Pro is 100% ONLINE and READY!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()