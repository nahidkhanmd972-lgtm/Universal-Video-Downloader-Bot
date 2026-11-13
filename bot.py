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
# 2. Multi-Language System (Default: Global English)
# ---------------------------------------------------------------------------
STRINGS = {
    "en": {
        "welcome": (
            "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
            "⚡ <b>Fastest Universal Media Downloader</b>\n"
            "Send any public video link from Facebook, Instagram, TikTok, or YouTube to download instantly!\n\n"
            "🌐 <b>Supported:</b> Facebook, Instagram, TikTok, YouTube, X/Twitter, Pinterest & 1000+ sites.\n\n"
            "👇 <i>Use the dashboard below or click <b>[ ☰ Menu ]</b>:</i>"
        ),
        "btn_profile": "👤 My Profile",
        "btn_stats": "📊 Live Stats",
        "btn_guide": "ℹ️ Guide",
        "btn_lang": "🌐 Language",
        "btn_feedback": "✍️ Feedback / Report",
        "btn_admin": "💬 Contact Admin",
        "btn_back": "🔙 Back",
        "btn_master": "🛠️ Admin Panel",
        "stats": "📊 <b>Global Statistics</b>\n\n👥 <b>Users:</b> <code>{users:,}</code>\n📥 <b>Downloads:</b> <code>{downloads:,}</code>\n🟢 <b>Server:</b> <code>Online 24/7 (Turbo)</code>",
        "profile": "👤 <b>User Profile</b>\n\n• <b>Name:</b> {name}\n• <b>User ID:</b> <code>{user_id}</code>\n• <b>Language:</b> 🇬🇧 English\n• <b>Access:</b> <code>Unlimited Global</code>",
        "guide": "📌 <b>User Guide:</b>\n\n1. Copy any video link from FB, Insta, TikTok, or YouTube.\n2. Paste it directly into this chat.\n3. Media under 50 MB is delivered in chat.\n4. Media over 50 MB gets a fast direct download button.",
        "lang_select": "🌐 <b>Select Your Language:</b>",
        "lang_changed": "✅ <b>Language changed to English! 🇬🇧</b>",
        "feedback_prompt": "✍️ <b>Send Feedback</b>\nType your message below. It will be sent directly to the admin:",
        "feedback_success": "✅ <b>Thank you!</b> Your message has been forwarded to the admin.",
        "nonsense_warn": "🚨 <b>Hey! This isn't a chatroom! 😂</b>\nPlease send a valid <b>Facebook, TikTok, Instagram, or YouTube</b> link!",
        "fetching": "Fetching Media Stream",
        "delivered": "🎬 <b>Video Processed!</b>\n📥 Powered by @{admin}",
        "large_file": "📦 <b>Video > 50 MB!</b>\nTelegram limits bot file uploads. Click below to download original Full HD directly:",
        "btn_dl": "📥 Direct Download (Full HD)",
        "failed": "❌ <b>Extraction Failed!</b> Video may be private, age-restricted, or removed. Please verify your link!",
        "err": "⚠️ <b>Error processing video.</b> Please verify the URL and try again.",
        "quotes": [
            "Brewing your HD video like a fine cup of espresso... ☕🎬",
            "Wrestling media stream away from platform security... 🤼‍♂️💨",
            "Summoning digital sorcery: Abracadabra, pixels assemble! 🧙‍♂️✨",
            "Polishing every frame so your video sparkles in 60 FPS! ✨💎",
            "Dodging server traffic jams to deliver your file fast! 🏎️💨"
        ]
    },
    "bn": {
        "welcome": (
            "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>বিশ্বমানের অল-ইন-ওয়ান ভিডিও ডাউনলোডার</b>\n"
            "সরাসরি চ্যাটে যেকোনো পাবলিক ভিডিওর লিংক পাঠিয়ে দিন—কয়েক সেকেন্ডেই ভিডিও হাজির হবে!\n\n"
            "🌐 <b>সাপোর্টেড:</b> Facebook, Instagram Reels, TikTok, YouTube Shorts, Twitter, Pinterest ও ১০০০+ সাইট।\n\n"
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
        "stats": "📊 <b>লাইভ পরিসংখ্যান</b>\n\n👥 <b>মোট ব্যবহারকারী:</b> <code>{users:,} জন</code>\n📥 <b>মোট ডাউনলোড:</b> <code>{downloads:,} টি</code>\n🟢 <b>সার্ভার:</b> <code>Online 24/7 (সুপারফাস্ট)</code>",
        "profile": "👤 <b>ইউজার প্রোফাইল</b>\n\n• <b>নাম:</b> {name}\n• <b>আইডি:</b> <code>{user_id}</code>\n• <b>ভাষা:</b> 🇧🇩 বাংলা\n• <b>অ্যাক্সেস:</b> <code>আনলিমিটেড ফ্রি</code>",
        "guide": "📌 <b>সহজ ব্যবহারবিধি:</b>\n\n১. FB, Insta, TikTok বা YouTube-এর ভিডিও লিংক কপি করুন।\n২. সরাসরি চ্যাটে পাঠিয়ে দিন।\n৩. ৫০MB-এর ভেতরের ভিডিও সরাসরি চ্যাটে পাবেন।\n৪. ৫০MB-এর বড় ভিডিওর জন্য হাই-স্পিড ডাউনলোড লিংক পাবেন।",
        "lang_select": "🌐 <b>আপনার পছন্দের ভাষা বেছে নিন:</b>",
        "lang_changed": "✅ <b>ভাষা সফলভাবে বাংলায় পরিবর্তন করা হয়েছে! 🇧🇩</b>",
        "feedback_prompt": "✍️ <b>মতামত বা সমস্যার বিবরণ দিন</b>\nআপনার মেসেজটি নিচে লিখে পাঠান। এটি সরাসরি অ্যাডমিনের কাছে চলে যাবে:",
        "feedback_success": "✅ <b>ধন্যবাদ!</b> আপনার মতামতটি সফলভাবে অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "nonsense_warn": "🚨 <b>আরে ভাই! এটা আড্ডাবাজির জায়গা না! 😂</b>\nকাজের মতো <b>ফেসবুক, টিকটক, ইনস্টাগ্রাম বা ইউটিউব</b> লিংক পাঠান!",
        "fetching": "মিডিয়া স্ট্রিম সংগ্রহ করা হচ্ছে",
        "delivered": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large_file": "📦 <b>ভিডিওর সাইজ বিশাল! (> ৫০ MB)</b>\nটেলিগ্রাম চ্যাটে ৫০MB-এর বড় ফাইল পাঠানো নিষেধ। নিচের বাটনে চাপ দিয়ে সরাসরি হাই-স্পিডে নামিয়ে নিন:",
        "btn_dl": "📥 সরাসরি ফুল এইচডি ডাউনলোড করুন",
        "failed": "❌ <b>ভিডিও নামানো গেল না!</b> ভিডিওটি প্রাইভেট করা, ফ্রেন্ডস-অনলি বা লিংকটি ভুল। সঠিক পাবলিক লিংক দিন!",
        "unexpected_err": "⚠️ <b>সার্ভারে ত্রুটি হয়েছে।</b> লিংকটি যাচাই করে আবার চেষ্টা করুন।",
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
            "Hantarkan sebarang pautan video ke dalam sembang ini untuk memuat turun serta-merta!\n\n"
            "🌐 <b>Disokong:</b> Facebook, Instagram, TikTok, YouTube Shorts, X/Twitter & 1000+ laman web.\n\n"
            "👇 <i>Gunakan menu di bawah atau klik <b>[ ☰ Menu ]</b>:</i>"
        ),
        "btn_profile": "👤 Profil Saya",
        "btn_stats": "📊 Statistik Langsung",
        "btn_guide": "ℹ️ Cara Guna",
        "btn_lang": "🌐 Tukar Bahasa",
        "btn_feedback": "✍️ Maklum Balas",
        "btn_admin": "💬 Hubungi Admin",
        "btn_back": "🔙 Kembali",
        "btn_master": "🛠️ Panel Admin",
        "stats": "📊 <b>Statistik Langsung</b>\n\n👥 <b>Pengguna:</b> <code>{users:,}</code>\n📥 <b>Dimuat Turun:</b> <code>{downloads:,}</code>\n🟢 <b>Status:</b> <code>Dalam Talian 24/7</code>",
        "profile": "👤 <b>Profil Pengguna</b>\n\n• <b>Nama:</b> {name}\n• <b>ID Telegram:</b> <code>{user_id}</code>\n• <b>Bahasa:</b> 🇲🇾 Bahasa Melayu\n• <b>Akses:</b> <code>Akses Tanpa Had</code>",
        "guide": "📌 <b>Panduan Pengguna:</b>\n\n1. Salin pautan video dari FB, Insta, TikTok, atau YouTube.\n2. Hantar terus ke sembang ini.\n3. Fail <50 MB dihantar terus ke sembang.\n4. Fail >50 MB menjana butang muat turun pantas.",
        "lang_select": "🌐 <b>Pilih Bahasa Pilihan Anda:</b>",
        "lang_changed": "✅ <b>Bahasa berjaya ditukar kepada Bahasa Melayu! 🇲🇾</b>",
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas</b>\nTaipkan mesej anda di bawah untuk dihantar terus kepada admin:",
        "feedback_success": "✅ <b>Terima kasih!</b> Maklum balas anda telah dihantar kepada admin.",
        "nonsense_warn": "🚨 <b>Hei! Ini bukan tempat borak kosong! 😂</b>\nSila hantarkan pautan <b>Facebook, TikTok, Instagram atau YouTube</b> yang sah!",
        "fetching": "Mengambil Aliran Media",
        "delivered": "🎬 <b>Video Berjaya Dihantar!</b>\n📥 Dikuasakan oleh @{admin}",
        "large_file": "📦 <b>Fail Video Besar! (> 50 MB)</b>\nTelegram mengehadkan muat naik fail bot. Klik butang di bawah untuk muat turun kualiti penuh terus:",
        "btn_dl": "📥 Muat Turun Kualiti Penuh",
        "failed": "❌ <b>Gagal Memuat Turun!</b> Video mungkin ditetapkan sebagai Privasi atau telah dipadamkan.",
        "unexpected_err": "⚠️ <b>Ralat pemprosesan berlaku.</b> Sila sahkan pautan anda dan cuba lagi.",
        "quotes": [
            "Tunggu sebentar! Pelayan kami sedang memproses video anda... ☕⚡",
            "Menyelinap mengambil video daripada sekatan keselamatan... 🥷📦",
            "Menggilap setiap piksel supaya video anda berkilat dalam HD! ✨💎"
        ]
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
# 4. Render 24/7 Keep-Alive HTTP Server
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nahid Video Downloader Pro - Active 24/7")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------------------------
# 5. Media Scrapers & Download Engines
# ---------------------------------------------------------------------------
def clean_url(url: str) -> str:
    clean = url.split("?")[0].strip()
    if any(k in url for k in ["facebook.com/share", "fb.watch", "instagram.com/share"]):
        try:
            r = requests.get(
                url, 
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)"}, 
                allow_redirects=True, 
                timeout=8
            )
            resolved = r.url.split("?")[0]
            if "facebook.com" in resolved or "instagram.com" in resolved:
                return resolved
        except Exception:
            pass
    return clean if clean.startswith("http") else url

def scrape_facebook_native(url: str):
    """Direct regex stream scraper for Facebook mobile SD/HD MP4."""
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
    except Exception:
        pass
    return None

def download_rapidapi_tier(url: str, save_path: str) -> bool:
    """RapidAPI Universal Gateway Fallback."""
    if not RAPIDAPI_KEY:
        return False
    try:
        api_url = "https://all-in-one-media-downloader-api.p.rapidapi.com/"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "all-in-one-media-downloader-api.p.rapidapi.com",
            "Content-Type": "application/json"
        }
        resp = requests.post(api_url, json={"url": url}, headers=headers, timeout=18)
        data = resp.json()
        dl_url = data.get("download_url") or data.get("url") or (data.get("medias") and data["medias"][0].get("url"))
        if dl_url:
            r = requests.get(dl_url, stream=True, timeout=30)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception as e:
        logger.warning(f"RapidAPI fallback notice: {e}")
    return False

def download_tiktok_tikwm(url: str, save_path: str) -> bool:
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            v_url = res["data"]["play"]
            r = requests.get(v_url, stream=True, timeout=25)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception:
        pass
    return False

def download_ytdlp_smart(url: str, output_path: str):
    ydl_opts = {
        'format': 'bestvideo[height<=720][filesize<45M][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best',
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
# 6. Global UI Keyboards & Formatters
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
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="btn_home")]
    ])

def format_progress_box(user_id: int, step_pct: int, quote: str) -> str:
    filled = step_pct // 10
    progress_bar = "▓" * filled + "░" * (10 - filled)
    wave_header = "🌊" * (1 + (filled % 4))
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 <b>Nahid Video Downloader — Processing...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Status:</b> {tr(user_id, 'fetching')} {wave_header}\n"
        f"<code>[{progress_bar}] {step_pct}%</code>\n\n"
        f"💬 <i>\"{quote}\"</i>\n"
        "━━━━━━━━━━━━━━━━━━━━"
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
# 7. Command Handlers
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
    except Exception as e:
        logger.warning(f"Could not set commands: {e}")

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
# 8. Interactive Callback Dispatcher (with Legacy Button Support)
# ---------------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    # Legacy Button Mapping (Fixes old Bengali button deadlocks from previous messages)
    legacy_map = {
        "my_profile": "btn_profile",
        "help_guide": "btn_guide",
        "admin_panel": "btn_admin",
        "back_home": "btn_home",
        "menu_home": "btn_home",
        "menu_download": "btn_guide",
        "menu_platforms": "btn_guide",
        "menu_help": "btn_guide"
    }
    data = legacy_map.get(data, data)

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_back"), callback_data="btn_home")]])

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

    # Trigger Feedback Mode
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
                f"• <b>Server Status:</b> <code>Optimal (24/7)</code>"
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
# 9. Core Message Dispatcher (Feedback Routing & Video Downloader)
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

    # Feedback Routing Protocol (Direct to ADMIN_ID 8815124111)
    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False
        
        user_full_name = f"{user.first_name} {user.last_name or ''}".strip()
        user_handle = f"@{user.username}" if user.username else "No Username"
        
        admin_notification = (
            "📬 <b>New User Feedback Received!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>From:</b> {user_full_name}\n"
            f"🔗 <b>Username:</b> {user_handle}\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Comment / Issue:</b>\n\n{raw_text}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to forward feedback to admin: {e}")

        await message.reply_text(tr(user.id, "feedback_success"), reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML)
        return

    # Video Link Protocol
    urls = re.findall(r'(https?://\S+)', raw_text)

    # Smart Non-Link Auto-Delete & Funny Warning
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

    # Delete User's Link Instantly to keep chat spotless
    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]
    user_quotes = STRINGS.get(get_user_lang(user.id), STRINGS["en"])["quotes"]
    random_quote = random.choice(user_quotes)

    # Initial Animated Banner
    proc_msg = await send_banner_safe(chat_id=chat_id, caption=format_progress_box(user.id, 20, random_quote), context=context)

    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    # Animated Progress Simulation
    anim_active = True
    async def run_visual_animation():
        stages = [45, 65, 85]
        for s in stages:
            await asyncio.sleep(1.8)
            if not anim_active:
                break
            try:
                new_box = format_progress_box(user.id, s, random_quote)
                if proc_msg.photo:
                    await proc_msg.edit_caption(caption=new_box, parse_mode=ParseMode.HTML)
                else:
                    await proc_msg.edit_text(text=new_box, parse_mode=ParseMode.HTML)
            except Exception:
                pass

    anim_task = asyncio.create_task(run_visual_animation())

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        loop = asyncio.get_running_loop()
        resolved_url = await loop.run_in_executor(None, clean_url, target_url)

        download_success = False
        direct_stream_url = None

        # Tier 1: Facebook Native Regex Scraper
        if "facebook.com" in target_url or "fb.watch" in target_url:
            direct_fb = await loop.run_in_executor(None, scrape_facebook_native, target_url)
            if direct_fb:
                direct_stream_url = direct_fb
                fb_file = str(temp_dir / "fb_video.mp4")
                try:
                    r = requests.get(direct_fb, stream=True, timeout=25)
                    with open(fb_file, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                    download_success = True
                except Exception:
                    pass

        # Tier 2: yt-dlp Smart Adaptive Extractor
        if not download_success:
            try:
                await loop.run_in_executor(None, download_ytdlp_smart, resolved_url, output_template)
                download_success = True
            except Exception:
                pass

        # Tier 3: RapidAPI Gateway Fallback
        if not download_success and RAPIDAPI_KEY:
            rapid_file = str(temp_dir / "rapid_video.mp4")
            download_success = await loop.run_in_executor(None, download_rapidapi_tier, resolved_url, rapid_file)

        # Tier 4: TikTok TikWM Fallback
        if not download_success and ("tiktok.com" in resolved_url or "douyin.com" in resolved_url):
            tiktok_file = str(temp_dir / "tiktok_video.mp4")
            download_success = await loop.run_in_executor(None, download_tiktok_tikwm, resolved_url, tiktok_file)

        downloaded_files = glob.glob(f"{temp_dir}/*")

        anim_active = False
        anim_task.cancel()

        # Delivered directly in chat if <= 48 MB
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

        # Large Files (>48 MB to 500 MB): Deliver High-Speed Direct CDN Button
        if not direct_stream_url:
            direct_stream_url = await loop.run_in_executor(None, fetch_direct_stream_url, resolved_url)

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

        # Extraction Failed
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
# 10. Main Bootstrap Engine
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

    logger.info("Nahid Video Downloader Pro is officially LIVE and listening!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()