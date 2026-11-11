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

# Groq AI প্যাকেজ চেক
try:
    from groq import Groq
except ImportError:
    Groq = None

# FFmpeg লোড করা
try:
    static_ffmpeg.add_paths()
except Exception:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ও কনফিগারেশন
TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"

# টেলিগ্রাম আপলোড লিমিট (৪৮ MB)
MAX_TELEGRAM_UPLOAD_LIMIT = 48 * 1024 * 1024

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set()
}

groq_client = None
if Groq and GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logger.warning(f"Groq Init Warning: {e}")

BACKUP_FUNNY_MESSAGES = [
    "☕ এক কাপ চা খেয়ে একটু হাসুন! ভিডিও নামাতে গিয়ে সার্ভারের তো প্রায় ঘাম ছুটে গেছে...",
    "🏃‍♂️ ধরো ধরো! ভিডিও চোর লিংক নিয়ে রকেটের বেগে দৌড় দিয়েছে আপনার দিকে...",
    "🧙‍♂️ জাদুকরী মন্ত্র পড়া চলছে: আব্রাবি-কা-ডাব্রা, ভিডিও হয়ে যা উধাও থেকে সরাসরি এখানে!",
    "🍔 একটা আস্ত বার্গার চিবিয়ে শেষ করতে যতোক্ষণ লাগবে, তার আগেই ভিডিও হাজির হচ্ছে...",
    "🚀 ইলন মাস্কের রকেটও লজ্জা পাবে ভাই, একটু ফুরফুরে মেজাজে অপেক্ষা করুন...",
    "🐒 বানর নাচ দেখতে দেখতেই ভিডিও ডাউনলোড হয়ে যাবে, একটু চিল করুন বস!",
    "💡 হুট করে কারেন্ট চলে যাওয়ার আগেই ভিডিও নামিয়ে ফেলছি, সাথে থাকুন!"
]

# ---------------------------------------------------------------------------
# Render Free Web Service পোর্ট কিপ-অ্যালাইভ
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - 24/7 Universal Downloader Active")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------------------------
# Groq AI জেনারেটর
# ---------------------------------------------------------------------------
def generate_ai_waiting_text() -> str:
    if not groq_client:
        return random.choice(BACKUP_FUNNY_MESSAGES)
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a witty, hilarious Bangladeshi bot. Generate a short 1-line funny Bengali waiting message. Max 15 words with emojis."
                },
                {"role": "user", "content": "Tell user to wait"}
            ],
            max_tokens=60,
            temperature=1.0
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return random.choice(BACKUP_FUNNY_MESSAGES)

def generate_ai_error_explanation(technical_error: str) -> str:
    if not groq_client:
        err = technical_error.lower()
        if "private" in err or "login" in err:
            return "❌ বস, ভিডিওটা প্রাইভেট করা বা মেম্বার-অনলি! পাবলিক কোনো ভিডিওর লিংক দিন, সাথে সাথে এনে দেব। 😂"
        return "❌ লিংকটায় কোনো ঘাপলা আছে বা ভিডিওটি মুছে ফেলা হয়েছে বস! অন্য কোনো লিংক দিয়ে ট্রাই করুন।"
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system", 
                    "content": "A video download failed. Explain in funny colloquial Bengali (ঢাকা ফানি টোন) why it failed based on the error. Max 2 sentences with emojis."
                },
                {"role": "user", "content": f"Error: {technical_error}"}
            ],
            max_tokens=100,
            temperature=0.8
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return "❌ এই লিংক থেকে ভিডিও নামানো গেল না বস! ভিডিওটি প্রাইভেট করা বা লিংকটি ভুল। পাবলিক লিংক দিন!"

# ---------------------------------------------------------------------------
# স্পেশাল ফেসবুক স্ক্র্যাপার (লগইন ট্র্যাপ বাইপাস)
# ---------------------------------------------------------------------------
def scrape_facebook_direct(url: str):
    """ফেসবুকের মোবাইল রেসপন্স থেকে সরাসরি আসল MP4 লিংক বের করে"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
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
    except Exception as e:
        logger.warning(f"Facebook scraper notice: {e}")
    return None

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

# ---------------------------------------------------------------------------
# yt-dlp ডাউনলোড লজিক
# ---------------------------------------------------------------------------
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
    """বড় ফাইলের জন্য সরাসরি ডাউনলোড লিংক নেওয়া"""
    ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url') or (info.get('requested_formats') and info['requested_formats'][0].get('url'))

def download_tiktok_api(url: str, save_path: str) -> bool:
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            v_url = res["data"]["play"]
            r = requests.get(v_url, stream=True, timeout=20)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# টেলিগ্রাম হ্যান্ডলারসমূহ
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
        "আমি আপনার **এআই ইউনিভার্সাল ভিডিও ডাউনলোডার বট**!\n\n"
        "💡 ফেসবুক, ইনস্টাগ্রাম, টিকটক বা ইউটিউব—যেকোনো ভিডিওর লিংক সরাসরি চ্যাটে পাঠিয়ে দিন!\n"
        "• ৫০MB-এর ভেতরের ভিডিও সরাসরি টেলিগ্রাম চ্যাটে পাবেন।\n"
        "• ৫০MB-এর বড় ভিডিও (১০০MB–৫০০MB) হলে সরাসরি হাই-স্পিড ডাউনলোড লিংক পাবেন!\n\n"
        "👇 মেনু বা বাম পাশের **[/] স্লাশ বাটন** চাপুন:"
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
        "🟢 সার্ভার স্ট্যাটাস: ২৪ ঘণ্টা সচল ও হাই-স্পিড!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💬 সরাসরি ইনবক্স করুন", url=f"https://t.me/{ADMIN_USERNAME}")]]
    await update.message.reply_text(
        "👨‍💻 **অ্যাডমিন যোগাযোগ:**\n\nযেকোনো প্রশ্ন বা মতামতের জন্য সরাসরি ইনবক্স করুন:",
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
        text = f"📊 **বটের লাইভ পরিসংখ্যান:**\n\n👥 মোট ব্যবহারকারী: `{user_count} জন`\n📥 মোট ডাউনলোড: `{total_dl} টি`\n🟢 সার্ভার: ১০০% অনলাইন"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = "📌 *সহজ ব্যবহারবিধি:*\n\n১. যেকোনো ভিডিওর লিংক চ্যাটে পাঠান।\n২. ৫০MB এর ভেতরের ভিডিও সরাসরি পাবেন।\n৩. ৫০MB-এর বড় ভিডিওর জন্য ডাইরেক্ট ডাউনলোড বাটন পেয়ে যাবেন।"
        await query.edit_message_text(guide_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            stats_text = f"🛠️ *অ্যাডমিন প্যানেল:*\n\n👥 মোট ইউজার: `{len(BOT_STATS['unique_users'])}`\n📥 মোট ডাউনলোড: `{BOT_STATS['total_downloads']}`\n🧠 Groq AI: {'সক্রিয়' if groq_client else 'অফলাইন'}"
            await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data="back_home")]]))
        else:
            await query.answer("আপনার এক্সেস নেই!", show_alert=True)

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
        await query.edit_message_text("স্বাগতম! সরাসরি ভিডিওর লিংক পাঠান:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ---------------------------------------------------------------------------
# মূল মেসেজ প্রসেসিং ইঞ্জিন
# ---------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    urls = re.findall(r'(https?://\S+)', raw_text)
    if not urls:
        warning_msg = await context.bot.send_message(chat_id=chat_id, text="⚠️ ভাইরে ভাই, আবলতাবল কথা না লিখে কাজের মতো ফেসবুক, ইউটিউব বা ইনস্টাগ্রামের লিংক পাঠান! 😂")
        if context.job_queue:
            context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 4)
        return

    try:
        await update.message.delete()
    except Exception:
        pass

    target_url = urls[0]
    loop = asyncio.get_running_loop()

    # ফানি ওয়েটিং মেসেজ
    ai_waiting_text = await loop.run_in_executor(None, generate_ai_waiting_text)
    msg = await context.bot.send_message(chat_id=chat_id, text=ai_waiting_text)

    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        resolved_url = await loop.run_in_executor(None, clean_url, target_url)

        download_success = False
        caught_error = ""
        direct_stream_url = None

        # ১. ফেসবুকের জন্য স্পেশাল ডাইরেক্ট স্ক্র্যাপার চেষ্টা
        if "facebook.com" in target_url or "fb.watch" in target_url:
            direct_fb = await loop.run_in_executor(None, scrape_facebook_direct, target_url)
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
                except Exception as e:
                    logger.warning(f"FB direct download error: {e}")

        # ২. সাধারণ ডাউনলোডার ইঞ্জিন (YouTube, Insta, TikTok, etc.)
        if not download_success:
            try:
                await loop.run_in_executor(None, download_ytdlp_smart, resolved_url, output_template)
                download_success = True
            except Exception as e:
                caught_error = str(e)
                logger.warning(f"yt-dlp error: {caught_error}")

        # ৩. টিকটকের ব্যাকআপ ট্রাই
        if not download_success and ("tiktok.com" in resolved_url or "douyin.com" in resolved_url):
            tiktok_file = str(temp_dir / "tiktok_video.mp4")
            download_success = await loop.run_in_executor(None, download_tiktok_api, resolved_url, tiktok_file)

        downloaded_files = glob.glob(f"{temp_dir}/*")

        # ফাইল ৫০MB-এর ভেতরে হলে সরাসরি টেলিগ্রামে আপলোড
        if download_success and downloaded_files:
            video_path = downloaded_files[0]
            file_size = os.path.getsize(video_path)

            if file_size <= MAX_TELEGRAM_UPLOAD_LIMIT:
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

        # ফাইল ৫০MB-এর বড় হলে (১০০MB–৫০০MB) সরাসরি ব্রাউজার ডাউনলোড বাটন দেওয়া
        if not direct_stream_url:
            direct_stream_url = await loop.run_in_executor(None, fetch_direct_stream_url, resolved_url)

        if direct_stream_url:
            BOT_STATS["total_downloads"] += 1
            kb = [[InlineKeyboardButton("📥 সরাসরি ফুল এইচডি ডাউনলোড করুন", url=direct_stream_url)]]
            await msg.edit_text(
                "😱 **বাপরে বাপ! ভিডিওর সাইজ তো বিশাল (৫০ মেগাবাইটের বেশি)!**\n\n"
                "টেলিগ্রাম ফ্রিতে ৫০MB-এর বড় ভিডিও চ্যাটে পাঠাতে দেয় না। তবে টেনশন নাই বস! "
                "নিচের বাটনে চাপ দিয়ে রকেটের স্পিডে আপনার ফোনে সরাসরি নামিয়ে নিন: 👇",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # কোনোভাবেই নামানো না গেলে Groq AI দিয়ে ব্যাখ্যা
        ai_error_msg = await loop.run_in_executor(None, generate_ai_error_explanation, caught_error)
        await msg.edit_text(ai_error_msg)

    except Exception as exc:
        logger.error(f"Execution Error: {exc}", exc_info=True)
        await msg.edit_text("⚠️ উফ! সার্ভারে একটু খিকটু হয়েছে। আবার একটু কষ্ট করে লিংকটা পাঠান তো দেখি।")

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# মেইন ফাংশন
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    # কিপ-অ্যালাইভ সার্ভার চালু
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

    print("AI Universal Video Downloader Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()