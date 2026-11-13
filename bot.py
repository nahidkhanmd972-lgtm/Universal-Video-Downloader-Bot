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

# Credentials (set in Render > Environment)
TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "youtube-media-downloader.p.rapidapi.com")
# Optional second API for Facebook/Instagram/others (leave empty to skip)
GENERIC_API_HOST = os.getenv("GENERIC_API_HOST", "")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8815124111"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "NahidDevOfficial")
BOT_LOGO_URL = os.getenv(
    "BOT_LOGO_URL",
    "https://user55725.cn.imgto.link/public/20261113/fd75766042207998416adf8f-1000482026.avif"
)
MAX_UPLOAD_LIMIT = 48 * 1024 * 1024
STATS_FILE = "stats.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

ACTIVE_CANCELS = {}
JOB_PROGRESS = {}

# ---------------------------------------------------------------------------
# 2. 20 Witty Loading Messages
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
# 3. Languages (English default; other languages override what they define)
# ---------------------------------------------------------------------------
LANG_NAMES = {
    "en": "🇬🇧 English", "bn": "🇧🇩 বাংলা", "hi": "🇮🇳 हिन्दी", "ur": "🇵🇰 اردو",
    "ar": "🇸🇦 العربية", "ms": "🇲🇾 Melayu", "id": "🇮🇩 Indonesia", "tr": "🇹🇷 Türkçe",
    "es": "🇪🇸 Español", "fr": "🇫🇷 Français", "ru": "🇷🇺 Русский", "pt": "🇧🇷 Português",
}

EN = {
    "welcome": (
        "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n"
        "⚡ <b>The Ultimate Global Media Downloader</b>\n"
        "Drop any public video link from YouTube, Facebook, Instagram, or TikTok to download instantly in HD!\n\n"
        "🌐 <b>Platforms Supported:</b>\n"
        "• <b>YouTube</b> (Shorts, Songs & Standard Videos)\n"
        "• <b>Facebook</b> (Reels, Watch, Long Videos)\n"
        "• <b>Instagram</b> (Reels, Posts & Stories)\n"
        "• <b>TikTok</b> (Watermark-free)\n"
        "• <b>X/Twitter, Pinterest, Threads</b> & 1000+ more.\n\n"
        "👇 <i>Use the dashboard below or click <b>[ ☰ Menu ]</b>:</i>"
    ),
    "btn_profile": "👤 My Profile", "btn_stats": "📊 Live Statistics", "btn_guide": "ℹ️ User Guide",
    "btn_lang": "🌐 Language", "btn_feedback": "✍️ Feedback / Report", "btn_admin": "💬 Contact Admin",
    "btn_back": "🔙 Back to Menu", "btn_master": "🛠️ Admin Master Panel", "btn_cancel": "❌ Cancel",
    "btn_dl": "📥 Direct High-Speed Download",
    "btn_portal": "🌐 Open Web Download Portal",
    "stats": (
        "📊 <b>Nahid Video Downloader — Global Stats</b>\n\n"
        "👥 <b>Total Active Users:</b> <code>{users:,}</code>\n"
        "📥 <b>Total Media Processed:</b> <code>{downloads:,}</code>\n"
        "🟢 <b>Server Status:</b> <code>Online 24/7 (Turbo)</code>\n"
        "⚡ <b>Engine Health:</b> <code>Multi-Layer Anti-Bot Active</code>"
    ),
    "profile": (
        "👤 <b>User Account Overview</b>\n\n"
        "• <b>Name:</b> {name}\n"
        "• <b>User ID:</b> <code>{user_id}</code>\n"
        "• <b>Language:</b> {lang}\n"
        "• <b>Access Tier:</b> <code>Unlimited Turbo Access</code>"
    ),
    "guide": (
        "📌 <b>Quick User Manual:</b>\n\n"
        "1. Copy any video URL from YouTube, Facebook, Instagram, or TikTok.\n"
        "2. Paste it directly into this chat.\n"
        "3. Media under <b>50 MB</b> is delivered in chat with instant streaming.\n"
        "4. Large media over <b>50 MB</b> generates a high-speed direct download link."
    ),
    "choose_lang": "🌐 <b>Choose your language:</b>",
    "lang_changed": "✅ <b>Language changed!</b>",
    "feedback_prompt": "✍️ <b>Send Feedback & Suggestions</b>\nType your message below. It will be sent directly to the admin:",
    "feedback_ok": "✅ <b>Thank you!</b> Your message has been forwarded directly to the admin.",
    "invalid": "🚨 <b>Hey! This isn't a chatroom for nonsense! 😂</b>\nPlease send a valid <b>YouTube, Facebook, TikTok, or Instagram</b> link!",
    "delivered": "🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{admin}",
    "large": (
        "📦 <b>Large Video File Detected! (> 50 MB)</b>\n\n"
        "Telegram restricts bot uploads over 50MB. Click below to download directly:"
    ),
    "failed": (
        "❌ <b>Extraction Failed!</b>\n\n"
        "The video may be private, age-restricted, or removed. You can also try the web portal below:"
    ),
    "cancelled": "❌ <b>Download Cancelled!</b>\nThe operation was terminated by user.",
    "status": "Downloading High-Speed Media...",
}

L10N = {
    "bn": {
        "welcome": "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀\n\n⚡ YouTube, Facebook, Instagram বা TikTok-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠান, আমি HD-তে নামিয়ে দেব।\n\n👇 নিচের মেনু ব্যবহার করুন বা লিংক পেস্ট করুন।",
        "btn_profile": "👤 আমার প্রোফাইল", "btn_stats": "📊 লাইভ পরিসংখ্যান", "btn_guide": "ℹ️ ব্যবহারবিধি",
        "btn_lang": "🌐 ভাষা", "btn_feedback": "✍️ মতামত / সমস্যা", "btn_admin": "💬 অ্যাডমিন",
        "btn_back": "🔙 ফিরে যান", "btn_cancel": "❌ বাতিল", "btn_dl": "📥 সরাসরি ডাউনলোড করুন",
        "btn_portal": "🌐 ওয়েব ডাউনলোড পোর্টাল",
        "stats": "📊 <b>লাইভ পরিসংখ্যান</b>\n\n👥 ব্যবহারকারী: <code>{users:,}</code>\n📥 ডাউনলোড: <code>{downloads:,}</code>\n🟢 সার্ভার: <code>Online 24/7</code>",
        "guide": "📌 <b>ব্যবহারবিধি</b>\n\n১. যেকোনো ভিডিওর লিংক কপি করুন।\n২. এখানে পেস্ট করুন।\n৩. ৫০MB-এর কম হলে চ্যাটেই ভিডিও পাবেন।\n৪. বড় হলে ডাইরেক্ট ডাউনলোড বাটন আসবে।",
        "choose_lang": "🌐 <b>আপনার ভাষা বেছে নিন:</b>", "lang_changed": "✅ <b>ভাষা পরিবর্তন হয়েছে!</b>",
        "feedback_prompt": "✍️ <b>মতামত লিখুন</b>\nআপনার মেসেজ সরাসরি অ্যাডমিনের কাছে যাবে:",
        "feedback_ok": "✅ <b>ধন্যবাদ!</b> অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "invalid": "🚨 <b>আরে ভাই! এটা আড্ডার জায়গা না! 😂</b>\nসঠিক <b>YouTube, Facebook, TikTok বা Instagram</b> লিংক পাঠান!",
        "delivered": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>ভিডিও বড় (> ৫০ MB)</b>\n\nনিচের বাটনে চাপ দিয়ে সরাসরি ডাউনলোড করুন:",
        "failed": "❌ <b>ভিডিও আনা যায়নি!</b>\n\nভিডিওটি প্রাইভেট বা মুছে ফেলা হতে পারে। নিচের ওয়েব পোর্টালও চেষ্টা করতে পারেন:",
        "cancelled": "❌ <b>ডাউনলোড বাতিল করা হয়েছে!</b>", "status": "ডাউনলোড হচ্ছে...",
    },
    "hi": {
        "welcome": "<b>Nahid Video Downloader Pro</b> में स्वागत है, <b>{name}</b>! 🚀\n\nYouTube, Facebook, Instagram या TikTok का कोई भी पब्लिक वीडियो लिंक भेजें, मैं HD में डाउनलोड कर दूँगा।",
        "btn_lang": "🌐 भाषा", "btn_back": "🔙 वापस", "btn_cancel": "❌ रद्द करें", "btn_dl": "📥 सीधा डाउनलोड",
        "choose_lang": "🌐 <b>अपनी भाषा चुनें:</b>", "lang_changed": "✅ <b>भाषा बदल गई!</b>",
        "invalid": "🚨 कृपया सही वीडियो लिंक भेजें।", "delivered": "🎬 <b>हो गया!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>वीडियो बड़ा है (> 50 MB)</b>\n\nनीचे बटन दबाकर डाउनलोड करें:",
        "failed": "❌ <b>वीडियो नहीं मिला!</b>\n\nवीडियो प्राइवेट या हटाया हुआ हो सकता है।",
        "cancelled": "❌ <b>डाउनलोड रद्द।</b>", "status": "डाउनलोड हो रहा है...",
    },
    "ur": {
        "welcome": "<b>Nahid Video Downloader Pro</b> میں خوش آمدید، <b>{name}</b>! 🚀\n\nیوٹیوب، فیس بک، انسٹاگرام یا ٹک ٹاک کی ویڈیو کا لنک بھیجیں۔",
        "btn_lang": "🌐 زبان", "btn_back": "🔙 واپس", "btn_cancel": "❌ منسوخ", "btn_dl": "📥 ڈاؤن لوڈ",
        "choose_lang": "🌐 <b>اپنی زبان منتخب کریں:</b>", "lang_changed": "✅ <b>زبان تبدیل ہو گئی!</b>",
        "invalid": "🚨 براہ کرم درست ویڈیو لنک بھیجیں۔", "delivered": "🎬 <b>مکمل!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>ویڈیو بڑی ہے (> 50 MB)</b>\n\nنیچے بٹن دبا کر ڈاؤن لوڈ کریں:",
        "failed": "❌ <b>ویڈیو حاصل نہیں ہو سکی!</b>", "cancelled": "❌ <b>منسوخ کر دیا گیا۔</b>", "status": "ڈاؤن لوڈ ہو رہا ہے...",
    },
    "ar": {
        "welcome": "مرحباً بك في <b>Nahid Video Downloader Pro</b> يا <b>{name}</b>! 🚀\n\nأرسل رابط أي فيديو عام من يوتيوب أو فيسبوك أو انستغرام أو تيك توك.",
        "btn_lang": "🌐 اللغة", "btn_back": "🔙 رجوع", "btn_cancel": "❌ إلغاء", "btn_dl": "📥 تحميل مباشر",
        "choose_lang": "🌐 <b>اختر لغتك:</b>", "lang_changed": "✅ <b>تم تغيير اللغة!</b>",
        "invalid": "🚨 أرسل رابط فيديو صحيح.", "delivered": "🎬 <b>تم!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>الفيديو كبير (> 50 MB)</b>\n\nاضغط الزر للتحميل:",
        "failed": "❌ <b>تعذر جلب الفيديو!</b>", "cancelled": "❌ <b>تم الإلغاء.</b>", "status": "جارٍ التحميل...",
    },
    "ms": {
        "welcome": "Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀\n\nHantar pautan video dari YouTube, Facebook, Instagram atau TikTok untuk muat turun dalam HD.",
        "btn_lang": "🌐 Bahasa", "btn_back": "🔙 Kembali", "btn_cancel": "❌ Batal", "btn_dl": "📥 Muat Turun",
        "choose_lang": "🌐 <b>Pilih bahasa anda:</b>", "lang_changed": "✅ <b>Bahasa ditukar!</b>",
        "invalid": "🚨 Sila hantar pautan video yang sah.", "delivered": "🎬 <b>Siap!</b>\n📥 Dikuasakan oleh @{admin}",
        "large": "📦 <b>Video besar (> 50 MB)</b>\n\nTekan butang untuk muat turun:",
        "failed": "❌ <b>Video tidak dapat diambil!</b>", "cancelled": "❌ <b>Dibatalkan.</b>", "status": "Sedang memuat turun...",
    },
    "id": {
        "welcome": "Selamat datang di <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀\n\nKirim tautan video YouTube, Facebook, Instagram atau TikTok untuk diunduh dalam HD.",
        "btn_lang": "🌐 Bahasa", "btn_back": "🔙 Kembali", "btn_cancel": "❌ Batal", "btn_dl": "📥 Unduh Langsung",
        "choose_lang": "🌐 <b>Pilih bahasa Anda:</b>", "lang_changed": "✅ <b>Bahasa diubah!</b>",
        "invalid": "🚨 Kirim tautan video yang valid.", "delivered": "🎬 <b>Selesai!</b>\n📥 Didukung oleh @{admin}",
        "large": "📦 <b>Video besar (> 50 MB)</b>\n\nTekan tombol untuk mengunduh:",
        "failed": "❌ <b>Video tidak dapat diambil!</b>", "cancelled": "❌ <b>Dibatalkan.</b>", "status": "Mengunduh...",
    },
    "tr": {
        "welcome": "<b>Nahid Video Downloader Pro</b>'ya hoş geldin, <b>{name}</b>! 🚀\n\nYouTube, Facebook, Instagram veya TikTok video bağlantısını gönder, HD indireyim.",
        "btn_lang": "🌐 Dil", "btn_back": "🔙 Geri", "btn_cancel": "❌ İptal", "btn_dl": "📥 Doğrudan İndir",
        "choose_lang": "🌐 <b>Dilini seç:</b>", "lang_changed": "✅ <b>Dil değiştirildi!</b>",
        "invalid": "🚨 Geçerli bir video bağlantısı gönder.", "delivered": "🎬 <b>Tamam!</b>\n📥 @{admin}",
        "large": "📦 <b>Video büyük (> 50 MB)</b>\n\nİndirmek için düğmeye bas:",
        "failed": "❌ <b>Video alınamadı!</b>", "cancelled": "❌ <b>İptal edildi.</b>", "status": "İndiriliyor...",
    },
    "es": {
        "welcome": "¡Bienvenido a <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀\n\nEnvía un enlace de YouTube, Facebook, Instagram o TikTok y lo descargo en HD.",
        "btn_lang": "🌐 Idioma", "btn_back": "🔙 Volver", "btn_cancel": "❌ Cancelar", "btn_dl": "📥 Descarga directa",
        "choose_lang": "🌐 <b>Elige tu idioma:</b>", "lang_changed": "✅ <b>¡Idioma cambiado!</b>",
        "invalid": "🚨 Envía un enlace de video válido.", "delivered": "🎬 <b>¡Listo!</b>\n📥 @{admin}",
        "large": "📦 <b>Video grande (> 50 MB)</b>\n\nPulsa el botón para descargar:",
        "failed": "❌ <b>No se pudo obtener el video.</b>", "cancelled": "❌ <b>Cancelado.</b>", "status": "Descargando...",
    },
    "fr": {
        "welcome": "Bienvenue sur <b>Nahid Video Downloader Pro</b>, <b>{name}</b> ! 🚀\n\nEnvoyez un lien YouTube, Facebook, Instagram ou TikTok, je le télécharge en HD.",
        "btn_lang": "🌐 Langue", "btn_back": "🔙 Retour", "btn_cancel": "❌ Annuler", "btn_dl": "📥 Téléchargement direct",
        "choose_lang": "🌐 <b>Choisissez votre langue :</b>", "lang_changed": "✅ <b>Langue modifiée !</b>",
        "invalid": "🚨 Envoyez un lien vidéo valide.", "delivered": "🎬 <b>Terminé !</b>\n📥 @{admin}",
        "large": "📦 <b>Vidéo volumineuse (> 50 MB)</b>\n\nAppuyez sur le bouton pour télécharger :",
        "failed": "❌ <b>Impossible de récupérer la vidéo.</b>", "cancelled": "❌ <b>Annulé.</b>", "status": "Téléchargement...",
    },
    "ru": {
        "welcome": "Добро пожаловать в <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀\n\nОтправьте ссылку на видео из YouTube, Facebook, Instagram или TikTok, и я скачаю его в HD.",
        "btn_lang": "🌐 Язык", "btn_back": "🔙 Назад", "btn_cancel": "❌ Отмена", "btn_dl": "📥 Прямая загрузка",
        "choose_lang": "🌐 <b>Выберите язык:</b>", "lang_changed": "✅ <b>Язык изменён!</b>",
        "invalid": "🚨 Отправьте корректную ссылку на видео.", "delivered": "🎬 <b>Готово!</b>\n📥 @{admin}",
        "large": "📦 <b>Большое видео (> 50 MB)</b>\n\nНажмите кнопку для скачивания:",
        "failed": "❌ <b>Не удалось получить видео.</b>", "cancelled": "❌ <b>Отменено.</b>", "status": "Загрузка...",
    },
    "pt": {
        "welcome": "Bem-vindo ao <b>Nahid Video Downloader Pro</b>, <b>{name}</b>! 🚀\n\nEnvie um link do YouTube, Facebook, Instagram ou TikTok e eu baixo em HD.",
        "btn_lang": "🌐 Idioma", "btn_back": "🔙 Voltar", "btn_cancel": "❌ Cancelar", "btn_dl": "📥 Download direto",
        "choose_lang": "🌐 <b>Escolha seu idioma:</b>", "lang_changed": "✅ <b>Idioma alterado!</b>",
        "invalid": "🚨 Envie um link de vídeo válido.", "delivered": "🎬 <b>Pronto!</b>\n📥 @{admin}",
        "large": "📦 <b>Vídeo grande (> 50 MB)</b>\n\nToque no botão para baixar:",
        "failed": "❌ <b>Não foi possível obter o vídeo.</b>", "cancelled": "❌ <b>Cancelado.</b>", "status": "Baixando...",
    },
}

# ---------------------------------------------------------------------------
# 4. Persistent Database
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
    return L10N.get(get_lang(uid), {}).get(key) or EN.get(key, "")

# ---------------------------------------------------------------------------
# 5. Render 24/7 Keep-Alive HTTP Daemon
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
# 6. URL Sanitizers & Resolvers
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
# 7. Stream Downloader with Live Progress  -> returns "ok" | "big" | "fail"
# ---------------------------------------------------------------------------
def download_stream_with_progress(stream_url: str, save_path: str, job_id: str) -> str:
    try:
        with requests.get(stream_url, headers={"User-Agent": UA}, stream=True, timeout=40) as r:
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
    except Exception as e:
        logger.warning(f"Stream download error: {e}")
        return "fail"

# ---------------------------------------------------------------------------
# 8. Specialized Scrapers & API Gateways
# ---------------------------------------------------------------------------
def rapidapi_youtube_links(url: str) -> list:
    """YouTube Media Downloader (RapidAPI): returns direct video+audio URLs, best-fit first."""
    vid = extract_youtube_id(url)
    if not (RAPIDAPI_KEY and vid):
        return []
    try:
        r = requests.get(
            f"https://{RAPIDAPI_HOST}/v2/video/details",
            params={"videoId": vid},
            headers={"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST},
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning(f"RapidAPI YouTube status {r.status_code}: {r.text[:200]}")
            return []
        items = (r.json().get("videos") or {}).get("items") or []
        items = [i for i in items if i.get("url") and i.get("hasAudio", True)]
        def h(i):
            return int(i.get("height") or 0)
        small = sorted([i for i in items if h(i) <= 720], key=h, reverse=True)
        big = sorted([i for i in items if h(i) > 720], key=h)
        return [i["url"] for i in small + big]
    except Exception as e:
        logger.warning(f"RapidAPI YouTube error: {e}")
        return []

def generic_api_link(url: str):
    """Optional second RapidAPI (e.g. all-in-one downloader) for FB/IG/others."""
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
        headers = {
            "User-Agent": UA, "Referer": "https://fdown.net/", "Origin": "https://fdown.net",
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

def scrape_facebook_layer2(url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        html = requests.get(url, headers=headers, allow_redirects=True, timeout=10).text
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
# 9. Adaptive yt-dlp Engine
# ---------------------------------------------------------------------------
class DownloadCancelledException(Exception):
    pass

def download_with_ytdlp(url: str, output_path: str, job_id: str, is_yt: bool = False):
    def hook(d):
        if ACTIVE_CANCELS.get(job_id):
            raise DownloadCancelledException("Download cancelled by user.")
        if d["status"] == "downloading":
            JOB_PROGRESS[job_id] = {
                "downloaded": d.get("downloaded_bytes") or 0,
                "total": d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
                "speed": d.get("speed") or 0,
                "eta": d.get("eta") or 0,
            }

    if is_yt:
        fmt = (
            "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=720][filesize_approx<=45M]+bestaudio/"
            "best[height<=480][ext=mp4]/best[height<=480]/best"
        )
    else:
        fmt = "b[ext=mp4]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best"

    opts = {
        "format": fmt,
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "progress_hooks": [hook],
        "max_filesize": 400 * 1024 * 1024,
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
        "format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True, "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb"]}},
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("url") or (info.get("requested_formats") and info["requested_formats"][0].get("url"))

# ---------------------------------------------------------------------------
# 10. Sound Wave Equalizer (Live Fluctuating UI)
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
    return "█" * filled + "░" * (12 - filled)

def format_live_progress_text(uid: int, downloaded, total, speed, eta, quote: str, frame_idx: int) -> str:
    pct = min(99.9, (downloaded / total * 100)) if total > 0 else 0.0
    bar = make_progress_bar(pct)
    wave_bars = EQUALIZER_WAVES[frame_idx % len(EQUALIZER_WAVES)]
    dl_mb = downloaded / (1024 * 1024)
    tot_mb = total / (1024 * 1024) if total > 0 else 0.0
    spd_mb = speed / (1024 * 1024) if speed > 0 else 0.0
    eta_str = f"{int(eta)}s" if eta and eta > 0 else "..."
    size_str = f"{dl_mb:.1f} / {tot_mb:.1f} MB" if tot_mb > 0 else f"{dl_mb:.1f} MB"

    return (
        "🎛️ <b>NAHID MEDIA ENGINE — TURBO STREAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <b>Status:</b> <i>{tr(uid, 'status')}</i>\n"
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

def build_cancel_keyboard(uid: int, job_id: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_cancel"), callback_data=f"cancel_{job_id}")]])

async def send_banner_safe(chat_id, caption, reply_markup=None, context=None):
    try:
        return await context.bot.send_photo(
            chat_id=chat_id, photo=BOT_LOGO_URL, caption=caption,
            reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        return await context.bot.send_message(
            chat_id=chat_id, text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )

async def edit_any(msg, text, kb=None):
    """Edit a message whether it is a photo card or a plain text message."""
    try:
        if msg.photo:
            await msg.edit_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await msg.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# 11. Keyboards
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
    codes = list(LANG_NAMES)
    rows = [
        [InlineKeyboardButton(LANG_NAMES[c], callback_data=f"setlang_{c}") for c in codes[i:i + 2]]
        for i in range(0, len(codes), 2)
    ]
    return InlineKeyboardMarkup(rows)

def profile_text(user):
    return tr(user.id, "profile").format(
        name=f"{user.first_name} {user.last_name or ''}".strip(),
        user_id=user.id,
        lang=LANG_NAMES.get(get_lang(user.id), "English")
    )

def stats_text(uid):
    return tr(uid, "stats").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"])

# ---------------------------------------------------------------------------
# 12. Command Handlers
# ---------------------------------------------------------------------------
async def set_menu_commands(application):
    commands = [
        BotCommand("start", "🚀 Start / Refresh Main Dashboard"),
        BotCommand("lang", "🌐 Change Language"),
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
    first_time = str(user.id) not in DB["user_langs"]
    DB["unique_users"].add(user.id)
    save_db()
    context.user_data["feedback_mode"] = False

    if first_time:
        await update.message.reply_text(
            "🌐 <b>Choose your language / ভাষা বেছে নিন:</b>",
            reply_markup=build_lang_menu(), parse_mode=ParseMode.HTML
        )
        return

    try:
        await update.message.delete()
    except Exception:
        pass
    await send_banner_safe(
        update.effective_chat.id,
        tr(user.id, "welcome").format(name=user.first_name),
        build_main_menu(user.id), context
    )

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(
        tr(update.effective_user.id, "choose_lang"), reply_markup=build_lang_menu(), parse_mode=ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(stats_text(update.effective_user.id), parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = False
    await update.message.reply_text(profile_text(update.effective_user), parse_mode=ParseMode.HTML)

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = True
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_cancel"), callback_data="btn_home")]])
    await update.message.reply_text(tr(user.id, "feedback_prompt"), reply_markup=cancel_kb, parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["feedback_mode"] = False
    kb = [[InlineKeyboardButton(tr(user.id, "btn_admin"), url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(
        f"👨‍💻 <b>Support:</b> @{ADMIN_USERNAME}", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
    )

# ---------------------------------------------------------------------------
# 13. Interactive Button Callbacks
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
        DB["user_langs"][str(user.id)] = data.replace("setlang_", "")
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
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_cancel"), callback_data="btn_home")]])
        await edit_any(query.message, tr(user.id, "feedback_prompt"), cancel_kb)
    elif data == "btn_stats":
        await edit_any(query.message, stats_text(user.id), back_kb)
    elif data == "btn_profile":
        await edit_any(query.message, profile_text(user), back_kb)
    elif data == "btn_guide":
        await edit_any(query.message, tr(user.id, "guide"), back_kb)
    elif data == "btn_admin":
        if user.id == ADMIN_ID:
            text = (
                "🛠️ <b>Master Developer Control Panel</b>\n\n"
                f"• <b>Total Users:</b> <code>{len(DB['unique_users'])}</code>\n"
                f"• <b>Total Downloads:</b> <code>{DB['total_downloads']}</code>\n"
                f"• <b>RapidAPI (YouTube):</b> <code>{'Active' if RAPIDAPI_KEY else 'Disabled'}</code>\n"
                f"• <b>Generic API:</b> <code>{'Active' if GENERIC_API_HOST else 'Not set'}</code>\n"
                "• <b>Server Status:</b> <code>Optimal (24/7 Turbo)</code>"
            )
            await edit_any(query.message, text, back_kb)
        else:
            await query.answer("Access Restricted: Administrator Only!", show_alert=True)
    elif data == "btn_home":
        await edit_any(query.message, tr(user.id, "welcome").format(name=user.first_name), build_main_menu(user.id))

# ---------------------------------------------------------------------------
# 14. Message Handler & Live Dynamic Loop
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

    # Feedback Routing (Direct to Admin)
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
            tr(user.id, "feedback_ok"), reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML
        )
        return

    urls = re.findall(r"(https?://\S+)", raw_text)

    # Non-link: delete + 5-second warning
    if not urls:
        try:
            await message.delete()
        except Exception:
            pass
        warn_msg = await context.bot.send_message(
            chat_id=chat_id, text=tr(user.id, "invalid"), parse_mode=ParseMode.HTML
        )

        async def delete_warning_later(msg_id: int):
            await asyncio.sleep(5)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass

        asyncio.create_task(delete_warning_later(warn_msg.message_id))
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
    proc_msg = await send_banner_safe(
        chat_id=chat_id, caption=initial_text,
        reply_markup=build_cancel_keyboard(user.id, job_id), context=context
    )

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
            card = format_live_progress_text(
                user.id, p.get("downloaded", 0), p.get("total", 0),
                p.get("speed", 0), p.get("eta", 0), random.choice(FUNNY_QUOTES), frame
            )
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
            """Download a direct stream link. Remembers the link if it is too big for chat."""
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

        # ---- YOUTUBE: RapidAPI first (cloud IPs get blocked), then yt-dlp ----
        if yt:
            if RAPIDAPI_KEY:
                links = await loop.run_in_executor(None, rapidapi_youtube_links, cleaned_url)
                for lk in links[:4]:
                    if await grab(lk):
                        download_success = True
                        break
                    if state["direct"]:
                        break
            if not download_success and not state["direct"]:
                download_success = await try_ytdlp(True)

        # ---- FACEBOOK: FDown -> mobile regex -> generic API -> yt-dlp ----
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

        # ---- TIKTOK / INSTAGRAM / TWITTER / OTHERS ----
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

        # Deliver in chat if <= 48 MB
        if download_success and files:
            video_path = files[0]
            if os.path.getsize(video_path) <= MAX_UPLOAD_LIMIT:
                DB["total_downloads"] += 1
                save_db()
                caption = tr(user.id, "delivered").format(admin=ADMIN_USERNAME)
                try:
                    with open(video_path, "rb") as vf:
                        await context.bot.send_video(
                            chat_id=chat_id, video=vf, caption=caption, supports_streaming=True,
                            read_timeout=300, write_timeout=300, parse_mode=ParseMode.HTML
                        )
                except Exception:
                    with open(video_path, "rb") as vf:
                        await context.bot.send_document(
                            chat_id=chat_id, document=vf, caption=caption,
                            read_timeout=300, write_timeout=300, parse_mode=ParseMode.HTML
                        )
                try:
                    await proc_msg.delete()
                except Exception:
                    pass
                return

        # Large file: direct link
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

        # Failed: message + web portal button
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
# 15. Main Bootstrap Engine
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.critical("BOT_TOKEN is not configured!")
        return

    threading.Thread(target=run_http_server, daemon=True).start()

    custom_request = HTTPXRequest(
        connect_timeout=60.0, read_timeout=300.0, write_timeout=300.0, pool_timeout=60.0
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

    logger.info("Nahid Video Downloader Pro (Ultimate Edition) is officially LIVE!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()