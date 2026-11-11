import os
import re
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

# Groq AI ইমপোর্ট (যদি থাকে)
try:
    from groq import Groq
except ImportError:
    Groq = None

# ---------------------------------------------------------------------------
# ১. রুট ছাড়া সার্ভারে FFmpeg লোড করা
# ---------------------------------------------------------------------------
try:
    static_ffmpeg.add_paths()
except Exception:
    pass

# ---------------------------------------------------------------------------
# ২. লগিং কনফিগারেশন
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ৩. কনস্ট্যান্ট ও এনভায়রনমেন্ট
# ---------------------------------------------------------------------------
TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"
MAX_TELEGRAM_UPLOAD_BYTES = 48 * 1024 * 1024  # টেলিগ্রাম ফ্রি বটের ৪৮ এমবি লিমিট

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set()
}

# Groq ক্লায়েন্ট ইনিশিয়ালাইজেশন
groq_client = None
if Groq and GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logger.warning(f"Groq Init Warning: {e}")

# ব্যাকআপ ফানি ওয়েটিং মেসেজ (যদি Groq সাময়িক অফলাইন থাকে)
BACKUP_WAITING_MESSAGES = [
    "☕ এক কাপ চা খেয়ে একটু হাসুন! ভিডিও নামাতে গিয়ে সার্ভারের তো প্রায় ঘাম ছুটে গেছে...",
    "🏃‍♂️ ধরো ধরো! ভিডিও চোর লিংক নিয়ে রকেটের বেগে দৌড় দিয়েছে আপনার দিকে...",
    "🧙‍♂️ জাদুকরী মন্ত্র পড়া চলছে: আব্রাবি-কা-ডাব্রা, ভিডিও হয়ে যা উধাও থেকে সরাসরি এখানে!",
    "🍔 একটা আস্ত বার্গার চিবিয়ে শেষ করতে যতোক্ষণ লাগবে, তার আগেই ভিডিও হাজির হচ্ছে...",
    "🚀 ইলন মাস্কের রকেটও লজ্জা পাবে ভাই, একটু ফুরফুরে মেজাজে অপেক্ষা করুন...",
    "🐒 বানর নাচ দেখতে দেখতেই ভিডিও ডাউনলোড হয়ে যাবে, একটু চিল করুন বস!"
]

# ---------------------------------------------------------------------------
# ৪. Groq AI জেনারেটর (ফানি ডায়ালগ ও এরর ব্যাখ্যা)
# ---------------------------------------------------------------------------
def generate_ai_waiting_text() -> str:
    """Groq AI দিয়ে প্রতিবার র্যান্ডম হাসির ডায়ালগ তৈরি"""
    if not groq_client:
        return random.choice(BACKUP_WAITING_MESSAGES)
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a hilarious, friendly, witty Bangladeshi Telegram Video Bot. Generate a short 1-line funny Bengali status telling the user to wait while their video is being fetched/cooked. Add funny emojis. Keep it under 20 words."
                },
                {"role": "user", "content": "Tell me to wait in a funny way"}
            ],
            max_tokens=60,
            temperature=1.0
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return random.choice(BACKUP_WAITING_MESSAGES)

def generate_ai_error_explanation(technical_error: str) -> str:
    """Groq AI দিয়ে ব্যবহারকারীকে সহজ বাংলায় বুঝিয়ে বলা কেন ভিডিও নামেনি"""
    if not groq_client:
        err = technical_error.lower()
        if "private" in err or "login" in err:
            return "❌ বস, ভিডিওটা প্রাইভেট বা ফ্রেন্ডস-অনলি করা! মালিক তালা মেরে রাখলে তো পুলিশও ঢুকতে পারবে না, আমি কোত্থেকে আনব? 😂 পাবলিক কোনো লিংক দিন!"
        return "❌ লিংকটায় কোনো ঘাপলা আছে বা সাইটটা ব্লক করেছে বস! অন্য কোনো সঠিক পাবলিক লিংক দিয়ে ট্রাই করুন তো দেখি।"
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a witty, hilarious Bangladeshi bot. A video download failed. Explain to the user in funny colloquial Bengali (ঢাকা/বাংলা ফানি টোন) why it failed based on the error. Keep it simple, funny, and 2 sentences max with emojis."
                },
                {"role": "user", "content": f"The technical error is: {technical_error}"}
            ],
            max_tokens=100,
            temperature=0.8
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return "❌ এই লিংক থেকে ভিডিও নামানো গেল না বস! হয়তো ভিডিওটি প্রাইভেট করা বা লিংকটি ভুল। পাবলিক কোনো লিংক দিন!"

# ---------------------------------------------------------------------------
# ৫. Render Free Web Service পোর্ট কিপ-অ্যালাইভ
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - AI Ultimate Bot is Running 24/7")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------------------------
# ৬. স্মার্ট লিংক ক্লিনার
# ---------------------------------------------------------------------------
def clean_and_resolve_url(url: str) -> str:
    clean_url = url.split("?")[0].strip()
    if "facebook.com/share" in url or "fb.watch" in url:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            })
            resp = session.get(url, allow_redirects=True, timeout=8)
            resolved = resp.url.split("?")[0]
            if "facebook.com" in resolved and ("videos" in resolved or "reel" in resolved or "watch" in resolved):
                return resolved
        except Exception:
            pass
    return clean_url if clean_url.startswith("http") else url

# ---------------------------------------------------------------------------
# ৭. স্মার্ট ভিডিও ডাউনলোডার (অটো কোয়ালিটি অ্যাডজাস্ট)
# ---------------------------------------------------------------------------
def download_media_smart(url: str, output_path: str):
    """
    ভিডিওর রেজোলিউশন স্মার্টলি অ্যাডজাস্ট করবে যাতে সাইজ ৫০MB-এর ভেতরে রাখা যায়
    """
    ydl_opts = {
        # প্রথমে চেষ্টা করবে 720p/480p দিয়ে সাইজ ৫০MB এর নিচে রাখার
        'format': 'bestvideo[height<=720][filesize<45M][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=720][filesize<48M]/best',
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
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.sanitize_info(info)

def fetch_direct_download_url(url: str):
    """৫০MB-এর বড় ভিডিওর ক্ষেত্রে ডাইরেক্ট ব্রাউজার লিংক বের করার মেথড"""
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url') or (info.get('requested_formats') and info['requested_formats'][0].get('url'))

# ---------------------------------------------------------------------------
# ৮. টেলিগ্রাম কমান্ড ও স্লাশ বাটন
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    BOT_STATS["unique_users"].add(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("📊 লাইভ ইউজার স্ট্যাটাস", callback_data="btn_stats"),
            InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
        ],
        [
            InlineKeyboardButton("💬 অ্যাডমিন যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
        ]
    ]
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন প্যানেল", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"স্বাগতম, *{user.first_name}*! 🚀🤖\n\n"
        "আমি আপনার **এআই-পাওয়ার্ড সুপারহিরো ডাউনলোডার বট**!\n\n"
        "💡 কোনো ঝামেলা ছাড়াই চ্যাটে ফেসবুক, ইনস্টাগ্রাম, ইউটিউব বা টিকটকের লিংক ছুড়ে মারুন—বাকি কাজ আমার!\n\n"
        "👇 অপশন দেখতে মেনু বা বাম পাশের **[/] স্লাশ বাটন** চাপুন:"
    )
    
    try:
        await update.message.delete()
    except Exception:
        pass

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = len(BOT_STATS["unique_users"])
    total_dl = BOT_STATS["total_downloads"]
    text = (
        "📊 **বটের বর্তমান পরিসংখ্যান:**\n\n"
        f"👥 মোট ব্যবহারকারী: `{user_count} জন`\n"
        f"📥 সফল ডাউনলোড: `{total_dl} টি ভিডিও`\n\n"
        "🟢 এআই সার্ভার: সুপারফাস্ট ও ফুল চার্জড!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💬 সরাসরি ইনবক্স করুন", url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(
        "👨‍💻 **অ্যাডমিন যোগাযোগ:**\n\nযেকোনো প্রশ্ন, স্পেশাল রিকোয়েস্ট বা মতামতের জন্য সরাসরি ইনবক্স করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def set_slash_commands(application):
    commands = [
        BotCommand("start", "🚀 বট শুরু বা রিফ্রেশ করুন"),
        BotCommand("stats", "📊 কত মানুষ ব্যবহার করছে দেখুন"),
        BotCommand("admin", "👨‍💻 অ্যাডমিনের সাথে যোগাযোগ করুন")
    ]
    await application.bot.set_my_commands(commands)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    if query.data == "btn_stats":
        user_count = len(BOT_STATS["unique_users"])
        total_dl = BOT_STATS["total_downloads"]
        text = (
            "📊 **বটের লাইভ পরিসংখ্যান:**\n\n"
            f"👥 মোট ব্যবহারকারী: `{user_count} জন`\n"
            f"📥 মোট ডাউনলোড: `{total_dl} টি`\n\n"
            "🟢 সার্ভার স্ট্যাটাস: Online & 100% Active"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 *সহজ ব্যবহারবিধি:*\n\n"
            "১. Facebook, YouTube, Insta, TikTok-এর যেকোনো পাবলিক ভিডিওর লিংক পাঠান।\n"
            "২. ৫০MB-এর ভেতরের ভিডিও সরাসরি টেলিগ্রাম চ্যাটে পাবেন।\n"
            "৩. ৫০MB-এর বড় ভিডিও হলে বট সাথে সাথে ডাইরেক্ট ডাউনলোড বাটন দিয়ে দেবে!"
        )
        await query.edit_message_text(guide_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            stats_text = (
                f"🛠️ *অ্যাডমিন প্যানেল:*\n\n"
                f"👥 মোট ইউজার: `{len(BOT_STATS['unique_users'])} জন`\n"
                f"📥 মোট ডাউনলোড: `{BOT_STATS['total_downloads']} টি`\n"
                f"🧠 Groq AI মোড: {'সক্রিয় (Active)' if groq_client else 'অফলাইন'}"
            )
            await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))
        else:
            await query.answer("আপনার এই এক্সেস নেই!", show_alert=True)

    elif query.data == "back_home":
        keyboard = [
            [
                InlineKeyboardButton("📊 লাইভ ইউজার স্ট্যাটাস", callback_data="btn_stats"),
                InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
            ],
            [
                InlineKeyboardButton("💬 অ্যাডমিন যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
            ]
        ]
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন প্যানেল", callback_data="admin_panel")])
        await query.edit_message_text("স্বাগতম! সরাসরি যেকোনো ভিডিওর লিংক পাঠান অথবা অপশন দেখুন:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ---------------------------------------------------------------------------
# ৯. মেসেজ হ্যান্ডলার ও ভিডিও ডেলিভারি লজিক
# ---------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    # লিংক শনাক্তকরণ
    urls = re.findall(r'(https?://\S+)', raw_text)
    if not urls:
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ ভাইরে ভাই, আবলতাবল কথা না লিখে কাজের মতো ফেসবুক, ইউটিউব বা ইনস্টাগ্রামের লিংক পাঠান! 😂"
        )
        if context.job_queue:
            context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 4)
        return

    try:
        await update.message.delete()
    except Exception:
        pass

    target_url = urls[0]

    # Groq AI দিয়ে র্যান্ডম মজাদার ওয়েটিং টেক্সট
    loop = asyncio.get_running_loop()
    ai_waiting_text = await loop.run_in_executor(None, generate_ai_waiting_text)
    msg = await context.bot.send_message(chat_id=chat_id, text=ai_waiting_text)

    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        resolved_url = await loop.run_in_executor(None, clean_and_resolve_url, target_url)

        download_success = False
        caught_error = ""

        try:
            await loop.run_in_executor(None, download_media_smart, resolved_url, output_template)
            download_success = True
        except Exception as e:
            caught_error = str(e)
            logger.warning(f"Download error: {caught_error}")

        downloaded_files = glob.glob(f"{temp_dir}/*")

        # ১. ফাইল ৫০MB-এর নিচে হলে সরাসরি চ্যাটে আপলোড
        if download_success and downloaded_files:
            video_path = downloaded_files[0]
            file_size = os.path.getsize(video_path)

            if file_size <= MAX_TELEGRAM_UPLOAD_BYTES:
                BOT_STATS["total_downloads"] += 1
                with open(video_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=chat_id, 
                        video=video_file, 
                        caption=f"🎬 বসের ভিডিও সফলভাবে হাজির!\n📥 Powered by @{ADMIN_USERNAME}",
                        supports_streaming=True,
                        read_timeout=300,
                        write_timeout=300
                    )
                await msg.delete()
                return

        # ২. ফাইল যদি ৫০MB-এর বড় হয়: ডাইরেক্ট ডাউনলোড বাটন উপহার দেওয়া
        direct_url = await loop.run_in_executor(None, fetch_direct_download_url, resolved_url)
        if direct_url:
            BOT_STATS["total_downloads"] += 1
            kb = [[InlineKeyboardButton("📥 সরাসরি ফুল এইচডি ডাউনলোড করুন", url=direct_url)]]
            await msg.edit_text(
                "😱 **বাপরে বাপ! ভিডিওর সাইজ তো বিশাল (৫০ মেগাবাইটের বেশি)!**\n\n"
                "টেলিগ্রামের নিজস্ব নিয়মে ৫০MB-এর বড় ভিডিও চ্যাটে পাঠানো নিষেধ। তবে কোনো টেনশন নাই বস! "
                "নিচের বাটনে চাপ দিয়ে রকেটের স্পিডে আপনার ফোনে সরাসরি নামিয়ে নিন: 👇",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # ৩. কোনোভাবেই নামানো না গেলে: Groq AI এররটি ফানিভাবে বুঝিয়ে বলবে
        ai_error_msg = await loop.run_in_executor(None, generate_ai_error_explanation, caught_error)
        await msg.edit_text(ai_error_msg)

    except Exception as exc:
        logger.error(f"Execution Error: {exc}", exc_info=True)
        await msg.edit_text("⚠️ উফ! সার্ভারের ফিউজ উড়ে যাওয়ার অবস্থা! একটু পর আবার লিংকটা পাঠান তো দেখি।")

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# ১০. মেইন বুটস্ট্র্যাপ
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    threading.Thread(target=run_http_server, daemon=True).start()

    custom_request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=60.0
    )

    application = ApplicationBuilder().token(TOKEN).request(custom_request).post_init(set_slash_commands).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("AI Universal Video Downloader Bot is fully running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()