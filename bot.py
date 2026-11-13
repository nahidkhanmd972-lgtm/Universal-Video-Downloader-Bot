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
ADMIN_ID = 8815124111  # আপনার অ্যাডমিন আইডি
ADMIN_USERNAME = "NahidDevOfficial"
BOT_LOGO_URL = "https://user55725.cn.imgto.link/public/20261113/fd75766042207998416adf8f-1000482026.avif"
MAX_TELEGRAM_UPLOAD_LIMIT = 48 * 1024 * 1024
STATS_FILE = "stats.json"

# ---------------------------------------------------------------------------
# 2. Multi-Language Dictionary with Feedback System
# ---------------------------------------------------------------------------
STRINGS = {
    "en": {
        "welcome": (
            "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
            "⚡ <b>The Ultimate Global Media Downloader</b>\n"
            "Drop any video link into this chat and your media will be downloaded instantly!\n\n"
            "🌐 <b>Supported:</b> Facebook, Instagram, TikTok (No Watermark), YouTube Shorts, X/Twitter, Pinterest & 1000+ sites.\n\n"
            "👇 <i>Use the dashboard below or click <b>[ ☰ Menu ]</b>:</i>"
        ),
        "btn_profile": "👤 My Profile",
        "btn_stats": "📊 Live Statistics",
        "btn_guide": "ℹ️ How to Use",
        "btn_lang": "🌐 Change Language",
        "btn_feedback": "💬 Send Feedback / Report",
        "btn_admin": "👨‍💻 Contact Admin",
        "btn_back": "🔙 Back to Dashboard",
        "btn_master": "🛠️ Admin Master Panel",
        "stats_title": "📊 <b>Nahid Video Downloader — Global Stats</b>\n\n👥 <b>Active Users:</b> <code>{users:,}</code>\n📥 <b>Media Processed:</b> <code>{downloads:,}</code>\n🟢 <b>Server Status:</b> <code>Online 24/7 (Turbo)</code>",
        "profile_title": "👤 <b>User Account Overview</b>\n\n• <b>Name:</b> {name}\n• <b>Telegram ID:</b> <code>{user_id}</code>\n• <b>Language:</b> 🇬🇧 English\n• <b>Tier:</b> <code>Unlimited Global Access</code>",
        "guide_title": "📌 <b>Quick User Manual:</b>\n\n1. Copy any video URL from FB, Insta, TikTok, or YouTube.\n2. Paste it directly into this chat.\n3. Files under <b>50 MB</b> will be delivered in chat.\n4. Files over <b>50 MB</b> generate a high-speed direct download button.",
        "lang_select": "🌐 <b>Select Your Preferred Language:</b>\n\nChoose from the options below:",
        "lang_changed": "✅ <b>Language successfully updated to English! 🇬🇧</b>",
        "feedback_prompt": "✍️ <b>Send Feedback & Suggestions</b>\n\nPlease type your message, report, or issue below. It will be delivered directly to the bot developer!",
        "feedback_success": "✅ <b>Thank you!</b> Your feedback has been sent directly to the admin. We appreciate your support!",
        "nonsense_warn": "🚨 <b>Hey! This isn't a chatroom for nonsense! 😂</b>\n\nStop typing random gibberish and drop a valid <b>Facebook, TikTok, Instagram, or YouTube</b> link so I can get your video!",
        "processing_title": "🚀 <b>Nahid Video Downloader — Processing...</b>",
        "status_fetching": "Fetching Media Streams",
        "delivered_caption": "🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{admin}",
        "large_file_title": "📦 <b>Large Video File Detected! (> 50 MB)</b>\n\nTelegram restricts bot uploads to 50MB. Click below to download original Full HD directly:",
        "btn_direct_dl": "📥 Direct High-Speed Download (Full HD)",
        "failed_title": "❌ <b>Extraction Unsuccessful!</b>\n\nThe video might be Private, age-restricted, or removed by the platform. Please verify the URL!",
        "unexpected_err": "⚠️ <b>An unexpected processing error occurred.</b> Please verify your URL and try again.",
        "quotes": [
            "Hold your horses! Server hamsters are drinking Red Bull... 🐹⚡",
            "Brewing your HD video like a fine cup of artisan espresso... ☕🎬",
            "Wrestling the video stream away from platform security guards... 🤼‍♂️💨",
            "Summoning digital sorcery: Abracadabra, pixels assemble! 🧙‍♂️✨",
            "Even Elon Musk's Falcon 9 is jealous of our packet speed! 🚀🔥",
            "Sneaking past social media paywalls like a cyberpunk ninja... 🥷📦",
            "Polishing every frame so your video sparkles in 60 FPS! ✨💎"
        ]
    },
    "bn": {
        "welcome": (
            "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>বিশ্বমানের অল-ইন-ওয়ান ভিডিও ডাউনলোডার</b>\n"
            "সরাসরি চ্যাটে যেকোনো ভিডিওর লিংক পাঠিয়ে দিন—কয়েক সেকেন্ডেই ভিডিও হাজির হবে!\n\n"
            "🌐 <b>সাপোর্টেড:</b> Facebook, Instagram Reels, TikTok (ওয়াটারমার্ক ছাড়া), YouTube Shorts, Twitter, Pinterest ও ১০০০+ সাইট।\n\n"
            "👇 <i>নিচের ড্যাশবোর্ড অথবা <b>[ ☰ Menu ]</b> বাটন ব্যবহার করুন:</i>"
        ),
        "btn_profile": "👤 আমার প্রোফাইল",
        "btn_stats": "📊 লাইভ পরিসংখ্যান",
        "btn_guide": "ℹ️ ব্যবহারবিধি",
        "btn_lang": "🌐 ভাষা পরিবর্তন (Language)",
        "btn_feedback": "✍️ মতামত / সমস্যা জানান",
        "btn_admin": "👨‍💻 অ্যাডমিন যোগাযোগ",
        "btn_back": "🔙 ড্যাশবোর্ডে ফিরুন",
        "btn_master": "🛠️ অ্যাডমিন মাস্টার প্যানেল",
        "stats_title": "📊 <b>Nahid Video Downloader — লাইভ পরিসংখ্যান</b>\n\n👥 <b>মোট ব্যবহারকারী:</b> <code>{users:,} জন</code>\n📥 <b>মোট ডাউনলোড:</b> <code>{downloads:,} টি</code>\n🟢 <b>সার্ভার স্ট্যাটাস:</b> <code>Online 24/7 (সুপারফাস্ট)</code>",
        "profile_title": "👤 <b>ইউজার প্রোফাইল বিবরণ</b>\n\n• <b>নাম:</b> {name}\n• <b>টেলিগ্রাম আইডি:</b> <code>{user_id}</code>\n• <b>নির্বাচিত ভাষা:</b> 🇧🇩 বাংলা\n• <b>অ্যাক্সেস:</b> <code>আনলিমিটেড ফ্রি ইউজার</code>",
        "guide_title": "📌 <b>সহজ ব্যবহারবিধি:</b>\n\n১. FB, Insta, TikTok বা YouTube-এর যেকোনো ভিডিও লিংক কপি করুন।\n২. চ্যাটে সরাসরি লিংকটি পেস্ট করে সেন্ড করুন।\n৩. ৫০MB-এর ভেতরের ভিডিও সরাসরি চ্যাটে পাবেন।\n৪. ৫০MB-এর বড় ভিডিওর জন্য হাই-স্পিড ডাইরেক্ট ডাউনলোড বাটন পাবেন।",
        "lang_select": "🌐 <b>আপনার পছন্দের ভাষা বেছে নিন:</b>\n\nনিচের যেকোনো একটি বাটনে চাপ দিন:",
        "lang_changed": "✅ <b>ভাষা সফলভাবে বাংলায় পরিবর্তন করা হয়েছে! 🇧🇩</b>",
        "feedback_prompt": "✍️ <b>মতামত ও ফিডব্যাক</b>\n\nআপনার যেকোনো মতামত, অভিযোগ বা পরামর্শ নিচে লিখে পাঠান। আপনার মেসেজটি সরাসরি অ্যাডমিনের কাছে পৌঁছে যাবে!",
        "feedback_success": "✅ <b>ধন্যবাদ!</b> আপনার মূল্যবান মতামতটি সফলভাবে অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "nonsense_warn": "🚨 <b>আরে ভাই! এটা আড্ডাবাজির জায়গা না! 😂</b>\n\nআজেবাজে টেক্সট না পাঠিয়ে কাজের মতো <b>ফেসবুক, টিকটক, ইনস্টাগ্রাম বা ইউটিউব</b> লিংক পাঠান!",
        "processing_title": "🚀 <b>Nahid Video Downloader — প্রসেসিং হচ্ছে...</b>",
        "status_fetching": "মিডিয়া স্ট্রিম নামানো হচ্ছে",
        "delivered_caption": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large_file_title": "📦 <b>ভিডিও সাইজ বিশাল! (> ৫০ MB)</b>\n\nটেলিগ্রাম চ্যাটে ৫০MB-এর বড় ভিডিও পাঠানো নিষেধ। নিচের বাটনে চাপ দিয়ে ফুল স্পিডে নামিয়ে নিন:",
        "btn_direct_dl": "📥 সরাসরি ফুল এইচডি ডাউনলোড করুন",
        "failed_title": "❌ <b>ভিডিও নামানো গেল না!</b>\n\nভিডিওটি প্রাইভেট করা, বয়স-সীমাবদ্ধ বা প্ল্যাটফর্ম থেকে মুছে ফেলা হয়েছে। সঠিক পাবলিক লিংক দিন!",
        "unexpected_err": "⚠️ <b>সার্ভারে অপ্রত্যাশিত ত্রুটি হয়েছে।</b> দয়া করে লিংকটি আবার যাচাই করে পাঠান।",
        "quotes": [
            "এক কাপ চা খেয়ে একটু হাসুন! ভিডিও নামাতে গিয়ে সার্ভারের তো প্রায় ঘাম ছুটে গেছে... ☕🎬",
            "ধরো ধরো! ভিডিও চোর লিংক নিয়ে রকেটের বেগে দৌড় দিয়েছে আপনার দিকে... 🏃‍♂️💨",
            "জাদুকরী মন্ত্র পড়া চলছে: আব্রাবি-কা-ডাব্রা, ভিডিও হয়ে যা উধাও থেকে হাজির! 🧙‍♂️✨",
            "ইলন মাস্কের রকেটও লজ্জা পাবে ভাই, একটু ফুরফুরে মেজাজে অপেক্ষা করুন... 🚀🔥",
            "বানর নাচ দেখতে দেখতেই ভিডিও ডাউনলোড হয়ে যাবে, একটু চিল করুন বস! 🐒🍿",
            "ভিডিওটা একটু সাজুগুজু করছে, মেকআপ শেষ হলেই ইনবক্সে ঢুকবে! 💃💎"
        ]
    },
    "ms": {
        "welcome": (
            "Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀🤖\n\n"
            "⚡ <b>Pemuat Turun Media Global Terbaik</b>\n"
            "Hantarkan sebarang pautan video ke dalam sembang ini dan video anda akan dimuat turun serta-merta!\n\n"
            "🌐 <b>Disokong:</b> Facebook, Instagram, TikTok (Tanpa Tanda Air), YouTube Shorts, X/Twitter, Pinterest & 1000+ laman web.\n\n"
            "👇 <i>Gunakan papan pemuka di bawah atau klik <b>[ ☰ Menu ]</b>:</i>"
        ),
        "btn_profile": "👤 Profil Saya",
        "btn_stats": "📊 Statistik Langsung",
        "btn_guide": "ℹ️ Cara Penggunaan",
        "btn_lang": "🌐 Tukar Bahasa",
        "btn_feedback": "✍️ Hantar Maklum Balas",
        "btn_admin": "👨‍💻 Hubungi Admin",
        "btn_back": "🔙 Kembali ke Menu",
        "btn_master": "🛠️ Panel Induk Admin",
        "stats_title": "📊 <b>Nahid Video Downloader — Statistik Langsung</b>\n\n👥 <b>Pengguna Aktif:</b> <code>{users:,}</code>\n📥 <b>Media Diproses:</b> <code>{downloads:,}</code>\n🟢 <b>Status Pelayan:</b> <code>Dalam Talian 24/7 (Pantas)</code>",
        "profile_title": "👤 <b>Gambaran Keseluruhan Akaun</b>\n\n• <b>Nama:</b> {name}\n• <b>ID Telegram:</b> <code>{user_id}</code>\n• <b>Bahasa:</b> 🇲🇾 Bahasa Melayu\n• <b>Akses:</b> <code>Akses Global Tanpa Had</code>",
        "guide_title": "📌 <b>Panduan Pantas Pengguna:</b>\n\n1. Salin sebarang pautan video dari FB, Insta, TikTok, atau YouTube.\n2. Tampal terus ke dalam sembang ini.\n3. Fail di bawah <b>50 MB</b> akan dihantar terus ke sembang.\n4. Fail melebihi <b>50 MB</b> akan menghasilkan butang muat turun pantas.",
        "lang_select": "🌐 <b>Pilih Bahasa Pilihan Anda:</b>\n\nPilih daripada pilihan di bawah:",
        "lang_changed": "✅ <b>Bahasa berjaya ditukar kepada Bahasa Melayu! 🇲🇾</b>",
        "feedback_prompt": "✍️ <b>Maklum Balas & Sokongan</b>\n\nSila taipkan mesej, aduan, atau cadangan anda di bawah. Ia akan dihantar terus kepada pembangun bot!",
        "feedback_success": "✅ <b>Terima kasih!</b> Maklum balas anda telah dihantar terus kepada admin. Kami menghargai sokongan anda!",
        "nonsense_warn": "🚨 <b>Hei! Ini bukan tempat berborak kosong! 😂</b>\n\nBerhenti taip benda mengarut dan hantarkan pautan <b>Facebook, TikTok, Instagram atau YouTube</b> yang sah!",
        "processing_title": "🚀 <b>Nahid Video Downloader — Memproses...</b>",
        "status_fetching": "Mengambil Aliran Media",
        "delivered_caption": "🎬 <b>Video Berjaya Dihantar!</b>\n📥 Dikuasakan oleh @{admin}",
        "large_file_title": "📦 <b>Fail Video Bersaiz Besar Dikesan! (> 50 MB)</b>\n\nTelegram mengehadkan muat naik fail bot kepada 50MB. Klik butang di bawah untuk muat turun terus kualiti penuh:",
        "btn_direct_dl": "📥 Muat Turun Terus Kualiti Penuh",
        "failed_title": "❌ <b>Gagal Memuat Turun!</b>\n\nVideo mungkin Ditetapkan Peribadi, sekatan umur, atau telah dipadamkan. Sila sahkan pautan anda!",
        "unexpected_err": "⚠️ <b>Ralat pemprosesan tidak dijangka berlaku.</b> Sila sahkan pautan anda dan cuba lagi.",
        "quotes": [
            "Tunggu sebentar! Hamster pelayan kami sedang minum kopi pekat... 🐹⚡",
            "Sedang menyelinap mengambil video daripada pengawal keselamatan... 🥷📦",
            "Roket Elon Musk pun kalah dengan kelajuan muat turun kami! 🚀🔥",
            "Menggilap setiap piksel supaya video anda berkilat dalam HD! ✨💎",
            "Sedikit masa lagi! Sediakan bertih jagung anda untuk menonton! 🍿🎉"
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
    return DB["user_langs"].get(str(user_id), "en")

def set_user_lang(user_id: int, lang_code: str):
    DB["user_langs"][str(user_id)] = lang_code
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
        self.wfile.write(b"Nahid Video Downloader Pro - 24/7 Engine Active")

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
    if "facebook.com/share" in url or "fb.watch" in url:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True, timeout=6)
            resolved = r.url.split("?")[0]
            if "facebook.com" in resolved:
                return resolved
        except Exception:
            pass
    return clean if clean.startswith("http") else url

def scrape_facebook_native(url: str):
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
            match = re.search(p, html)
            if match:
                raw = match.group(1)
                clean = raw.encode('utf-8').decode('unicode-escape').replace('\\/', '/').replace('&amp;', '&')
                if clean.startswith("http"):
                    return clean
    except Exception:
        pass
    return None

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
        [InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
        [InlineKeyboardButton("🇧🇩 বাংলা (Bengali)", callback_data="setlang_bn")],
        [InlineKeyboardButton("🇲🇾 Bahasa Melayu (Malay)", callback_data="setlang_ms")],
        [InlineKeyboardButton("🔙 Back / পেছনে", callback_data="btn_home")]
    ])

def format_progress_box(user_id: int, step_pct: int, quote: str) -> str:
    filled = step_pct // 10
    progress_bar = "▓" * filled + "░" * (10 - filled)
    wave_header = "🌊" * (1 + (filled % 4))
    
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{tr(user_id, 'processing_title')}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Status:</b> {tr(user_id, 'status_fetching')} {wave_header}\n"
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
# 7. Command Handlers & Callbacks
# ---------------------------------------------------------------------------
async def set_menu_commands(application):
    commands = [
        BotCommand("start", "🚀 Start / Refresh Main Dashboard"),
        BotCommand("feedback", "✍️ Send Feedback / Report Issue"),
        BotCommand("lang", "🌐 Change Language / ভাষা / Bahasa"),
        BotCommand("stats", "📊 View Global Bot Statistics"),
        BotCommand("profile", "👤 View Personal Profile"),
        BotCommand("admin", "💬 Contact Verified Admin")
    ]
    await application.bot.set_my_commands(commands)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    DB["unique_users"].add(user.id)
    save_db()

    # Reset any active feedback state
    context.user_data["waiting_for_feedback"] = False

    welcome_text = tr(user.id, "welcome").format(name=user.first_name)

    try:
        await update.message.delete()
    except Exception:
        pass

    await send_banner_safe(update.effective_chat.id, welcome_text, build_main_menu(user.id), context)

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["waiting_for_feedback"] = True
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel / বাতিল", callback_data="btn_home")]])
    await update.message.reply_text(
        tr(user.id, "feedback_prompt"),
        reply_markup=cancel_kb,
        parse_mode=ParseMode.HTML
    )

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["waiting_for_feedback"] = False
    await update.message.reply_text(
        tr(user.id, "lang_select"),
        reply_markup=build_lang_menu(),
        parse_mode=ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["waiting_for_feedback"] = False
    text = tr(user.id, "stats_title").format(
        users=len(DB["unique_users"]),
        downloads=DB["total_downloads"]
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["waiting_for_feedback"] = False
    text = tr(user.id, "profile_title").format(
        name=f"{user.first_name} {user.last_name or ''}".strip(),
        user_id=user.id
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["waiting_for_feedback"] = False
    kb = [[InlineKeyboardButton(tr(user.id, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(
        f"👨‍💻 <b>Nahid Video Downloader Support</b>\n\nDirect contact: @{ADMIN_USERNAME}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.HTML
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_back"), callback_data="btn_home")]])

    # Language Switcher
    if data.startswith("setlang_"):
        new_lang = data.replace("setlang_", "")
        set_user_lang(user.id, new_lang)
        welcome_text = tr(user.id, "welcome").format(name=user.first_name)
        try:
            await query.edit_message_caption(
                caption=f"{tr(user.id, 'lang_changed')}\n\n{welcome_text}",
                parse_mode=ParseMode.HTML,
                reply_markup=build_main_menu(user.id)
            )
        except Exception:
            await query.edit_message_text(
                text=f"{tr(user.id, 'lang_changed')}\n\n{welcome_text}",
                parse_mode=ParseMode.HTML,
                reply_markup=build_main_menu(user.id)
            )
        return

    # Trigger Feedback Mode
    if data == "btn_feedback":
        context.user_data["waiting_for_feedback"] = True
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel / বাতিল", callback_data="btn_home")]])
        try:
            await query.edit_message_caption(
                caption=tr(user.id, "feedback_prompt"),
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_kb
            )
        except Exception:
            await query.edit_message_text(
                text=tr(user.id, "feedback_prompt"),
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_kb
            )
        return

    if data == "btn_lang":
        context.user_data["waiting_for_feedback"] = False
        try:
            await query.edit_message_caption(caption=tr(user.id, "lang_select"), parse_mode=ParseMode.HTML, reply_markup=build_lang_menu())
        except Exception:
            await query.edit_message_text(text=tr(user.id, "lang_select"), parse_mode=ParseMode.HTML, reply_markup=build_lang_menu())

    elif data == "btn_stats":
        context.user_data["waiting_for_feedback"] = False
        text = tr(user.id, "stats_title").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"])
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_profile":
        context.user_data["waiting_for_feedback"] = False
        text = tr(user.id, "profile_title").format(name=f"{user.first_name} {user.last_name or ''}".strip(), user_id=user.id)
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_guide":
        context.user_data["waiting_for_feedback"] = False
        text = tr(user.id, "guide_title")
        try:
            await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        except Exception:
            await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=back_kb)

    elif data == "btn_admin":
        context.user_data["waiting_for_feedback"] = False
        if user.id == ADMIN_ID:
            stats_text = (
                f"🛠️ <b>Master Developer Control Panel</b>\n\n"
                f"• <b>Total Users:</b> <code>{len(DB['unique_users'])}</code>\n"
                f"• <b>Completed Downloads:</b> <code>{DB['total_downloads']}</code>\n"
                f"• <b>Admin ID:</b> <code>{ADMIN_ID}</code>\n"
                f"• <b>Server Status:</b> <code>Optimal (24/7)</code>"
            )
            try:
                await query.edit_message_caption(caption=stats_text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
            except Exception:
                await query.edit_message_text(text=stats_text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
        else:
            await query.answer("Access Restricted: Administrator Only!", show_alert=True)

    elif data == "btn_home":
        context.user_data["waiting_for_feedback"] = False
        welcome_text = tr(user.id, "welcome").format(name=user.first_name)
        try:
            await query.edit_message_caption(caption=welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))
        except Exception:
            await query.edit_message_text(text=welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu(user.id))

# ---------------------------------------------------------------------------
# 8. Core Message Dispatcher (Feedback Routing & Video Downloader)
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

    # -----------------------------------------------------------------------
    # FEEDBACK ROUTING SYSTEM: Forwards message directly to ADMIN_ID (8815124111)
    # -----------------------------------------------------------------------
    if context.user_data.get("waiting_for_feedback"):
        context.user_data["waiting_for_feedback"] = False
        
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
        
        # অ্যাডমিনের কাছে মেসেজ পাঠানো
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_notification,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to forward feedback to admin: {e}")

        # ইউজারকে ধন্যবাদ বার্তা দেওয়া
        await message.reply_text(
            tr(user.id, "feedback_success"),
            reply_markup=build_main_menu(user.id),
            parse_mode=ParseMode.HTML
        )
        return

    # -----------------------------------------------------------------------
    # VIDEO LINK PROCESSING PROTOCOL
    # -----------------------------------------------------------------------
    urls = re.findall(r'(https?://\S+)', raw_text)

    # Smart Auto-Delete & Non-Link Warning
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

    # Delete User's Link Instantly to keep chat spotless
    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]
    user_quotes = STRINGS.get(get_user_lang(user.id), STRINGS["en"])["quotes"]
    random_quote = random.choice(user_quotes)

    # Animated Processing Box with Logo
    proc_msg = await send_banner_safe(
        chat_id=chat_id,
        caption=format_progress_box(user.id, 20, random_quote),
        context=context
    )

    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

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

        # Tier 1: Facebook Native Scraper
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

        # Tier 2: yt-dlp Smart Extractor
        if not download_success:
            try:
                await loop.run_in_executor(None, download_ytdlp_smart, resolved_url, output_template)
                download_success = True
            except Exception:
                pass

        # Tier 3: TikTok TikWM Fallback
        if not download_success and ("tiktok.com" in resolved_url or "douyin.com" in resolved_url):
            tiktok_file = str(temp_dir / "tiktok_video.mp4")
            download_success = await loop.run_in_executor(None, download_tiktok_tikwm, resolved_url, tiktok_file)

        downloaded_files = glob.glob(f"{temp_dir}/*")

        anim_active = False
        anim_task.cancel()

        # Delivered via Telegram if <= 48 MB
        if download_success and downloaded_files:
            video_path = downloaded_files[0]
            file_size = os.path.getsize(video_path)

            if file_size <= MAX_TELEGRAM_UPLOAD_LIMIT:
                DB["total_downloads"] += 1
                save_db()
                with open(video_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_file,
                        caption=tr(user.id, "delivered_caption").format(admin=ADMIN_USERNAME),
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
            kb = [[InlineKeyboardButton(tr(user.id, "btn_direct_dl"), url=direct_stream_url)]]
            large_caption = tr(user.id, "large_file_title")
            try:
                if proc_msg.photo:
                    await proc_msg.edit_caption(caption=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await proc_msg.edit_text(text=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=large_caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        # Extraction Failed
        fail_text = tr(user.id, "failed_title")
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
        err_msg = tr(user.id, "unexpected_err")
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
# 9. Main Bootstrap Engine
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.critical("BOT_TOKEN is not configured!")
        return

    # Start 24/7 Render keep-alive server
    threading.Thread(target=run_http_server, daemon=True).start()

    custom_request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=60.0
    )

    application = ApplicationBuilder().token(TOKEN).request(custom_request).post_init(set_menu_commands).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming_message))

    logger.info("Nahid Video Downloader Pro (with Feedback Engine) is running!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()