
    #!/usr/bin/env python3
"""
UniversalDL Telegram Bot
Supported Environments: Render, Railway, Heroku, Koyeb, Docker, Linux VPS, Android Termux
Python 3.11+ | python-telegram-bot v20+ | yt-dlp | FFmpeg | SQLite | QRCode
"""

import asyncio
import html
import logging
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import qrcode
import requests
import yt_dlp
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# 1. Hosting & Termux Environment Detection + FFmpeg Setup
# ---------------------------------------------------------------------------
def detect_environment() -> str:
    prefix = os.getenv("PREFIX", "")
    if os.getenv("TERMUX_VERSION") or "com.termux" in prefix:
        return "Termux (Android)"
    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
        return "Render Cloud"
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return "Railway Cloud"
    if os.getenv("KOYEB_APP_NAME"):
        return "Koyeb Cloud"
    if os.getenv("FLY_APP_NAME"):
        return "Fly.io Cloud"
    if os.getenv("DYNO"):
        return "Heroku"
    if Path("/.dockerenv").exists():
        return "Docker Container"
    return f"Linux / {platform.system()}"


HOST_ENV = detect_environment()
IS_TERMUX = HOST_ENV.startswith("Termux")


def setup_ffmpeg_paths() -> None:
    """Prefer native FFmpeg (Termux/Linux VPS); fallback to static-ffmpeg (Render/Cloud)."""
    if shutil.which("ffmpeg"):
        return
    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
    except Exception:
        pass


setup_ffmpeg_paths()

BASE_DIR = Path(__file__).resolve().parent
TEMP_ROOT = Path(tempfile.gettempdir())

# ---------------------------------------------------------------------------
# 2. Logging & Environment Variables
# ---------------------------------------------------------------------------
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "bot.log")).strip()
log_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger("UniversalDLBot")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "").strip()
RAPIDAPI_HOST: str = os.getenv("RAPIDAPI_HOST", "").strip()
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "").strip().lstrip("@")
DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "universal_dl.db")).strip()
COOKIES_FILE: str = os.getenv("COOKIES_FILE", str(BASE_DIR / "cookies.txt")).strip()

try:
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0").strip() or "0")
except ValueError:
    ADMIN_ID = 0

MAX_TG_UPLOAD_BYTES = 49 * 1024 * 1024
MAX_TG_DOWNLOAD_BYTES = 20 * 1024 * 1024
MAX_TEXT_PASTE_BYTES = 256 * 1024
MAX_DISK_DOWNLOAD_BYTES = 250 * 1024 * 1024

EXECUTOR = ThreadPoolExecutor(max_workers=12 if IS_TERMUX else 16)

STATE_LOCK = threading.Lock()
ACTIVE_CANCELS: dict[str, bool] = {}
JOB_PROGRESS: dict[str, dict[str, Any]] = {}


class DownloadCancelledError(Exception):
    """Raised when a user cancels an active download."""


# ---------------------------------------------------------------------------
# 3. Multi-Language Dictionary (English, Bengali, Malay)
# ---------------------------------------------------------------------------
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": (
            "👋 <b>Welcome to UniversalDL Pro, {name}!</b>\n\n"
            "🚀 All-in-one media toolkit: Video Downloader, QR Code Generator, and Video-to-MP3 Converter.\n\n"
            "👇 <b>Choose a tool from the menu below:</b>"
        ),
        "btn_video": "🎬 Video Downloader",
        "btn_qr": "📱 QR Code Generator",
        "btn_v2a": "🎵 Video to Audio",
        "btn_profile": "👤 Profile",
        "btn_stats": "📊 Statistics",
        "btn_help": "ℹ️ Help / Guide",
        "btn_lang": "🌐 Language",
        "btn_admin": "🛡️ Admin / Support",
        "btn_feedback": "✍️ Send Feedback",
        "btn_contact_admin": "💬 Contact Admin",
        "btn_back": "🔙 Back to Menu",
        "btn_cancel": "❌ Cancel Download",
        "btn_direct_dl": "📥 Direct Download Link",
        "video_prompt": (
            "🎬 <b>Video Downloader</b>\n\n"
            "Send any public video link from:\n"
            "• YouTube (Videos &amp; Shorts)\n"
            "• Facebook (Watch &amp; Reels)\n"
            "• Instagram (Reels &amp; Posts)\n"
            "• TikTok\n\n"
            "<i>Quality: Up to 1080p MP4 with audio.</i>"
        ),
        "qr_prompt": (
            "📱 <b>QR Code Generator</b>\n\n"
            "Send either:\n"
            "1️⃣ <b>Text</b> (uploaded to <code>paste.rs</code> to create a shareable link)\n"
            "2️⃣ <b>Photo</b> (uploaded to <code>catbox.moe</code> to create an image link)\n\n"
            "⚠️ <b>Privacy Notice:</b> Uploaded text and images are hosted on public third-party servers and may be publicly accessible to anyone with the URL."
        ),
        "v2a_prompt": (
            "🎵 <b>Video to Audio (MP3)</b>\n\n"
            "Send a Telegram video file (up to <b>20 MB</b>) and I will extract the audio and convert it to MP3."
        ),
        "profile_text": (
            "👤 <b>Your Profile</b>\n\n"
            "• <b>Name:</b> {name}\n"
            "• <b>User ID:</b> <code>{user_id}</code>\n"
            "• <b>Username:</b> {username}\n"
            "• <b>Language:</b> {lang_label}\n"
            "• <b>Your Downloads:</b> <code>{downloads}</code>\n"
            "• <b>QR Codes Created:</b> <code>{qr_count}</code>\n"
            "• <b>MP3 Conversions:</b> <code>{v2a_count}</code>"
        ),
        "stats_text": (
            "📊 <b>Global Bot Statistics</b>\n\n"
            "• <b>Total Users:</b> <code>{users:,}</code>\n"
            "• <b>Total Video Downloads:</b> <code>{downloads:,}</code>\n"
            "• <b>Total QR Codes:</b> <code>{qr_count:,}</code>\n"
            "• <b>Total MP3 Conversions:</b> <code>{v2a_count:,}</code>"
        ),
        "help_text": (
            "ℹ️ <b>Help &amp; User Guide</b>\n\n"
            "1. <b>Video Downloader:</b> Tap <i>Video Downloader</i> (or paste a link directly) to download up to 1080p MP4. Files over 49 MB automatically try a compact size or provide a direct link.\n"
            "2. <b>QR Code Generator:</b> Tap <i>QR Code Generator</i>, then send text or a photo. Text is hosted on paste.rs and photos on catbox.moe.\n"
            "3. <b>Video to Audio:</b> Tap <i>Video to Audio</i> and send a Telegram video (&lt;= 20 MB) to receive an MP3 file.\n"
            "4. <b>Language:</b> Switch between English, Bengali, and Malay anytime."
        ),
        "lang_prompt": "🌐 <b>Select your preferred language:</b>",
        "lang_updated": "✅ Language updated to <b>English</b>.",
        "support_text": (
            "🛡️ <b>Support &amp; Feedback</b>\n\n"
            "If a video link fails, please make sure the post is public and try again.\n"
            "You can send feedback directly to the admin using the button below."
        ),
        "feedback_prompt": "✍️ <b>Send Feedback</b>\nType your message below and it will be forwarded to the admin:",
        "feedback_sent": "✅ <b>Thank you!</b> Your message has been sent to the admin.",
        "admin_panel": (
            "🛡️ <b>Admin Panel</b>\n\n"
            "• <b>Host Environment:</b> <code>{env}</code>\n"
            "• <b>FFmpeg:</b> <code>{ffmpeg_ok}</code>\n"
            "• <b>Total Users:</b> <code>{users:,}</code>\n"
            "• <b>Total Downloads:</b> <code>{downloads:,}</code>\n"
            "• <b>RapidAPI Fallback:</b> <code>{rapidapi}</code>\n\n"
            "<b>Admin Commands:</b>\n"
            "• <code>/adminstats</code> — Detailed stats\n"
            "• <code>/broadcast &lt;message&gt;</code> — Message all users\n"
            "• <code>/logs</code> — View recent error logs"
        ),
        "dl_starting": "⏳ <b>Initializing download...</b>",
        "dl_progress": (
            "📥 <b>Downloading Video...</b>\n\n"
            "<code>[{bar}] {pct:.1f}%</code>\n"
            "💾 <b>Size:</b> <code>{dl_mb:.2f} / {tot_mb:.2f} MB</code>\n"
            "🚀 <b>Speed:</b> <code>{spd_mb:.2f} MB/s</code> | ⏳ <b>ETA:</b> <code>{eta}</code>"
        ),
        "dl_processing": "⚙️ <b>Optimizing quality / converting to MP4...</b>",
        "dl_uploading": "📤 <b>Uploading video to Telegram...</b>",
        "dl_cancelled": "❌ <b>Download cancelled.</b>",
        "dl_success": "✅ <b>Video downloaded successfully!</b>",
        "dl_too_large": (
            "📦 <b>File Exceeds Telegram's 50 MB Bot Limit</b>\n\n"
            "The video is <b>{size_mb:.1f} MB</b>. Use the direct download button below:"
        ),
        "dl_too_large_no_url": (
            "📦 <b>File Too Large ({size_mb:.1f} MB)</b>\n\n"
            "Telegram limits bot uploads to 50 MB, and no smaller stream or direct link could be extracted."
        ),
        "dl_failed": "❌ <b>Download failed.</b> The video may be private, geo-blocked, age-restricted, or temporarily unavailable.",
        "invalid_url": "⚠️ Please send a valid video URL (YouTube, Facebook, Instagram, or TikTok) or choose a tool from the menu.",
        "qr_uploading_text": "⏳ Uploading text to <code>paste.rs</code> and generating QR code...",
        "qr_uploading_photo": "⏳ Uploading photo to <code>catbox.moe</code> and generating QR code...",
        "qr_done": "✅ <b>QR Code Generated!</b>\n🔗 <b>URL:</b> {url}\n\n⚠️ <i>Note: This link is publicly accessible.</i>",
        "qr_text_failed": "❌ <b>Failed to upload text to paste.rs.</b> No QR code was generated.",
        "qr_photo_failed": "❌ <b>Failed to upload photo to catbox.moe.</b> No QR code was generated.",
        "qr_need_input": "⚠️ Please send <b>text</b> or a <b>photo</b> to generate a QR code, or tap Back to Menu.",
        "v2a_processing": "🎵 <b>Downloading video and extracting MP3 audio...</b>",
        "v2a_too_big": "⚠️ Telegram bots can only download files up to <b>20 MB</b>. Please send a smaller video.",
        "v2a_out_too_big": "⚠️ The extracted MP3 exceeds Telegram's 50 MB upload limit.",
        "v2a_failed": "❌ <b>Audio conversion failed.</b> Ensure the video has an audio track and FFmpeg is installed.",
        "v2a_done": "✅ <b>MP3 Audio Extracted!</b>",
        "v2a_need_video": "⚠️ Please send a <b>video file</b> to convert to MP3, or tap Back to Menu.",
        "use_qr_mode": "ℹ️ To generate a QR code for an image, tap <b>📱 QR Code Generator</b> in the menu first.",
        "use_v2a_mode": "ℹ️ To convert a video to MP3, tap <b>🎵 Video to Audio</b> in the menu first.",
    },
    "bn": {
        "welcome": (
            "👋 <b>UniversalDL Pro-তে স্বাগতম, {name}!</b>\n\n"
            "🚀 অল-ইন-ওয়ান মিডিয়া টুলকিট: ভিডিও ডাউনলোডার, QR কোড জেনারেটর এবং ভিডিও থেকে MP3 কনভার্টার।\n\n"
            "👇 <b>নিচের মেনু থেকে একটি টুল বেছে নিন:</b>"
        ),
        "btn_video": "🎬 ভিডিও ডাউনলোডার",
        "btn_qr": "📱 QR কোড জেনারেটর",
        "btn_v2a": "🎵 ভিডিও থেকে অডিও",
        "btn_profile": "👤 প্রোফাইল",
        "btn_stats": "📊 পরিসংখ্যান",
        "btn_help": "ℹ️ সাহায্য / গাইড",
        "btn_lang": "🌐 ভাষা",
        "btn_admin": "🛡️ অ্যাডমিন / সাপোর্ট",
        "btn_feedback": "✍️ মতামত পাঠান",
        "btn_contact_admin": "💬 অ্যাডমিনের সাথে যোগাযোগ",
        "btn_back": "🔙 মেনুতে ফিরুন",
        "btn_cancel": "❌ ডাউনলোড বাতিল",
        "btn_direct_dl": "📥 সরাসরি ডাউনলোড লিংক",
        "video_prompt": (
            "🎬 <b>ভিডিও ডাউনলোডার</b>\n\n"
            "যেকোনো পাবলিক ভিডিও লিংক পাঠান:\n"
            "• YouTube (ভিডিও ও শর্টস)\n"
            "• Facebook (ওয়াচ ও রিলস)\n"
            "• Instagram (রিলস ও পোস্ট)\n"
            "• TikTok\n\n"
            "<i>মান: অডিওসহ সর্বোচ্চ 1080p MP4।</i>"
        ),
        "qr_prompt": (
            "📱 <b>QR কোড জেনারেটর</b>\n\n"
            "যেকোনো একটি পাঠান:\n"
            "1️⃣ <b>টেক্সট</b> (শেয়ারযোগ্য লিংকের জন্য <code>paste.rs</code>-এ আপলোড হবে)\n"
            "2️⃣ <b>ছবি/ফটো</b> (ছবির লিংকের জন্য <code>catbox.moe</code>-এ আপলোড হবে)\n\n"
            "⚠️ <b>গোপনীয়তা সতর্কতা:</b> আপলোড করা টেক্সট এবং ছবি পাবলিক সার্ভারে সংরক্ষিত হয় এবং লিংক থাকা যে কেউ তা দেখতে পারেন।"
        ),
        "v2a_prompt": (
            "🎵 <b>ভিডিও থেকে অডিও (MP3)</b>\n\n"
            "একটি টেলিগ্রাম ভিডিও ফাইল পাঠান (সর্বোচ্চ <b>২০ MB</b>), আমি অডিও আলাদা করে MP3 পাঠিয়ে দেব।"
        ),
        "profile_text": (
            "👤 <b>আপনার প্রোফাইল</b>\n\n"
            "• <b>নাম:</b> {name}\n"
            "• <b>ইউজার আইডি:</b> <code>{user_id}</code>\n"
            "• <b>ইউজারনেম:</b> {username}\n"
            "• <b>ভাষা:</b> {lang_label}\n"
            "• <b>আপনার ডাউনলোড:</b> <code>{downloads}</code>\n"
            "• <b>তৈরি QR কোড:</b> <code>{qr_count}</code>\n"
            "• <b>MP3 রূপান্তর:</b> <code>{v2a_count}</code>"
        ),
        "stats_text": (
            "📊 <b>গ্লোবাল বট পরিসংখ্যান</b>\n\n"
            "• <b>মোট ব্যবহারকারী:</b> <code>{users:,}</code>\n"
            "• <b>মোট ভিডিও ডাউনলোড:</b> <code>{downloads:,}</code>\n"
            "• <b>মোট QR কোড:</b> <code>{qr_count:,}</code>\n"
            "• <b>মোট MP3 রূপান্তর:</b> <code>{v2a_count:,}</code>"
        ),
        "help_text": (
            "ℹ️ <b>সাহায্য ও ব্যবহারবিধি</b>\n\n"
            "১. <b>ভিডিও ডাউনলোডার:</b> <i>ভিডিও ডাউনলোডার</i>-এ চাপুন (অথবা সরাসরি লিংক দিন)। ৪৯ MB-এর বড় হলে বট ছোট মান নামানোর চেষ্টা করবে অথবা সরাসরি লিংক দেবে।\n"
            "২. <b>QR কোড জেনারেটর:</b> বাটনে চেপে টেক্সট বা ছবি পাঠান। টেক্সট paste.rs এবং ছবি catbox.moe-তে আপলোড হবে।\n"
            "৩. <b>ভিডিও থেকে অডিও:</b> বাটনে চেপে ২০ MB-এর মধ্যে ভিডিও পাঠিয়ে MP3 নিন।\n"
            "৪. <b>ভাষা:</b> যেকোনো সময় ইংরেজি, বাংলা বা মালয় ভাষা বেছে নিন।"
        ),
        "lang_prompt": "🌐 <b>আপনার পছন্দের ভাষা নির্বাচন করুন:</b>",
        "lang_updated": "✅ ভাষা পরিবর্তন করে <b>বাংলা</b> করা হয়েছে।",
        "support_text": (
            "🛡️ <b>সাপোর্ট ও মতামত</b>\n\n"
            "কোনো লিংকে সমস্যা হলে লিংকটি পাবলিক কি না যাচাই করে আবার চেষ্টা করুন।\n"
            "সরাসরি অ্যাডমিনকে মেসেজ পাঠাতে নিচের বাটনে চাপুন।"
        ),
        "feedback_prompt": "✍️ <b>মতামত পাঠান</b>\nআপনার মেসেজটি লিখে পাঠান, এটি সরাসরি অ্যাডমিনের কাছে চলে যাবে:",
        "feedback_sent": "✅ <b>ধন্যবাদ!</b> আপনার মেসেজটি অ্যাডমিনের কাছে পাঠানো হয়েছে।",
        "admin_panel": (
            "🛡️ <b>অ্যাডমিন প্যানেল</b>\n\n"
            "• <b>হোস্ট এনভায়রনমেন্ট:</b> <code>{env}</code>\n"
            "• <b>FFmpeg স্ট্যাটাস:</b> <code>{ffmpeg_ok}</code>\n"
            "• <b>মোট ব্যবহারকারী:</b> <code>{users:,}</code>\n"
            "• <b>মোট ডাউনলোড:</b> <code>{downloads:,}</code>\n"
            "• <b>RapidAPI ফলব্যাক:</b> <code>{rapidapi}</code>\n\n"
            "<b>অ্যাডমিন কমান্ড:</b>\n"
            "• <code>/adminstats</code> — বিস্তারিত পরিসংখ্যান\n"
            "• <code>/broadcast &lt;বার্তা&gt;</code> — সবাইকে বার্তা পাঠান\n"
            "• <code>/logs</code> — সাম্প্রতিক লগ দেখুন"
        ),
        "dl_starting": "⏳ <b>ডাউনলোড শুরু হচ্ছে...</b>",
        "dl_progress": (
            "📥 <b>ভিডিও ডাউনলোড হচ্ছে...</b>\n\n"
            "<code>[{bar}] {pct:.1f}%</code>\n"
            "💾 <b>সাইজ:</b> <code>{dl_mb:.2f} / {tot_mb:.2f} MB</code>\n"
            "🚀 <b>গতি:</b> <code>{spd_mb:.2f} MB/s</code> | ⏳ <b>বাকি:</b> <code>{eta}</code>"
        ),
        "dl_processing": "⚙️ <b>কোয়ালিটি ঠিক ও MP4-এ রূপান্তর হচ্ছে...</b>",
        "dl_uploading": "📤 <b>টেলিগ্রামে ভিডিও আপলোড হচ্ছে...</b>",
        "dl_cancelled": "❌ <b>ডাউনলোড বাতিল করা হয়েছে।</b>",
        "dl_success": "✅ <b>ভিডিও সফলভাবে নামানো হয়েছে!</b>",
        "dl_too_large": (
            "📦 <b>ফাইলটি টেলিগ্রামের ৫০ MB সীমার চেয়ে বড়</b>\n\n"
            "ফাইলের আকার ছিল <b>{size_mb:.1f} MB</b>। নিচের ডাইরেক্ট ডাউনলোড বাটনটি ব্যবহার করুন:"
        ),
        "dl_too_large_no_url": (
            "📦 <b>ফাইলটি অনেক বড় ({size_mb:.1f} MB)</b>\n\n"
            "টেলিগ্রাম বট ৫০ MB-এর বেশি ফাইল পাঠাতে পারে না এবং ছোট সাইজ বা ডাইরেক্ট লিংক পাওয়া যায়নি।"
        ),
        "dl_failed": "❌ <b>ডাউনলোড ব্যর্থ হয়েছে।</b> ভিডিওটি প্রাইভেট, বয়স-সীমাবদ্ধ বা সাময়িকভাবে বন্ধ থাকতে পারে।",
        "invalid_url": "⚠️ অনুগ্রহ করে একটি সঠিক ভিডিও লিংক (YouTube, Facebook, Instagram বা TikTok) পাঠান অথবা মেনু ব্যবহার করুন।",
        "qr_uploading_text": "⏳ টেক্সট <code>paste.rs</code>-এ আপলোড করে QR কোড তৈরি হচ্ছে...",
        "qr_uploading_photo": "⏳ ছবি <code>catbox.moe</code>-এ আপলোড করে QR কোড তৈরি হচ্ছে...",
        "qr_done": "✅ <b>QR কোড তৈরি সম্পন্ন!</b>\n🔗 <b>লিংক:</b> {url}\n\n⚠️ <i>সতর্কতা: এই লিংকটি পাবলিক।</i>",
        "qr_text_failed": "❌ <b>paste.rs-এ টেক্সট আপলোড ব্যর্থ হয়েছে।</b> কোনো QR কোড তৈরি করা হয়নি।",
        "qr_photo_failed": "❌ <b>catbox.moe-এ ছবি আপলোড ব্যর্থ হয়েছে।</b> কোনো QR কোড তৈরি করা হয়নি।",
        "qr_need_input": "⚠️ QR কোড তৈরি করতে <b>টেক্সট</b> বা <b>ছবি</b> পাঠান, অথবা মেনুতে ফিরে যান।",
        "v2a_processing": "🎵 <b>ভিডিও ডাউনলোড করে MP3 অডিও তৈরি হচ্ছে...</b>",
        "v2a_too_big": "⚠️ টেলিগ্রাম বট সর্বোচ্চ <b>২০ MB</b> ফাইল ডাউনলোড করতে পারে। ছোট ভিডিও পাঠান।",
        "v2a_out_too_big": "⚠️ তৈরি করা MP3 ফাইলটি ৫০ MB সীমা অতিক্রম করেছে।",
        "v2a_failed": "❌ <b>অডিও রূপান্তর ব্যর্থ হয়েছে।</b> ভিডিওটিতে অডিও আছে কি না এবং FFmpeg ঠিক আছে কি না দেখুন।",
        "v2a_done": "✅ <b>MP3 অডিও সফলভাবে তৈরি হয়েছে!</b>",
        "v2a_need_video": "⚠️ MP3 করতে একটি <b>ভিডিও ফাইল</b> পাঠান, অথবা মেনুতে ফিরে যান।",
        "use_qr_mode": "ℹ️ ছবির QR কোড বানাতে প্রথমে মেনু থেকে <b>📱 QR কোড জেনারেটর</b> বাটনে চাপুন।",
        "use_v2a_mode": "ℹ️ ভিডিও থেকে MP3 বানাতে প্রথমে মেনু থেকে <b>🎵 ভিডিও থেকে অডিও</b> বাটনে চাপুন।",
    },
    "ms": {
        "welcome": (
            "👋 <b>Selamat datang ke UniversalDL Pro, {name}!</b>\n\n"
            "🚀 Kit alat media lengkap: Pemuat Turun Video, Penjana Kod QR, dan Penukar Video ke MP3.\n\n"
            "👇 <b>Pilih alat daripada menu di bawah:</b>"
        ),
        "btn_video": "🎬 Muat Turun Video",
        "btn_qr": "📱 Penjana Kod QR",
        "btn_v2a": "🎵 Video ke Audio",
        "btn_profile": "👤 Profil",
        "btn_stats": "📊 Statistik",
        "btn_help": "ℹ️ Bantuan / Panduan",
        "btn_lang": "🌐 Bahasa",
        "btn_admin": "🛡️ Admin / Sokongan",
        "btn_feedback": "✍️ Hantar Maklum Balas",
        "btn_contact_admin": "💬 Hubungi Admin",
        "btn_back": "🔙 Kembali ke Menu",
        "btn_cancel": "❌ Batal Muat Turun",
        "btn_direct_dl": "📥 Pautan Muat Turun Terus",
        "video_prompt": (
            "🎬 <b>Muat Turun Video</b>\n\n"
            "Hantar sebarang pautan video awam daripada:\n"
            "• YouTube (Video &amp; Shorts)\n"
            "• Facebook (Watch &amp; Reels)\n"
            "• Instagram (Reels &amp; Siaran)\n"
            "• TikTok\n\n"
            "<i>Kualiti: Sehingga 1080p MP4 dengan audio.</i>"
        ),
        "qr_prompt": (
            "📱 <b>Penjana Kod QR</b>\n\n"
            "Hantar salah satu:\n"
            "1️⃣ <b>Teks</b> (dimuat naik ke <code>paste.rs</code> untuk cipta pautan kongsi)\n"
            "2️⃣ <b>Foto</b> (dimuat naik ke <code>catbox.moe</code> untuk cipta pautan imej)\n\n"
            "⚠️ <b>Notis Privasi:</b> Teks dan imej yang dimuat naik dihoskan di pelayan awam pihak ketiga dan boleh diakses oleh sesiapa yang mempunyai pautan."
        ),
        "v2a_prompt": (
            "🎵 <b>Video ke Audio (MP3)</b>\n\n"
            "Hantar fail video Telegram (sehingga <b>20 MB</b>) dan saya akan mengekstrak audio ke format MP3."
        ),
        "profile_text": (
            "👤 <b>Profil Anda</b>\n\n"
            "• <b>Nama:</b> {name}\n"
            "• <b>ID Pengguna:</b> <code>{user_id}</code>\n"
            "• <b>Nama Pengguna:</b> {username}\n"
            "• <b>Bahasa:</b> {lang_label}\n"
            "• <b>Muat Turun Anda:</b> <code>{downloads}</code>\n"
            "• <b>Kod QR Dicipta:</b> <code>{qr_count}</code>\n"
            "• <b>Penukaran MP3:</b> <code>{v2a_count}</code>"
        ),
        "stats_text": (
            "📊 <b>Statistik Global Bot</b>\n\n"
            "• <b>Jumlah Pengguna:</b> <code>{users:,}</code>\n"
            "• <b>Jumlah Muat Turun Video:</b> <code>{downloads:,}</code>\n"
            "• <b>Jumlah Kod QR:</b> <code>{qr_count:,}</code>\n"
            "• <b>Jumlah Penukaran MP3:</b> <code>{v2a_count:,}</code>"
        ),
        "help_text": (
            "ℹ️ <b>Bantuan &amp; Panduan Pengguna</b>\n\n"
            "1. <b>Muat Turun Video:</b> Tekan <i>Muat Turun Video</i> (atau hantar pautan terus) untuk muat turun sehingga 1080p MP4. Fail melebihi 49 MB akan cuba dimuat turun dalam saiz lebih kecil atau melalui pautan terus.\n"
            "2. <b>Penjana Kod QR:</b> Tekan <i>Penjana Kod QR</i>, kemudian hantar teks atau foto.\n"
            "3. <b>Video ke Audio:</b> Tekan <i>Video ke Audio</i> dan hantar video Telegram (&lt;= 20 MB) untuk dapatkan fail MP3.\n"
            "4. <b>Bahasa:</b> Tukar bahasa antara Inggeris, Bengali, dan Melayu pada bila-bila masa."
        ),
        "lang_prompt": "🌐 <b>Pilih bahasa pilihan anda:</b>",
        "lang_updated": "✅ Bahasa ditukar kepada <b>Bahasa Melayu</b>.",
        "support_text": (
            "🛡️ <b>Sokongan &amp; Maklum Balas</b>\n\n"
            "Jika pautan bermasalah, pastikan video bersifat awam dan cuba lagi.\n"
            "Anda boleh menghantar maklum balas terus kepada admin melalui butang di bawah."
        ),
        "feedback_prompt": "✍️ <b>Hantar Maklum Balas</b>\nTaipkan mesej anda di bawah untuk dihantar kepada admin:",
        "feedback_sent": "✅ <b>Terima kasih!</b> Mesej anda telah dihantar kepada admin.",
        "admin_panel": (
            "🛡️ <b>Panel Admin</b>\n\n"
            "• <b>Persekitaran Hos:</b> <code>{env}</code>\n"
            "• <b>FFmpeg:</b> <code>{ffmpeg_ok}</code>\n"
            "• <b>Jumlah Pengguna:</b> <code>{users:,}</code>\n"
            "• <b>Jumlah Muat Turun:</b> <code>{downloads:,}</code>\n"
            "• <b>Sandaran RapidAPI:</b> <code>{rapidapi}</code>\n\n"
            "<b>Arahan Admin:</b>\n"
            "• <code>/adminstats</code> — Statistik terperinci\n"
            "• <code>/broadcast &lt;mesej&gt;</code> — Siar mesej kepada semua pengguna\n"
            "• <code>/logs</code> — Lihat log ralat terkini"
        ),
        "dl_starting": "⏳ <b>Memulakan muat turun...</b>",
        "dl_progress": (
            "📥 <b>Memuat Turun Video...</b>\n\n"
            "<code>[{bar}] {pct:.1f}%</code>\n"
            "💾 <b>Saiz:</b> <code>{dl_mb:.2f} / {tot_mb:.2f} MB</code>\n"
            "🚀 <b>Kelajuan:</b> <code>{spd_mb:.2f} MB/s</code> | ⏳ <b>Baki:</b> <code>{eta}</code>"
        ),
        "dl_processing": "⚙️ <b>Mengoptimumkan kualiti &amp; menukar ke MP4...</b>",
        "dl_uploading": "📤 <b>Memuat naik video ke Telegram...</b>",
        "dl_cancelled": "❌ <b>Muat turun dibatalkan.</b>",
        "dl_success": "✅ <b>Video berjaya dimuat turun!</b>",
        "dl_too_large": (
            "📦 <b>Fail Melebihi Had 50 MB Telegram</b>\n\n"
            "Saiz video ialah <b>{size_mb:.1f} MB</b>. Gunakan butang muat turun terus di bawah:"
        ),
        "dl_too_large_no_url": (
            "📦 <b>Fail Terlalu Besar ({size_mb:.1f} MB)</b>\n\n"
            "Telegram mengehadkan muat naik bot kepada 50 MB dan tiada pautan alternatif ditemui."
        ),
        "dl_failed": "❌ <b>Muat turun gagal.</b> Video mungkin peribadi, disekat, atau pautan tidak sah.",
        "invalid_url": "⚠️ Sila hantar pautan video yang sah (YouTube, Facebook, Instagram, atau TikTok) atau guna menu di bawah.",
        "qr_uploading_text": "⏳ Memuat naik teks ke <code>paste.rs</code> dan menjana kod QR...",
        "qr_uploading_photo": "⏳ Memuat naik foto ke <code>catbox.moe</code> dan menjana kod QR...",
        "qr_done": "✅ <b>Kod QR Berjaya Dijana!</b>\n🔗 <b>Pautan:</b> {url}\n\n⚠️ <i>Nota: Pautan ini boleh diakses secara umum.</i>",
        "qr_text_failed": "❌ <b>Gagal memuat naik teks ke paste.rs.</b> Tiada kod QR dijana.",
        "qr_photo_failed": "❌ <b>Gagal memuat naik foto ke catbox.moe.</b> Tiada kod QR dijana.",
        "qr_need_input": "⚠️ Sila hantar <b>teks</b> atau <b>foto</b> untuk menjana kod QR, atau kembali ke menu.",
        "v2a_processing": "🎵 <b>Memuat turun video dan mengekstrak audio MP3...</b>",
        "v2a_too_big": "⚠️ Bot Telegram hanya boleh memuat turun fail sehingga <b>20 MB</b>. Sila hantar video yang lebih kecil.",
        "v2a_out_too_big": "⚠️ Fail MP3 yang dihasilkan melebihi had muat naik 50 MB Telegram.",
        "v2a_failed": "❌ <b>Penukaran audio gagal.</b> Pastikan video mempunyai trek audio dan FFmpeg dipasang.",
        "v2a_done": "✅ <b>Audio MP3 berjaya diekstrak!</b>",
        "v2a_need_video": "⚠️ Sila hantar <b>fail video</b> untuk ditukar ke MP3, atau kembali ke menu.",
        "use_qr_mode": "ℹ️ Untuk menjana kod QR bagi imej, tekan <b>📱 Penjana Kod QR</b> di menu dahulu.",
        "use_v2a_mode": "ℹ️ Untuk mengekstrak MP3 daripada video, tekan <b>🎵 Video ke Audio</b> di menu dahulu.",
    },
}

LANG_LABELS = {"en": "🇬🇧 English", "bn": "🇧🇩 বাংলা", "ms": "🇲🇾 Bahasa Melayu"}


# ---------------------------------------------------------------------------
# 4. SQLite Persistent Database
# ---------------------------------------------------------------------------
class Database:
    """Thread-safe SQLite database for users and statistics."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    first_name TEXT DEFAULT '',
                    language TEXT DEFAULT 'en',
                    downloads_count INTEGER DEFAULT 0,
                    qr_count INTEGER DEFAULT 0,
                    v2a_count INTEGER DEFAULT 0,
                    joined_at TEXT NOT NULL,
                    last_active TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_user(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, joined_at, last_active)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_active = excluded.last_active
                """,
                (user_id, username or "", first_name or "User", now, now),
            )
            conn.commit()

    def get_lang(self, user_id: int) -> str:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row and row["language"] in STRINGS:
                return row["language"]
        return "en"

    def set_lang(self, user_id: int, lang: str) -> None:
        if lang not in STRINGS:
            lang = "en"
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
            conn.commit()

    def increment_stat(self, user_id: int, column: str) -> None:
        if column not in {"downloads_count", "qr_count", "v2a_count"}:
            return
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE users SET {column} = {column} + 1 WHERE user_id = ?", (user_id,))
            conn.commit()

    def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_global_stats(self) -> dict[str, int]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_users,
                    COALESCE(SUM(downloads_count), 0) AS total_downloads,
                    COALESCE(SUM(qr_count), 0) AS total_qr,
                    COALESCE(SUM(v2a_count), 0) AS total_v2a
                FROM users
                """
            ).fetchone()
            return {
                "total_users": row["total_users"],
                "total_downloads": row["total_downloads"],
                "total_qr": row["total_qr"],
                "total_v2a": row["total_v2a"],
            }

    def get_all_user_ids(self) -> list[int]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM users").fetchall()
            return [int(r["user_id"]) for r in rows]


DB = Database(DB_PATH)


def tr(user_id: int, key: str) -> str:
    lang = DB.get_lang(user_id)
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))


# ---------------------------------------------------------------------------
# 5. Cloud Keep-Alive HTTP Server (Auto-active on Render / PaaS)
# ---------------------------------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"UniversalDL Bot Online | Env: {HOST_ENV}".encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_health_server_if_needed() -> None:
    port_env = os.getenv("PORT", "").strip()
    is_paas = any(
        os.getenv(v)
        for v in ("RENDER", "RENDER_SERVICE_ID", "RAILWAY_ENVIRONMENT", "KOYEB_APP_NAME", "FLY_APP_NAME", "DYNO")
    )
    if not port_env and not is_paas:
        return
    port = int(port_env or "8080")
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("Keep-alive HTTP server started on port %d (%s)", port, HOST_ENV)
    except OSError as exc:
        logger.warning("Health server could not bind port %d: %s", port, exc)


# ---------------------------------------------------------------------------
# 6. URL Parsing & Cleaning
# ---------------------------------------------------------------------------
SUPPORTED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "tiktok.com",
    "vt.tiktok.com",
    "vm.tiktok.com",
)


def extract_first_url(text: str) -> Optional[str]:
    match = re.search(r"(https?://\S+)", text)
    return match.group(1).rstrip(".,!?)>]'\"") if match else None


def is_supported_video_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return any(domain in host for domain in SUPPORTED_DOMAINS)
    except Exception:
        return False


def clean_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()

    if "youtube.com" in host or "youtu.be" in host:
        if "/shorts/" in parsed.path:
            video_id = parsed.path.split("/shorts/")[-1].split("/")[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
        qs = parse_qs(parsed.query)
        qs.pop("si", None)
        qs.pop("feature", None)
        return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    if "facebook.com" in host or "fb.watch" in host:
        if any(k in url for k in ("facebook.com/share", "fb.watch", "facebook.com/reel")):
            try:
                r = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)"},
                    allow_redirects=True,
                    timeout=10,
                )
                if "facebook.com" in r.url:
                    parsed = urlparse(r.url)
            except Exception:
                pass
        if parsed.path.startswith("/watch") or "story.php" in parsed.path:
            qs = parse_qs(parsed.query)
            kept = {k: v for k, v in qs.items() if k in ("v", "story_fbid", "id")}
            return urlunparse(parsed._replace(query=urlencode(kept, doseq=True)))
        return urlunparse(parsed._replace(query=""))

    if "instagram.com" in host:
        qs = parse_qs(parsed.query)
        qs.pop("igsh", None)
        qs.pop("igshid", None)
        return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    return url


# ---------------------------------------------------------------------------
# 7. FFmpeg Validation & Conversion Helpers
# ---------------------------------------------------------------------------
def get_ffmpeg_bin() -> Optional[str]:
    return shutil.which("ffmpeg")


def get_ffprobe_bin() -> Optional[str]:
    return shutil.which("ffprobe")


def validate_video_file(file_path: Path) -> bool:
    if not file_path.exists() or not file_path.is_file():
        return False
    if file_path.suffix.lower() in {".part", ".ytdl", ".tmp"} or file_path.stat().st_size < 8192:
        return False

    ffprobe = get_ffprobe_bin()
    if not ffprobe:
        return True
    try:
        proc = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1", str(file_path),
            ],
            capture_output=True, text=True, timeout=20, check=False,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except Exception:
        return False


def ensure_mp4(file_path: Path) -> Path:
    if file_path.suffix.lower() == ".mp4":
        return file_path
    ffmpeg = get_ffmpeg_bin()
    if not ffmpeg:
        return file_path
    out_path = file_path.with_suffix(".mp4")
    try:
        subprocess.run(
            [
                ffmpeg, "-y", "-i", str(file_path),
                "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
                "-movflags", "+faststart", str(out_path),
            ],
            capture_output=True, timeout=180, check=True,
        )
        if out_path.exists() and out_path.stat().st_size > 8192:
            file_path.unlink(missing_ok=True)
            return out_path
    except Exception as exc:
        logger.warning("MP4 conversion failed: %s", exc)
    return file_path


def extract_mp3_with_ffmpeg(input_video: Path, output_mp3: Path) -> bool:
    ffmpeg = get_ffmpeg_bin()
    if not ffmpeg:
        logger.error("FFmpeg binary not found!")
        return False
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(input_video), "-vn", "-acodec", "libmp3lame", "-b:a", "192k", str(output_mp3)],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if proc.returncode != 0:
            logger.warning("FFmpeg MP3 stderr: %s", proc.stderr[-500:])
            return False
        return output_mp3.exists() and output_mp3.stat().st_size > 1024
    except Exception as exc:
        logger.error("FFmpeg execution error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# 8. Multi-Engine Video Downloader
# ---------------------------------------------------------------------------
def update_job_progress(job_id: str, downloaded: int, total: int, speed: float, eta: float) -> None:
    with STATE_LOCK:
        JOB_PROGRESS[job_id] = {"downloaded": downloaded, "total": total, "speed": speed, "eta": eta}


def is_job_cancelled(job_id: str) -> bool:
    with STATE_LOCK:
        return ACTIVE_CANCELS.get(job_id, False)


def download_stream_with_resume(stream_url: str, save_path: Path, job_id: str, retries: int = 3) -> str:
    headers_base = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for attempt in range(1, retries + 1):
        if is_job_cancelled(job_id):
            raise DownloadCancelledError()

        existing = save_path.stat().st_size if save_path.exists() else 0
        headers = dict(headers_base)
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"

        try:
            with requests.get(stream_url, headers=headers, stream=True, timeout=30) as resp:
                if resp.status_code == 416:
                    return "OK" if (save_path.exists() and save_path.stat().st_size > 8192) else "FAILED"
                if existing > 0 and resp.status_code == 200:
                    existing = 0
                    mode = "wb"
                elif resp.status_code in (200, 206):
                    mode = "ab" if resp.status_code == 206 else "wb"
                else:
                    resp.raise_for_status()
                    mode = "wb"

                content_len = int(resp.headers.get("Content-Length", "0") or "0")
                total_size = existing + content_len if content_len > 0 else 0
                if total_size > MAX_DISK_DOWNLOAD_BYTES:
                    return "TOO_LARGE"

                downloaded = existing
                start_t = time.monotonic()
                with open(save_path, mode) as fh:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if is_job_cancelled(job_id):
                            raise DownloadCancelledError()
                        if not chunk:
                            continue
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > MAX_DISK_DOWNLOAD_BYTES:
                            return "TOO_LARGE"
                        elapsed = time.monotonic() - start_t
                        speed = (downloaded - existing) / elapsed if elapsed > 0 else 0.0
                        eta = (total_size - downloaded) / speed if (speed > 0 and total_size > downloaded) else 0.0
                        update_job_progress(job_id, downloaded, total_size, speed, eta)

            if save_path.exists() and save_path.stat().st_size > 8192:
                return "OK"
        except DownloadCancelledError:
            raise
        except Exception as exc:
            logger.warning("Stream attempt %d/%d failed: %s", attempt, retries, exc)
            time.sleep(1.2)
    return "FAILED"


def download_with_ytdlp(
    url: str,
    temp_dir: Path,
    job_id: str,
    compact_mode: bool = False,
    yt_clients: Optional[list[str]] = None,
) -> Optional[Path]:
    def progress_hook(d: dict[str, Any]) -> None:
        if is_job_cancelled(job_id):
            raise DownloadCancelledError()
        if d.get("status") == "downloading":
            update_job_progress(
                job_id,
                int(d.get("downloaded_bytes") or 0),
                int(d.get("total_bytes") or d.get("total_bytes_estimate") or 0),
                float(d.get("speed") or 0.0),
                float(d.get("eta") or 0.0),
            )

    fmt = (
        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/best"
        if compact_mode
        else "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080][ext=mp4]/best[height<=1080]/best"
    )

    ydl_opts: dict[str, Any] = {
        "format": fmt,
        "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 4,
        "fragment_retries": 4,
        "extractor_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "max_filesize": MAX_DISK_DOWNLOAD_BYTES,
        "socket_timeout": 25,
        "progress_hooks": [progress_hook],
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {"youtube": {"player_client": yt_clients or ["android", "ios"]}},
    }

    cookies_path = Path(COOKIES_FILE)
    if cookies_path.exists() and cookies_path.is_file():
        ydl_opts["cookiefile"] = str(cookies_path)

    if get_ffmpeg_bin():
        ydl_opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    candidates = [p for p in temp_dir.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not candidates:
        return None
    best = ensure_mp4(max(candidates, key=lambda p: p.stat().st_size))
    return best if validate_video_file(best) else None


def scrape_facebook_fdown(url: str) -> Optional[str]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://fdown.net/",
            "Origin": "https://fdown.net",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        res = requests.post("https://fdown.net/download.php", data={"URLz": url}, headers=headers, timeout=12)
        if res.status_code == 200:
            for pattern in (r'id=["\']hdlink["\'][^>]*href=["\']([^"\']+)["\']', r'id=["\']sdlink["\'][^>]*href=["\']([^"\']+)["\']'):
                m = re.search(pattern, res.text)
                if m:
                    return m.group(1).replace("&amp;", "&")
    except Exception:
        pass
    return None


def scrape_facebook_native(url: str) -> Optional[str]:
    try:
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)"},
            allow_redirects=True,
            timeout=12,
        )
        if res.status_code == 200:
            for pattern in (
                r'"browser_native_hd_url":"(https:[^"]+)"',
                r'"browser_native_sd_url":"(https:[^"]+)"',
                r'"playable_url_quality_hd":"(https:[^"]+)"',
                r'"playable_url":"(https:[^"]+)"',
            ):
                m = re.search(pattern, res.text)
                if m:
                    raw = m.group(1).replace("\\/", "/").replace("&amp;", "&")
                    if raw.startswith("http"):
                        return raw
    except Exception:
        pass
    return None


def scrape_tiktok_tikwm(url: str) -> Optional[str]:
    try:
        res = requests.get("https://tikwm.com/api/", params={"url": url}, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("code") == 0 and isinstance(data.get("data"), dict):
                play_url = data["data"].get("play")
                if isinstance(play_url, str) and play_url.startswith("http"):
                    return play_url
    except Exception:
        pass
    return None


def scrape_tiktok_lovetik(url: str) -> Optional[str]:
    try:
        res = requests.post("https://lovetik.com/api/ajax/search", data={"query": url}, timeout=12)
        if res.status_code == 200:
            data = res.json()
            links = data.get("links") or []
            if data.get("status") == "ok" and links:
                for item in links:
                    dl = item.get("a")
                    if dl and "watermark" not in str(item.get("t", "")).lower():
                        return dl
                return links[0].get("a")
    except Exception:
        pass
    return None


def scrape_youtube_invidious(url: str) -> Optional[str]:
    try:
        m = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)
        if not m:
            return None
        vid = m.group(1)
        for inst in ("https://inv.nadeko.net", "https://invidious.nerdvpn.de", "https://inv.tux.pizza"):
            try:
                res = requests.get(f"{inst}/api/v1/videos/{vid}", timeout=6)
                if res.status_code == 200:
                    streams = res.json().get("formatStreams") or []
                    if streams and streams[-1].get("url"):
                        return streams[-1]["url"]
            except Exception:
                continue
    except Exception:
        pass
    return None


def fallback_rapidapi_url(url: str) -> Optional[str]:
    if not (RAPIDAPI_KEY and RAPIDAPI_HOST):
        return None
    try:
        endpoint = f"https://{RAPIDAPI_HOST}/"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        resp = requests.post(endpoint, json={"url": url}, headers=headers, timeout=15)
        if resp.status_code != 200:
            resp = requests.get(endpoint, params={"url": url}, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            candidate = data.get("download_url") or data.get("url") or data.get("video")
            if not candidate and isinstance(data.get("medias"), list) and data["medias"]:
                candidate = data["medias"][0].get("url")
            if isinstance(candidate, str) and candidate.startswith("http"):
                return candidate
    except Exception as exc:
        logger.warning("RapidAPI fallback error: %s", exc)
    return None


def extract_direct_stream_url(url: str) -> Optional[str]:
    try:
        with yt_dlp.YoutubeDL({"format": "best[ext=mp4]/best", "quiet": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            direct = info.get("url")
            if isinstance(direct, str) and direct.startswith("http"):
                return direct
    except Exception:
        pass
    return fallback_rapidapi_url(url)


def run_download_pipeline(url: str, temp_dir: Path, job_id: str) -> tuple[Optional[Path], Optional[str], bool]:
    cleaned = clean_url(url)
    host = urlparse(cleaned).netloc.lower()
    is_youtube = "youtube.com" in host or "youtu.be" in host

    for clients in ([["android", "ios"], ["tv", "web"]] if is_youtube else [None]):
        if is_job_cancelled(job_id):
            raise DownloadCancelledError()
        try:
            video_path = download_with_ytdlp(cleaned, temp_dir, job_id, compact_mode=False, yt_clients=clients)
            if video_path:
                return video_path, None, False
        except DownloadCancelledError:
            raise
        except Exception as exc:
            logger.warning("yt-dlp attempt (clients=%s) failed: %s", clients, exc)

    if is_job_cancelled(job_id):
        raise DownloadCancelledError()

    candidates: list[Optional[str]] = []
    if is_youtube:
        candidates.append(scrape_youtube_invidious(cleaned))
    elif "facebook.com" in host or "fb.watch" in host:
        candidates.extend([scrape_facebook_fdown(cleaned), scrape_facebook_native(cleaned)])
    elif "tiktok.com" in host:
        candidates.extend([scrape_tiktok_tikwm(cleaned), scrape_tiktok_lovetik(cleaned)])
    candidates.append(fallback_rapidapi_url(cleaned))

    last_url: Optional[str] = None
    for idx, direct_url in enumerate(candidates):
        if not direct_url:
            continue
        last_url = direct_url
        out_file = temp_dir / f"fallback_{idx}.mp4"
        status = download_stream_with_resume(direct_url, out_file, job_id)
        if status == "TOO_LARGE":
            return None, direct_url, True
        if status == "OK":
            out_file = ensure_mp4(out_file)
            if validate_video_file(out_file):
                return out_file, direct_url, False

    return None, last_url, False


# ---------------------------------------------------------------------------
# 9. QR Code Generator Helpers (paste.rs & catbox.moe)
# ---------------------------------------------------------------------------
def upload_text_to_paste_rs(text: str) -> Optional[str]:
    try:
        resp = requests.post(
            "https://paste.rs/",
            data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=15,
        )
        if resp.status_code != 201:
            logger.warning("paste.rs status %s: %s", resp.status_code, resp.text[:200])
            return None
        url = resp.text.strip()
        return url if url.startswith("https://paste.rs/") else None
    except Exception as exc:
        logger.error("paste.rs error: %s", exc)
        return None


def upload_image_to_catbox(image_path: Path) -> Optional[str]:
    try:
        with open(image_path, "rb") as fh:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (image_path.name, fh)},
                timeout=30,
            )
        if resp.status_code != 200:
            logger.warning("catbox.moe status %s: %s", resp.status_code, resp.text[:200])
            return None
        url = resp.text.strip()
        return url if url.startswith("https://") else None
    except Exception as exc:
        logger.error("catbox.moe error: %s", exc)
        return None


def generate_qr_png(content_url: str, out_path: Path) -> Path:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(content_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img.save(out_path, format="PNG")
    return out_path


# ---------------------------------------------------------------------------
# 10. Keyboards & Formatters
# ---------------------------------------------------------------------------
def build_main_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "btn_video"), callback_data="menu_video_dl"),
                InlineKeyboardButton(tr(user_id, "btn_qr"), callback_data="menu_qr"),
            ],
            [
                InlineKeyboardButton(tr(user_id, "btn_v2a"), callback_data="menu_v2a"),
                InlineKeyboardButton(tr(user_id, "btn_profile"), callback_data="menu_profile"),
            ],
            [
                InlineKeyboardButton(tr(user_id, "btn_stats"), callback_data="menu_stats"),
                InlineKeyboardButton(tr(user_id, "btn_help"), callback_data="menu_help"),
            ],
            [
                InlineKeyboardButton(tr(user_id, "btn_lang"), callback_data="menu_lang"),
                InlineKeyboardButton(tr(user_id, "btn_admin"), callback_data="menu_admin"),
            ],
        ]
    )


def build_back_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(user_id, "btn_back"), callback_data="menu_home")]])


def build_support_menu(user_id: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(tr(user_id, "btn_feedback"), callback_data="menu_feedback")]]
    if ADMIN_USERNAME:
        rows.append([InlineKeyboardButton(tr(user_id, "btn_contact_admin"), url=f"https://t.me/{ADMIN_USERNAME}")])
    rows.append([InlineKeyboardButton(tr(user_id, "btn_back"), callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


def build_lang_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
            [InlineKeyboardButton("🇧🇩 বাংলা (Bengali)", callback_data="setlang_bn")],
            [InlineKeyboardButton("🇲🇾 Bahasa Melayu", callback_data="setlang_ms")],
            [InlineKeyboardButton(tr(user_id, "btn_back"), callback_data="menu_home")],
        ]
    )


def build_cancel_keyboard(user_id: int, job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(user_id, "btn_cancel"), callback_data=f"cancel_{job_id}")]])


def format_progress_message(user_id: int, prog: dict[str, Any]) -> str:
    downloaded = int(prog.get("downloaded", 0))
    total = int(prog.get("total", 0))
    speed = float(prog.get("speed", 0.0))
    eta = float(prog.get("eta", 0.0))
    pct = min(99.9, (downloaded / total * 100.0)) if total > 0 else 0.0
    filled = max(0, min(12, int(pct // 8.33)))
    bar = "█" * filled + "░" * (12 - filled)
    return tr(user_id, "dl_progress").format(
        bar=bar,
        pct=pct,
        dl_mb=downloaded / (1024 * 1024),
        tot_mb=(total / (1024 * 1024)) if total > 0 else 0.0,
        spd_mb=(speed / (1024 * 1024)) if speed > 0 else 0.0,
        eta=f"{int(eta)}s" if eta > 0 else "...",
    )


# ---------------------------------------------------------------------------
# 11. Command & Callback Handlers
# ---------------------------------------------------------------------------
async def set_bot_commands(app: Application) -> None:
    commands = [
        BotCommand("start", "Open Main Menu"),
        BotCommand("help", "Help & User Guide"),
        BotCommand("lang", "Change Language"),
        BotCommand("profile", "Your Profile"),
        BotCommand("stats", "Global Statistics"),
    ]
    try:
        await app.bot.set_my_commands(commands)
    except Exception as exc:
        logger.warning("Could not set bot commands: %s", exc)


def _sync_user(update: Update) -> int:
    u = update.effective_user
    DB.upsert_user(u.id, u.username, u.first_name)
    return u.id


def _render_profile_text(user_id: int) -> str:
    row = DB.get_user(user_id) or {}
    name = html.escape(row.get("first_name") or "User")
    uname = f"@{html.escape(row['username'])}" if row.get("username") else "N/A"
    lang = row.get("language", "en")
    return tr(user_id, "profile_text").format(
        name=name,
        user_id=user_id,
        username=uname,
        lang_label=LANG_LABELS.get(lang, LANG_LABELS["en"]),
        downloads=row.get("downloads_count", 0),
        qr_count=row.get("qr_count", 0),
        v2a_count=row.get("v2a_count", 0),
    )


def _render_stats_text(user_id: int) -> str:
    g = DB.get_global_stats()
    return tr(user_id, "stats_text").format(
        users=g["total_users"],
        downloads=g["total_downloads"],
        qr_count=g["total_qr"],
        v2a_count=g["total_v2a"],
    )


def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


def _render_admin_panel(user_id: int) -> str:
    g = DB.get_global_stats()
    return tr(user_id, "admin_panel").format(
        env=html.escape(HOST_ENV),
        ffmpeg_ok="Available" if get_ffmpeg_bin() else "Missing",
        users=g["total_users"],
        downloads=g["total_downloads"],
        rapidapi="Configured" if (RAPIDAPI_KEY and RAPIDAPI_HOST) else "Disabled",
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    context.user_data["mode"] = None
    name = html.escape(update.effective_user.first_name or "User")
    await update.message.reply_text(
        tr(user_id, "welcome").format(name=name),
        reply_markup=build_main_menu(user_id),
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    context.user_data["mode"] = None
    await update.message.reply_text(tr(user_id, "help_text"), reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML)


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    context.user_data["mode"] = None
    await update.message.reply_text(tr(user_id, "lang_prompt"), reply_markup=build_lang_menu(user_id), parse_mode=ParseMode.HTML)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    context.user_data["mode"] = None
    await update.message.reply_text(_render_profile_text(user_id), reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    context.user_data["mode"] = None
    await update.message.reply_text(_render_stats_text(user_id), reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML)


async def adminstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Admin access only.")
        return
    await update.message.reply_text(_render_admin_panel(user_id), parse_mode=ParseMode.HTML)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Admin access only.")
        return
    msg_text = " ".join(context.args).strip()
    if not msg_text:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    user_ids = DB.get_all_user_ids()
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(user_ids)} users...")
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=msg_text)
            sent += 1
        except RetryAfter as r_err:
            await asyncio.sleep(r_err.retry_after + 0.5)
            try:
                await context.bot.send_message(chat_id=uid, text=msg_text)
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status_msg.edit_text(f"✅ Broadcast complete.\nSent: {sent}\nFailed: {failed}")


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Admin access only.")
        return
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        await update.message.reply_text("Log file not found.")
        return
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            tail = "".join(fh.readlines()[-30:])[-3800:]
        await update.message.reply_text(f"<pre>{html.escape(tail or 'Empty log')}</pre>", parse_mode=ParseMode.HTML)
    except Exception as exc:
        await update.message.reply_text(f"Failed to read logs: {exc}")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    DB.upsert_user(user.id, user.username, user.first_name)
    data = query.data or ""
    await query.answer()

    if data.startswith("cancel_"):
        job_id = data.removeprefix("cancel_")
        with STATE_LOCK:
            ACTIVE_CANCELS[job_id] = True
        try:
            await query.edit_message_text(tr(user.id, "dl_cancelled"), parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
        return

    if data.startswith("setlang_"):
        DB.set_lang(user.id, data.removeprefix("setlang_"))
        context.user_data["mode"] = None
        name = html.escape(user.first_name or "User")
        text = f"{tr(user.id, 'lang_updated')}\n\n{tr(user.id, 'welcome').format(name=name)}"
        await query.edit_message_text(text, reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML)
        return

    if data == "menu_home":
        context.user_data["mode"] = None
        name = html.escape(user.first_name or "User")
        await query.edit_message_text(tr(user.id, "welcome").format(name=name), reply_markup=build_main_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_video_dl":
        context.user_data["mode"] = "video_dl"
        await query.edit_message_text(tr(user.id, "video_prompt"), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_qr":
        context.user_data["mode"] = "qr"
        await query.edit_message_text(tr(user.id, "qr_prompt"), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_v2a":
        context.user_data["mode"] = "v2a"
        await query.edit_message_text(tr(user.id, "v2a_prompt"), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_profile":
        context.user_data["mode"] = None
        await query.edit_message_text(_render_profile_text(user.id), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_stats":
        context.user_data["mode"] = None
        await query.edit_message_text(_render_stats_text(user.id), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_help":
        context.user_data["mode"] = None
        await query.edit_message_text(tr(user.id, "help_text"), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_lang":
        context.user_data["mode"] = None
        await query.edit_message_text(tr(user.id, "lang_prompt"), reply_markup=build_lang_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_feedback":
        context.user_data["mode"] = "feedback"
        await query.edit_message_text(tr(user.id, "feedback_prompt"), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
    elif data == "menu_admin":
        context.user_data["mode"] = None
        if is_admin(user.id):
            await query.edit_message_text(_render_admin_panel(user.id), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(tr(user.id, "support_text"), reply_markup=build_support_menu(user.id), parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# 12. Async Feature Workflows
# ---------------------------------------------------------------------------
async def process_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    job_id = uuid.uuid4().hex[:10]
    temp_dir = TEMP_ROOT / f"universal_dl_{job_id}"

    with STATE_LOCK:
        ACTIVE_CANCELS[job_id] = False
        JOB_PROGRESS[job_id] = {"downloaded": 0, "total": 0, "speed": 0.0, "eta": 0.0}

    status_msg = await update.message.reply_text(
        tr(user_id, "dl_starting"),
        reply_markup=build_cancel_keyboard(user_id, job_id),
        parse_mode=ParseMode.HTML,
    )

    loop = asyncio.get_running_loop()
    loop_active = True

    async def progress_updater() -> None:
        last_text = ""
        while loop_active and not is_job_cancelled(job_id):
            await asyncio.sleep(3.5)
            if not loop_active or is_job_cancelled(job_id):
                break
            with STATE_LOCK:
                prog = dict(JOB_PROGRESS.get(job_id, {}))
            if prog.get("downloaded", 0) <= 0:
                continue
            card = format_progress_message(user_id, prog)
            if card != last_text and not is_job_cancelled(job_id):
                last_text = card
                try:
                    await status_msg.edit_text(card, reply_markup=build_cancel_keyboard(user_id, job_id), parse_mode=ParseMode.HTML)
                except RetryAfter as r_err:
                    await asyncio.sleep(r_err.retry_after)
                except TelegramError:
                    pass

    progress_task = asyncio.create_task(progress_updater())

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        video_path, fallback_url, disk_too_large = await loop.run_in_executor(EXECUTOR, run_download_pipeline, url, temp_dir, job_id)
        loop_active = False
        progress_task.cancel()

        if is_job_cancelled(job_id):
            return

        if disk_too_large and fallback_url:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user_id, "btn_direct_dl"), url=fallback_url)]])
            await status_msg.edit_text(tr(user_id, "dl_too_large").format(size_mb=50.0), reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        if not video_path or not video_path.exists():
            await status_msg.edit_text(tr(user_id, "dl_failed"), parse_mode=ParseMode.HTML)
            return

        file_size = video_path.stat().st_size
        if file_size > MAX_TG_UPLOAD_BYTES:
            await status_msg.edit_text(tr(user_id, "dl_processing"), parse_mode=ParseMode.HTML)
            compact_dir = temp_dir / "compact"
            compact_dir.mkdir(exist_ok=True)
            try:
                compact_path = await loop.run_in_executor(EXECUTOR, download_with_ytdlp, clean_url(url), compact_dir, job_id, True, None)
                if compact_path and compact_path.stat().st_size <= MAX_TG_UPLOAD_BYTES:
                    video_path = compact_path
                    file_size = compact_path.stat().st_size
            except DownloadCancelledError:
                return
            except Exception as exc:
                logger.info("Compact fallback unavailable: %s", exc)

        if file_size <= MAX_TG_UPLOAD_BYTES:
            await status_msg.edit_text(tr(user_id, "dl_uploading"), parse_mode=ParseMode.HTML)
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
            with open(video_path, "rb") as vf:
                await context.bot.send_video(
                    chat_id=chat_id, video=vf, caption=tr(user_id, "dl_success"),
                    supports_streaming=True, read_timeout=300, write_timeout=300, parse_mode=ParseMode.HTML,
                )
            DB.increment_stat(user_id, "downloads_count")
            try:
                await status_msg.delete()
            except TelegramError:
                pass
        else:
            direct_url = fallback_url or await loop.run_in_executor(EXECUTOR, extract_direct_stream_url, clean_url(url))
            size_mb = file_size / (1024 * 1024)
            if direct_url and direct_url.startswith("http"):
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(tr(user_id, "btn_direct_dl"), url=direct_url)]])
                await status_msg.edit_text(tr(user_id, "dl_too_large").format(size_mb=size_mb), reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                await status_msg.edit_text(tr(user_id, "dl_too_large_no_url").format(size_mb=size_mb), parse_mode=ParseMode.HTML)

    except DownloadCancelledError:
        logger.info("Job %s cancelled by user %s", job_id, user_id)
    except Exception as exc:
        logger.exception("Video download error: %s", exc)
        try:
            await status_msg.edit_text(tr(user_id, "dl_failed"), parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
    finally:
        loop_active = False
        if not progress_task.done():
            progress_task.cancel()
        with STATE_LOCK:
            ACTIVE_CANCELS.pop(job_id, None)
            JOB_PROGRESS.pop(job_id, None)
        shutil.rmtree(temp_dir, ignore_errors=True)


async def process_qr_text(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str) -> None:
    user_id = update.effective_user.id
    if len(raw_text.encode("utf-8")) > MAX_TEXT_PASTE_BYTES:
        await update.message.reply_text(tr(user_id, "qr_text_failed"), parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text(tr(user_id, "qr_uploading_text"), parse_mode=ParseMode.HTML)
    temp_dir = TEMP_ROOT / f"universal_qr_{uuid.uuid4().hex[:10]}"
    loop = asyncio.get_running_loop()

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        paste_url = await loop.run_in_executor(EXECUTOR, upload_text_to_paste_rs, raw_text)
        if not paste_url:
            await status_msg.edit_text(tr(user_id, "qr_text_failed"), parse_mode=ParseMode.HTML)
            return

        qr_path = temp_dir / "qr_text.png"
        await loop.run_in_executor(EXECUTOR, generate_qr_png, paste_url, qr_path)
        with open(qr_path, "rb") as img_fh:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=img_fh,
                caption=tr(user_id, "qr_done").format(url=html.escape(paste_url)),
                reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML,
            )
        DB.increment_stat(user_id, "qr_count")
        try:
            await status_msg.delete()
        except TelegramError:
            pass
    except Exception as exc:
        logger.exception("QR text error: %s", exc)
        await status_msg.edit_text(tr(user_id, "qr_text_failed"), parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def process_qr_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message = update.message

    if message.photo:
        tg_obj, filename = message.photo[-1], "photo.jpg"
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        tg_obj, filename = message.document, (message.document.file_name or "image.png")
    else:
        await message.reply_text(tr(user_id, "qr_need_input"), parse_mode=ParseMode.HTML)
        return

    if getattr(tg_obj, "file_size", 0) and tg_obj.file_size > MAX_TG_DOWNLOAD_BYTES:
        await message.reply_text(tr(user_id, "v2a_too_big"), parse_mode=ParseMode.HTML)
        return

    status_msg = await message.reply_text(tr(user_id, "qr_uploading_photo"), parse_mode=ParseMode.HTML)
    temp_dir = TEMP_ROOT / f"universal_qrimg_{uuid.uuid4().hex[:10]}"
    loop = asyncio.get_running_loop()

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_img = temp_dir / Path(filename).name
        tg_file = await tg_obj.get_file()
        await tg_file.download_to_drive(custom_path=str(local_img))

        catbox_url = await loop.run_in_executor(EXECUTOR, upload_image_to_catbox, local_img)
        if not catbox_url:
            await status_msg.edit_text(tr(user_id, "qr_photo_failed"), parse_mode=ParseMode.HTML)
            return

        qr_path = temp_dir / "qr_photo.png"
        await loop.run_in_executor(EXECUTOR, generate_qr_png, catbox_url, qr_path)
        with open(qr_path, "rb") as img_fh:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=img_fh,
                caption=tr(user_id, "qr_done").format(url=html.escape(catbox_url)),
                reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML,
            )
        DB.increment_stat(user_id, "qr_count")
        try:
            await status_msg.delete()
        except TelegramError:
            pass
    except BadRequest as exc:
        logger.warning("Telegram photo download error: %s", exc)
        await status_msg.edit_text(tr(user_id, "qr_photo_failed"), parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("QR photo error: %s", exc)
        await status_msg.edit_text(tr(user_id, "qr_photo_failed"), parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def process_video_to_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message = update.message

    video_obj = message.video or (
        message.document if message.document and (message.document.mime_type or "").startswith("video/") else None
    )
    if not video_obj:
        await message.reply_text(tr(user_id, "v2a_need_video"), parse_mode=ParseMode.HTML)
        return

    if getattr(video_obj, "file_size", 0) and video_obj.file_size > MAX_TG_DOWNLOAD_BYTES:
        await message.reply_text(tr(user_id, "v2a_too_big"), parse_mode=ParseMode.HTML)
        return

    status_msg = await message.reply_text(tr(user_id, "v2a_processing"), parse_mode=ParseMode.HTML)
    temp_dir = TEMP_ROOT / f"universal_v2a_{uuid.uuid4().hex[:10]}"
    loop = asyncio.get_running_loop()

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        in_name = getattr(video_obj, "file_name", None) or "input_video.mp4"
        input_path = temp_dir / Path(in_name).name
        output_mp3 = temp_dir / f"{input_path.stem}.mp3"

        tg_file = await video_obj.get_file()
        await tg_file.download_to_drive(custom_path=str(input_path))

        success = await loop.run_in_executor(EXECUTOR, extract_mp3_with_ffmpeg, input_path, output_mp3)
        if not success:
            await status_msg.edit_text(tr(user_id, "v2a_failed"), parse_mode=ParseMode.HTML)
            return

        if output_mp3.stat().st_size > MAX_TG_UPLOAD_BYTES:
            await status_msg.edit_text(tr(user_id, "v2a_out_too_big"), parse_mode=ParseMode.HTML)
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_AUDIO)
        with open(output_mp3, "rb") as audio_fh:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id, audio=audio_fh, title=input_path.stem,
                caption=tr(user_id, "v2a_done"), reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML,
            )
        DB.increment_stat(user_id, "v2a_count")
        try:
            await status_msg.delete()
        except TelegramError:
            pass
    except BadRequest as exc:
        logger.warning("Telegram video download error: %s", exc)
        await status_msg.edit_text(tr(user_id, "v2a_too_big"), parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Video to audio error: %s", exc)
        await status_msg.edit_text(tr(user_id, "v2a_failed"), parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 13. Message Dispatchers & Entrypoint
# ---------------------------------------------------------------------------
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user_id = _sync_user(update)
    user = update.effective_user
    text = update.message.text.strip()
    mode = context.user_data.get("mode")

    if mode == "feedback":
        context.user_data["mode"] = None
        if ADMIN_ID:
            uname = f"@{html.escape(user.username)}" if user.username else "N/A"
            admin_msg = (
                "📬 <b>New User Feedback</b>\n"
                f"👤 <b>From:</b> {html.escape(user.first_name or 'User')} ({uname})\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n{html.escape(text)}"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode=ParseMode.HTML)
            except Exception as exc:
                logger.warning("Failed to forward feedback: %s", exc)
        await update.message.reply_text(tr(user_id, "feedback_sent"), reply_markup=build_main_menu(user_id), parse_mode=ParseMode.HTML)
        return

    if mode == "qr":
        await process_qr_text(update, context, text)
        return

    if mode == "v2a":
        await update.message.reply_text(tr(user_id, "v2a_need_video"), reply_markup=build_back_menu(user_id), parse_mode=ParseMode.HTML)
        return

    url = extract_first_url(text)
    if url and is_supported_video_url(url):
        await process_video_download(update, context, url)
    else:
        await update.message.reply_text(tr(user_id, "invalid_url"), reply_markup=build_main_menu(user_id), parse_mode=ParseMode.HTML)


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = _sync_user(update)
    if context.user_data.get("mode") == "qr":
        await process_qr_photo(update, context)
    else:
        await update.message.reply_text(tr(user_id, "use_qr_mode"), reply_markup=build_main_menu(user_id), parse_mode=ParseMode.HTML)


async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = _sync_user(update)
    if context.user_data.get("mode") == "v2a":
        await process_video_to_audio(update, context)
    else:
        await update.message.reply_text(tr(user_id, "use_v2a_mode"), reply_markup=build_main_menu(user_id), parse_mode=ParseMode.HTML)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error: %s", context.error, exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing! Copy .env.example to .env and set BOT_TOKEN.")
        raise SystemExit(1)

    logger.info("Environment: %s | Temp: %s | FFmpeg: %s", HOST_ENV, TEMP_ROOT, get_ffmpeg_bin() or "missing")
    start_health_server_if_needed()

    request = HTTPXRequest(connect_timeout=60.0, read_timeout=300.0, write_timeout=300.0, pool_timeout=60.0)
    app = ApplicationBuilder().token(TOKEN := BOT_TOKEN).request(request).post_init(set_bot_commands).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("adminstats", adminstats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo_message))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_error_handler(error_handler)

    logger.info("UniversalDL Bot is ONLINE (%s)!", HOST_ENV)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()