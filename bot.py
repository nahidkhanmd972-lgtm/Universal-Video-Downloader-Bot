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

# Credentials (Environment Variables থেকে রিড করবে)
TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "youtube-media-downloader.p.rapidapi.com")
GENERIC_API_HOST = os.getenv("GENERIC_API_HOST", "")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8815124111"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "NahidDevOfficial")

# কাস্টম অ্যানিমেটেড থ্রিডি লোগো ইউআরএল
BOT_LOGO_URL = os.getenv(
    "BOT_LOGO_URL",
    "https://user55725.cn.imgto.link/public/20261113/3b13a0dfe6eaa21ad1c15b4f-1000483594.avif"
)

MAX_UPLOAD_LIMIT = 48 * 1024 * 1024  # 48 MB (Telegram limit safe margin)
STATS_FILE = "stats.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

ACTIVE_CANCELS = {}
JOB_PROGRESS = {}

# ---------------------------------------------------------------------------
# 2. Multi-Language Dictionary (Global Support: English, Malay, Bengali, Indonesian, Arabic, Spanish)
# ---------------------------------------------------------------------------
LANG_NAMES = {
    "en": "🇬🇧 English",
    "ms": "🇲🇾 Melayu",
    "bn": "🇧🇩 বাংলা",
    "id": "🇮🇩 Indonesia",
    "ar": "🇸🇦 العربية",
    "es": "🇪🇸 Español"
}

L10N = {
    "en": {
        "welcome": "👋 Welcome to <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n⚡ Drop any public video link from YouTube, Facebook, Instagram, or TikTok to download instantly in HD!\n\n👇 <i>Use the dashboard below or send any link:</i>",
        "btn_profile": "👤 My Profile", "btn_stats": "📊 Live Statistics", "btn_guide": "ℹ️ User Guide",
        "btn_lang": "🌐 Language", "btn_feedback": "✍️ Feedback", "btn_admin": "💬 Admin",
        "btn_back": "🔙 Back", "btn_cancel": "❌ Cancel", "btn_dl": "📥 Direct High-Speed Download",
        "stats": "📊 <b>Global Stats</b>\n\n👥 Users: <code>{users:,}</code>\n📥 Processed: <code>{downloads:,}</code>\n🟢 Status: <code>Online 24/7</code>",
        "guide": "📌 <b>Quick Guide:</b>\n1. Send any video link.\n2. Under 50MB comes directly to chat.\n3. Large files generate a fast direct download link.",
        "choose_lang": "🌐 <b>Select your preferred language:</b>",
        "lang_changed": "✅ <b>Language successfully updated!</b>",
        "feedback_prompt": "✍️ <b>Send Feedback</b>\nType your message below for the admin:",
        "feedback_ok": "✅ <b>Thank you!</b> Message sent to admin.",
        "invalid": "🚨 <b>Please send a valid YouTube, Facebook, TikTok, or Instagram link! 😂</b>",
        "delivered": "🎬 <b>Video Processed Successfully!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>Large Video File Detected! (> 50MB)</b>\nClick below to download directly:",
        "failed": "❌ <b>Extraction Failed!</b>\nThe video may be private or restricted.",
        "cancelled": "❌ <b>Download Cancelled!</b>", "status": "Downloading High-Speed Media...",
        "quotes": [
            "☕ Grab a cup of coffee! Server hamsters running on nitro...",
            "🐢 Supersonic download packets arriving at light speed!",
            "🚀 Even Elon Musk's Falcon 9 is jealous of our velocity!",
            "🥷 Sneaking past platform security like a cyber ninja...",
            "🧙‍♂️ Chanting digital sorcery: Pixels assemble right now!",
            "🍿 Getting popcorn ready, your HD video is almost cooked!",
            "🏎️ Burning digital rubber on the high-speed data highway!"
        ]
    },
    "ms": {
        "welcome": "👋 Selamat datang ke <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n⚡ Hantar pautan video awam dari YouTube, Facebook, Instagram, atau TikTok untuk dimuat turun dalam HD!\n\n👇 <i>Gunakan menu di bawah atau hantar pautan:</i>",
        "btn_profile": "👤 Profil Saya", "btn_stats": "📊 Statistik Langsung", "btn_guide": "ℹ️ Panduan Pengguna",
        "btn_lang": "🌐 Bahasa", "btn_feedback": "✍️ Maklum Balas", "btn_admin": "💬 Admin",
        "btn_back": "🔙 Kembali", "btn_cancel": "❌ Batal", "btn_dl": "📥 Muat Turun Pantas",
        "stats": "📊 <b>Statistik Global</b>\n\n👥 Pengguna: <code>{users:,}</code>\n📥 Diproses: <code>{downloads:,}</code>\n🟢 Status: <code>Online 24/7</code>",
        "guide": "📌 <b>Panduan Pantas:</b>\n1. Hantar sebarang pautan video.\n2. Bawah 50MB dihantar terus ke chat.\n3. Fail besar menjana pautan muat turun pantas.",
        "choose_lang": "🌐 <b>Pilih bahasa pilihan anda:</b>",
        "lang_changed": "✅ <b>Bahasa berjaya dikemas kini!</b>",
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas</b>\nTaip mesej anda di bawah untuk admin:",
        "feedback_ok": "✅ <b>Terima kasih!</b> Mesej dihantar kepada admin.",
        "invalid": "🚨 <b>Sila hantar pautan YouTube, Facebook, TikTok, atau Instagram yang sah! 😂</b>",
        "delivered": "🎬 <b>Video Berjaya Diproses!</b>\n📥 Dikuasakan oleh @{admin}",
        "large": "📦 <b>Fail Video Besar Dikesان! (> 50MB)</b>\nKlik di bawah untuk muat turun terus:",
        "failed": "❌ <b>Gagal Mengekstrak!</b>\nVideo mungkin peribadi atau disekat.",
        "cancelled": "❌ <b>Muat Turun Dibatalkan!</b>", "status": "Sedang memuat turun media...",
        "quotes": [
            "☕ Sambil minum kopi, pelayan kami sedang memproses video...",
            "🐢 Bersabar, paket muat turun sedang meluncur laju!",
            "🚀 Kelajuan pelayan kami memang tiada tandingan!",
            "🥷 Mengelak kawalan keselamatan platform seperti ninja siber...",
            "🧙‍♂️ Sihir digital sedang dijalankan: piksel sedang dipasang!",
            "🍿 Sediakan bertih jagung, video HD anda hampir siap!",
            "🏎️ Meluncur laju di lebuh raya data digital!"
        ]
    },
    "bn": {
        "welcome": "স্বাগতম <b>Nahid Video Downloader Pro</b>-তে, <b>{name}</b>! 🚀\n\n⚡ YouTube, Facebook, Instagram বা TikTok-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠান, আমি এইচডি কোয়ালিটিতে নামিয়ে দেব।\n\n👇 নিচের মেনু ব্যবহার করুন বা লিংক পেস্ট করুন।",
        "btn_profile": "👤 আমার প্রোফাইল", "btn_stats": "📊 লাইভ পরিসংখ্যান", "btn_guide": "ℹ️ ব্যবহারবিধি",
        "btn_lang": "🌐 ভাষা", "btn_feedback": "✍️ মতামত", "btn_admin": "💬 অ্যাডমিন",
        "btn_back": "🔙 ফিরে যান", "btn_cancel": "❌ বাতিল", "btn_dl": "📥 সরাসরি ডাউনলোড করুন",
        "stats": "📊 <b>লাইভ পরিসংখ্যান</b>\n\n👥 ব্যবহারকারী: <code>{users:,}</code>\n📥 ডাউনলোড: <code>{downloads:,}</code>\n🟢 সার্ভার: <code>Online 24/7</code>",
        "guide": "📌 <b>ব্যবহারবিধি</b>\n১. যেকোনো ভিডিওর লিংক দিন।\n২. ৫০MB-এর কম হলে চ্যাটেই পাবেন।\n৩. বড় হলে ডাইরেক্ট ডাউনলোড বাটন আসবে।",
        "choose_lang": "🌐 <b>আপনার পছন্দের ভাষা সিলেক্ট করুন:</b>",
        "lang_changed": "✅ <b>ভাষা সফলভাবে পরিবর্তন হয়েছে!</b>",
        "feedback_prompt": "✍️ <b>মতামত লিখুন</b>\nআপনার মেসেজ সরাসরি অ্যাডমিনের কাছে যাবে:",
        "feedback_ok": "✅ <b>ধন্যবাদ!</b> অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "invalid": "🚨 <b>আরে ভাই, সঠিক ফেসবুক, ইনস্টাগ্রাম, ইউটিউব বা টিকটকের লিংক পাঠান! 😂</b>",
        "delivered": "🎬 <b>ভিডিও সফলভাবে হাজির!</b>\n📥 Powered by @{admin}",
        "large": "📦 <b>ভিডিও ফাইলের সাইজ বড়! (> ৫০MB)</b>\nনিচের বাটনে ক্লিক করে সরাসরি ডাউনলোড করে নিন:",
        "failed": "❌ <b>ভিডিও আনা যায়নি!</b>\nভিডিওটি প্রাইভেট বা রেস্ট্রিক্টেড হতে পারে।",
        "cancelled": "❌ <b>ডাউনলোড বাতিল করা হয়েছে!</b>", "status": "ডাউনলোড হচ্ছে...",
        "quotes": [
            "☕ এক কাপ চা খান! সার্ভারের হ্যামস্টারগুলো রকেটের গতিতে ছুটছে...",
            "🐢 একটু সবুর করুন, আলোর গতিতে ভিডিও নিয়ে আসছি!",
            "🚀 ইলন মাস্কের রকেটও আমাদের গতির কাছে ফেল!",
            "🥷 সিকিউরিটি গার্ডদের চোখ ফাঁকি দিয়ে ভিডিও আনা হচ্ছে...",
            "🧙‍♂️ জাদুমন্ত্র পড়া হচ্ছে: পিক্সেলগুলো দ্রুত এক হও!",
            "🍿 পপকর্ন নিয়ে বসুন, আপনার ভিডিও প্রায় তৈরি!",
            "🏎️ হাই-স্পিড ডেটা হাইওয়েতে ডিজিটাল ড্রাইভ চলছে..."
        ]
    },
    "id": {
        "welcome": "👋 Selamat datang di <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n⚡ Kirim tautan video publik dari YouTube, Facebook, Instagram, atau TikTok untuk diunduh dalam HD!\n\n👇 <i>Gunakan menu di bawah atau kirim tautan:</i>",
        "btn_profile": "👤 Profil Saya", "btn_stats": "📊 Statistik Langsung", "btn_guide": "ℹ️ Panduan",
        "btn_lang": "🌐 Bahasa", "btn_feedback": "✍️ Umpan Balik", "btn_admin": "💬 Admin",
        "btn_back": "🔙 Kembali", "btn_cancel": "❌ Batal", "btn_dl": "📥 Unduh Langsung",
        "stats": "📊 <b>Statistik Global</b>\n\n👥 Pengguna: <code>{users:,}</code>\n📥 Diproses: <code>{downloads:,}</code>\n🟢 Status: <code>Online 24/7</code>",
        "guide": "📌 <b>Panduan:</b> Kirim tautan video untuk diunduh secara instan.",
        "choose_lang": "🌐 <b>Pilih bahasa Anda:</b>",
        "lang_changed": "✅ <b>Bahasa berhasil diperbarui!</b>",
        "feedback_prompt": "✍️ <b>Kirim Umpan Balik:</b>",
        "feedback_ok": "✅ <b>Terima kasih!</b> Pesan terkirim ke admin.",
        "invalid": "🚨 <b>Kirim tautan video YouTube, Facebook, TikTok, atau Instagram yang valid! 😂</b>",
        "delivered": "🎬 <b>Video Berhasil Diproses!</b>\n📥 Didukung oleh @{admin}",
        "large": "📦 <b>File Video Besar! (> 50MB)</b>\nKlik di bawah untuk mengunduh:",
        "failed": "❌ <b>Gagal Mengekstrak!</b>\nVideo mungkin privat atau dibatasi.",
        "cancelled": "❌ <b>Unduhan Dibatalkan!</b>", "status": "Mengunduh media...",
        "quotes": [
            "☕ Sambil ngopi, server kami memproses video Anda...",
            "🐢 Paket unduhan meluncur dengan kecepatan cahaya!",
            "🚀 Kecepatan transfer data maksimal!",
            "🥷 Menyusุป keamanan platform seperti ninja siber...",
            "🧙‍♂️ Mantra digital: Piksel berkumpul sekarang!",
            "🍿 Siapkan popcorn, video Anda hampir siap!",
            "🏎️ Melaju kencang di jalan tol data!"
        ]
    },
    "ar": {
        "welcome": "👋 أهلاً بك في <b>Nahid Video Downloader Pro</b> يا <b>{name}</b>!\n\n⚡ أرسل رابط أي فيديو عام من يوتيوب، فيسبوك، انستغرام، أو تيك توك للتحميل فوراً بجودة HD!\n\n👇 <i>استخدم القائمة أدناه أو أرسل الرابط:</i>",
        "btn_profile": "👤 ملفي الشخصي", "btn_stats": "📊 الإحصائيات", "btn_guide": "ℹ️ الدليل",
        "btn_lang": "🌐 اللغة", "btn_feedback": "✍️ ملاحظات", "btn_admin": "💬 المشرف",
        "btn_back": "🔙 رجوع", "btn_cancel": "❌ إلغاء", "btn_dl": "📥 تحميل مباشر سريع",
        "stats": "📊 <b>الإحصائيات العامة</b>\n\n👥 المستخدمون: <code>{users:,}</code>\n📥 المعالجة: <code>{downloads:,}</code>\n🟢 الحالة: <code>متصل 24/7</code>",
        "guide": "📌 <b>الدليل السريع:</b> أرسل أي رابط فيديو لتحميله فوراً.",
        "choose_lang": "🌐 <b>اختر لغتك المفضلة:</b>",
        "lang_changed": "✅ <b>تم تحديث اللغة بنجاح!</b>",
        "feedback_prompt": "✍️ <b>إرسال ملاحظاتك:</b>",
        "feedback_ok": "✅ <b>شكراً لك!</b> تم إرسال رسالتك.",
        "invalid": "🚨 <b>الرجاء إرسال رابط صحيح من يوتيوب، فيسبوك، تيك توك، أو انستغرام! 😂</b>",
        "delivered": "🎬 <b>تم معالجة الفيديو بنجاح!</b>\n📥 مدعوم بواسطة @{admin}",
        "large": "📦 <b>ملف فيديو كبير! (> 50MB)</b>\nانقر أدناه للتحميل المباشر:",
        "failed": "❌ <b>فشل الاستخراج!</b>\nقد يكون الفيديو خاصاً أو محظوراً.",
        "cancelled": "❌ <b>تم إلغاء التحميل!</b>", "status": "جارٍ تحميل الوسائط...",
        "quotes": [
            "☕ استمتع بفنجان قهوة بينما نعمل على تجهيز الفيديو...",
            "🐢 حزم بيانات بسرعة فائقة في طريقها إليك!",
            "🚀 سرعة نقل خيالية تتجاوز التوقعات!",
            "🥷 التسلل عبر جدران الحماية مثل النينجا...",
            "🧙‍♂️ سحر البكسلات قيد التنفيذ الآن!",
            "🍿 جهز الفشار، فيديو عالي الدقة في طريقه للظهور!",
            "🏎️ انطلاق بسرعة البرق في طريق البيانات السريع!"
        ]
    },
    "es": {
        "welcome": "👋 ¡Bienvenido a <b>Nahid Video Downloader Pro</b>, <b>{name}</b>!\n\n⚡ ¡Envía cualquier enlace de video público de YouTube, Facebook, Instagram o TikTok para descargarlo en HD!\n\n👇 <i>Usa el menú o envía un enlace:</i>",
        "btn_profile": "👤 Mi Perfil", "btn_stats": "📊 Estadísticas", "btn_guide": "ℹ️ Guía",
        "btn_lang": "🌐 Idioma", "btn_feedback": "✍️ Comentarios", "btn_admin": "💬 Admin",
        "btn_back": "🔙 Volver", "btn_cancel": "❌ Cancelar", "btn_dl": "📥 Descarga Directa",
        "stats": "📊 <b>Estadísticas Globales</b>\n\n👥 Usuarios: <code>{users:,}</code>\n📥 Procesados: <code>{downloads:,}</code>\n🟢 Estado: <code>Online 24/7</code>",
        "guide": "📌 <b>Guía rápida:</b> Envía un enlace de video para descargar.",
        "choose_lang": "🌐 <b>Selecciona tu idioma:</b>",
        "lang_changed": "✅ <b>¡Idioma actualizado con éxito!</b>",
        "feedback_prompt": "✍️ <b>Enviar comentarios:</b>",
        "feedback_ok": "✅ <b>¡Gracias!</b> Mensaje enviado.",
        "invalid": "🚨 <b>¡Envía un enlace válido de YouTube, Facebook, TikTok o Instagram! 😂</b>",
        "delivered": "🎬 <b>¡Video procesado con éxito!</b>\n📥 Con la potencia de @{admin}",
        "large": "📦 <b>¡Archivo grande detectado! (> 50MB)</b>\nHaz clic abajo para descargar directamente:",
        "failed": "❌ <b>¡Falló la extracción!</b>\nEl video puede ser privado o restringido.",
        "cancelled": "❌ <b>¡Descarga cancelada!</b>", "status": "Descargando multimedia...",
        "quotes": [
            "☕ ¡Tómate un café mientras procesamos tu video!",
            "🐢 ¡Paquetes supersónicos llegando a velocidad de la luz!",
            "🚀 ¡Velocidad de transferencia increíble!",
            "🥷 ¡Infiltrándonos en el sistema como un ninja cibernético!",
            "🧙‍♂️ Hechizo digital: ¡los píxeles se ensamblan!",
            "🍿 ¡Prepara las palomitas, tu video casi está listo!",
            "🏎️ ¡Acelerando en la autopista de datos!"
        ]
    }
}

# ---------------------------------------------------------------------------
# 3. Persistent Database Handler
# ---------------------------------------------------------------------------
STATS_FILE = "stats.json"

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
    lang = get_lang(uid)
    return L10N.get(lang, L10N["en"]).get(key) or L10N["en"].get(key, "")

# ---------------------------------------------------------------------------
# 4. Render / Bot-Hosting 24/7 Keep-Alive HTTP Daemon
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
# 5. URL Helpers & Downloader Engines
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
# 6. UI & Keyboards Builder
# ---------------------------------------------------------------------------
def format_live_progress_text(uid: int, downloaded, total, speed, eta, quote: str) -> str:
    pct = min(99.9, (downloaded / total * 100)) if total > 0 else 0.0
    filled = max(0, min(12, int(pct // 8.33)))
    bar = "█" * filled + "░" * (12 - filled)
    dl_mb = downloaded / (1024 * 1024)
    tot_mb = total / (1024 * 1024) if total > 0 else 0.0
    spd_mb = speed / (1024 * 1024) if speed > 0 else 0.0
    
    return (
        "🎛️ <b>NAHID MEDIA ENGINE — TURBO STREAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <b>Status:</b> <i>{tr(uid, 'status')}</i>\n"
        f"📊 <b>Buffer:</b> <code>[{bar}] {pct:.1f}%</code>\n"
        f"💾 <b>Size:</b> <code>{dl_mb:.1f} / {tot_mb:.1f} MB</code>\n"
        f"🚀 <b>Speed:</b> <code>{spd_mb:.1f} MB/s</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>\"{quote}\"</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
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
    try:
        if msg.photo:
            await msg.edit_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await msg.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return True
    except Exception:
        return False

def build_main_menu(user_id: int):
    return InlineKeyboardMarkup([
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
    ])

def build_lang_menu():
    codes = list(LANG_NAMES.keys())
    rows = [
        [InlineKeyboardButton(LANG_NAMES[c], callback_data=f"setlang_{c}") for c in codes[i:i + 2]]
        for i in range(0, len(codes), 2)
    ]
    return InlineKeyboardMarkup(rows)

# ---------------------------------------------------------------------------
# 7. Command Handlers
# ---------------------------------------------------------------------------
async def set_menu_commands(application):
    commands = [
        BotCommand("start", "🚀 Start / Dashboard"),
        BotCommand("lang", "🌐 Change Language"),
        BotCommand("stats", "📊 Bot Statistics"),
        BotCommand("profile", "👤 User Profile"),
        BotCommand("feedback", "✍️ Send Feedback"),
        BotCommand("admin", "💬 Admin Support")
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
            "🌐 <b>Please select your language / Sila pilih bahasa / ভাষা নির্বাচন করুন:</b>",
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
    await update.message.reply_text(tr(update.effective_user.id, "choose_lang"), reply_markup=build_lang_menu(), parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(tr(uid, "stats").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"]), parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"👤 <b>User Profile</b>\n\n• <b>Name:</b> {user.first_name}\n• <b>ID:</b> <code>{user.id}</code>\n• <b>Language:</b> {LANG_NAMES.get(get_lang(user.id), 'English')}"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["feedback_mode"] = True
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(update.effective_user.id, "btn_cancel"), callback_data="btn_home")]])
    await update.message.reply_text(tr(update.effective_user.id, "feedback_prompt"), reply_markup=cancel_kb, parse_mode=ParseMode.HTML)

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
        save_db()
        text = f"{tr(user.id, 'lang_changed')}\n\n{tr(user.id, 'welcome').format(name=user.first_name)}"
        await edit_any(query.message, text, build_main_menu(user.id))
        return

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_back"), callback_data="btn_home")]])
    if data == "btn_lang":
        await edit_any(query.message, tr(user.id, "choose_lang"), build_lang_menu())
    elif data == "btn_feedback":
        context.user_data["feedback_mode"] = True
        await edit_any(query.message, tr(user.id, "feedback_prompt"), back_kb)
    elif data == "btn_stats":
        await edit_any(query.message, tr(user.id, "stats").format(users=len(DB["unique_users"]), downloads=DB["total_downloads"]), back_kb)
    elif data == "btn_guide":
        await edit_any(query.message, tr(user.id, "guide"), back_kb)
    elif data == "btn_home":
        await edit_any(query.message, tr(user.id, "welcome").format(name=user.first_name), build_main_menu(user.id))

# ---------------------------------------------------------------------------
# 8. Core Message Handler & Downloader Pipeline
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

    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False
        admin_text = f"📬 <b>Feedback from {user.first_name}</b> (<code>{user.id}</code>):\n\n{raw_text}"
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
        warn_msg = await context.bot.send_message(chat_id=chat_id, text=tr(user.id, "invalid"), parse_mode=ParseMode.HTML)
        async def del_warn():
            await asyncio.sleep(5)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=warn_msg.message_id)
            except Exception:
                pass
        asyncio.create_task(del_warn())
        return

    try:
        await message.delete()
    except Exception:
        pass

    target_url = urls[0]
    job_id = uuid.uuid4().hex[:8]
    ACTIVE_CANCELS[job_id] = False
    JOB_PROGRESS[job_id] = {"downloaded": 0, "total": 0, "speed": 0, "eta": 0}

    quotes_list = L10N.get(get_lang(user.id), L10N["en"]).get("quotes", L10N["en"]["quotes"])

    initial_text = format_live_progress_text(user.id, 0, 0, 0, 0, random.choice(quotes_list))
    proc_msg = await send_banner_safe(chat_id=chat_id, caption=initial_text, reply_markup=build_cancel_keyboard(user.id, job_id), context=context)

    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")
    loop_active = True

    async def progress_loop():
        while loop_active:
            await asyncio.sleep(2)
            if not loop_active or ACTIVE_CANCELS.get(job_id):
                break
            p = JOB_PROGRESS.get(job_id, {})
            q_list = L10N.get(get_lang(user.id), L10N["en"]).get("quotes", L10N["en"]["quotes"])
            card = format_live_progress_text(user.id, p.get("downloaded", 0), p.get("total", 0), p.get("speed", 0), p.get("eta", 0), random.choice(q_list))
            await edit_any(proc_msg, card, build_cancel_keyboard(user.id, job_id))

    prog_task = asyncio.create_task(progress_loop())
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

        async def try_ytdlp() -> bool:
            if ACTIVE_CANCELS.get(job_id):
                return False
            try:
                await loop.run_in_executor(None, download_with_ytdlp, cleaned_url, output_template, job_id)
                return True
            except Exception:
                return False

        # Platform Routing & Fallbacks
        if yt:
            if RAPIDAPI_KEY:
                for lk in rapidapi_youtube_links(cleaned_url)[:3]:
                    if await grab(lk):
                        download_success = True
                        break
            if not download_success and not state["direct"]:
                download_success = await try_ytdlp()
        elif "tiktok.com" in cleaned_url:
            tk = tikwm_link(cleaned_url)
            download_success = await grab(tk)
            if not download_success:
                download_success = await try_ytdlp()
        else:
            download_success = await try_ytdlp()
            if not download_success:
                g = generic_api_link(cleaned_url)
                download_success = await grab(g)

        loop_active = False
        prog_task.cancel()

        if ACTIVE_CANCELS.get(job_id):
            return

        files = [f for f in glob.glob(f"{temp_dir}/*") if os.path.getsize(f) > 1000]

        # Deliver if under size limit (48MB)
        if download_success and files:
            video_path = files[0]
            if os.path.getsize(video_path) <= MAX_UPLOAD_LIMIT:
                DB["total_downloads"] += 1
                save_db()
                caption = tr(user.id, "delivered").format(admin=ADMIN_USERNAME)
                try:
                    with open(video_path, "rb") as vf:
                        await context.bot.send_video(chat_id=chat_id, video=vf, caption=caption, supports_streaming=True, parse_mode=ParseMode.HTML)
                except Exception:
                    with open(video_path, "rb") as vf:
                        await context.bot.send_document(chat_id=chat_id, document=vf, caption=caption, parse_mode=ParseMode.HTML)
                try:
                    await proc_msg.delete()
                except Exception:
                    pass
                return

        # Large File / Direct Link Fallback
        direct = state["direct"] or (await loop.run_in_executor(None, fetch_direct_stream_url, cleaned_url))
        if direct:
            DB["total_downloads"] += 1
            save_db()
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id, "btn_dl"), url=direct)]])
            await edit_any(proc_msg, tr(user.id, "large"), kb)
            return

        # Failed State
        await edit_any(proc_msg, tr(user.id, "failed"))

    except Exception as exc:
        logger.error(f"Error: {exc}")
        loop_active = False
        prog_task.cancel()
        await edit_any(proc_msg, tr(user.id, "failed"))
    finally:
        loop_active = False
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# 9. Main Bootstrap Engine
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.critical("BOT_TOKEN is missing!")
        return

    # Start 24/7 Keep-Alive HTTP Daemon for Render / Bot-Hosting
    threading.Thread(target=run_http_server, daemon=True).start()

    custom_request = HTTPXRequest(connect_timeout=60.0, read_timeout=300.0, write_timeout=300.0)
    application = ApplicationBuilder().token(TOKEN).request(custom_request).post_init(set_menu_commands).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming_message))

    logger.info("Nahid Video Downloader Pro is 100% LIVE & Running 24/7 with Multi-Language Support!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()