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
ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"
MAX_FILE_SIZE_BYTES = 48 * 1024 * 1024  # ৪৮ এমবি সেফ লিমিট

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set()
}

FUNNY_WAITING_MESSAGES = [
    "☕ এক কাপ চা খেয়ে একটু হাসুন! ভিডিও নামাতে গিয়ে সার্ভারের তো প্রায় ঘাম ছুটে গেছে...",
    "🏃‍♂️ ধরো ধরো! ভিডিও চোর লিংক নিয়ে রকেটের বেগে দৌড় দিয়েছে আপনার দিকে...",
    "🧙‍♂️ জাদুকরী মন্ত্র পড়া চলছে: আব্রাবি-কা-ডাব্রা, ভিডিও হয়ে যা উধাও থেকে সরাসরি এখানে!",
    "🍔 একটা আস্ত বার্গার চিবিয়ে শেষ করতে যতোক্ষণ লাগবে, তার আগেই ভিডিও হাজির হচ্ছে...",
    "🚀 ইলন মাস্কের রকেটও লজ্জা পাবে ভাই, একটু ফুরফুরে মেজাজে অপেক্ষা করুন...",
    "🐒 বানর নাচ দেখতে দেখতেই ভিডিও ডাউনলোড হয়ে যাবে, একটু চিল করুন বস!",
    "🐢 কচ্ছপ নয় ভাই, এবার একদম চিতাবাঘের গতিতে ভিডিও ফেচ করা হচ্ছে...",
    "😎 আপনার লিংকের আকর্ষণে সার্ভারের নাকি ক্রাশ খাওয়ার অবস্থা, একটু ধৈর্য ধরুন!",
    "🔮 জাদুর হাড়ি থেকে ভিডিও বের করা হচ্ছে, একটু বাতাস লাগুক ফাইলটায়...",
    "💡 হুট করে কারেন্ট চলে যাওয়ার আগেই ভিডিও নামিয়ে ফেলছি, সাথে থাকুন!",
    "🛸 এলিয়েনরা সিগন্যাল পাঠাচ্ছে, ভিডিও প্রায় রিসিভ হয়ে গেছে বস!",
    "🍳 ডিম পোচ হতে যতক্ষণ লাগে, তার আগেই ভিডিও হাজির হয়ে যাবে!",
    "💃 ভিডিওটা একটু সাজুগুজু করছে, মেকআপ শেষ হলেই ইনবক্সে ঢুকবে!"
]

# ---------------------------------------------------------------------------
# ৪. Render Free Web Service পোর্ট হ্যান্ডলার
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Universal Ultimate Bot is Running 24/7")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------------------------
# ৫. স্মার্ট লিঙ্ক ক্লিনার ও রিডাইরেক্ট রিভিলার
# ---------------------------------------------------------------------------
def clean_and_resolve_url(url: str) -> str:
    """
    ফেসবুক, ইউটিউব ও টিকটকের সব গার্বেজ প্যারামিটার মুছে আসল ভিডিও লিঙ্ক বের করে
    """
    clean_url = url.split("?")[0].strip()

    # ফেসবুক শর্ট বা শেয়ার লিঙ্ক হ্যান্ডলিং
    if "facebook.com/share" in url or "fb.watch" in url:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            resp = session.get(url, allow_redirects=True, timeout=8)
            resolved = resp.url.split("?")[0]
            if "facebook.com" in resolved and ("videos" in resolved or "reel" in resolved or "watch" in resolved):
                return resolved
        except Exception:
            pass

    return clean_url if clean_url.startswith("http") else url

# ---------------------------------------------------------------------------
# ৬. ডাউনলোডার ইঞ্জিন (Primary & Secondary Fallbacks)
# ---------------------------------------------------------------------------
def download_with_ytdlp(url: str, output_path: str):
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
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

def download_tiktok_fallback(url: str, save_path: str) -> bool:
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            video_url = res["data"]["play"]
            r = requests.get(video_url, stream=True, timeout=25)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# ৭. টেলিগ্রাম কমান্ড ও স্লাশ বাটন
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
        f"স্বাগতম, *{user.first_name}*! 🚀\n\n"
        "🤖 এটি আপনার **অল-ইন-ওয়ান সুপারফাস্ট ভিডিও ডাউনলোডার বট**!\n\n"
        "💡 **কোনো বাটন ছাড়া সরাসরি চ্যাটে যেকোনো ভিডিওর লিংক দিন:**\n"
        "• **Facebook** (Reels, Watch, Video)\n"
        "• **Instagram** (Reels, Posts)\n"
        "• **TikTok** (Watermark-free)\n"
        "• **YouTube** (Shorts & Standard Videos)\n"
        "• **Twitter/X, Pinterest, Threads** সহ যেকোনো সাইট!\n\n"
        "👇 মেনু বা বাম পাশের **[/] স্লাশ বাটন** চেপে অপশন দেখতে পারেন:"
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
        "🟢 সার্ভার স্ট্যাটাস: ২৪ ঘণ্টা সচল ও সুপারফাস্ট!"
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
        BotCommand("start", "🚀 বট শুরু / রিফ্রেশ করুন"),
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
        await query.edit_message_text(
            text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]])
        )

    elif query.data == "help_guide":
        guide_text = (
            "📌 *সহজ ব্যবহারবিধি:*\n\n"
            "১. Facebook, YouTube, Insta বা TikTok-এর যেকোনো ভিডিও লিংক সরাসরি চ্যাটে পাঠান।\n"
            "২. বট স্বয়ংক্রিয়ভাবে এইচডি কোয়ালিটিতে ভিডিও নামিয়ে পাঠিয়ে দেবে।\n"
            "৩. ভিডিও লিংকটি অবশ্যই পাবলিক হতে হবে।"
        )
        await query.edit_message_text(
            guide_text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]])
        )

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            stats_text = (
                f"🛠️ *অ্যাডমিন স্ট্যাটিস্টিক্স প্যানেল:*\n\n"
                f"👥 মোট ইউনিক ইউজার: `{len(BOT_STATS['unique_users'])} জন`\n"
                f"📥 মোট সফল ডাউনলোড: `{BOT_STATS['total_downloads']} টি`\n"
                f"🟢 সার্ভার স্ট্যাটাস: Online & 100% Active"
            )
            await query.edit_message_text(
                stats_text, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]])
            )
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
        
        await query.edit_message_text(
            "স্বাগতম! সরাসরি যেকোনো ভিডিওর লিংক পাঠান অথবা নিচের অপশনগুলো দেখুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

# ---------------------------------------------------------------------------
# ৮. মেসেজ হ্যান্ডলার (ডাউনলোড ও ডেলিভারি)
# ---------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    # লিংক ডিটেক্ট করা
    urls = re.findall(r'(https?://\S+)', raw_text)
    if not urls:
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ ভাইরে ভাই, আবলতাবল কথা না লিখে কাজের মতো ফেসবুক, ইউটিউব বা ইনস্টাগ্রামের লিংক পাঠান! 😂"
        )
        if context.job_queue:
            context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 4)
        return

    # ইউজার মেসেজ রিমুভ করে চ্যাট ফ্রেশ রাখা
    try:
        await update.message.delete()
    except Exception:
        pass

    target_url = urls[0]
    random_funny_text = random.choice(FUNNY_WAITING_MESSAGES)
    msg = await context.bot.send_message(chat_id=chat_id, text=random_funny_text)

    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        loop = asyncio.get_running_loop()

        # লিঙ্ক ক্লিন ও রিডাইরেক্ট রিজলভ করা
        resolved_url = await loop.run_in_executor(None, clean_and_resolve_url, target_url)

        download_success = False

        # ১. প্রাইমারি yt-dlp ডাউনলোড
        try:
            await loop.run_in_executor(None, download_with_ytdlp, resolved_url, output_template)
            download_success = True
        except Exception as e:
            logger.warning(f"Primary error on {resolved_url}: {e}")

        # ২. টিকটক অল্টারনেটিভ ফলব্যাক
        if not download_success and ("tiktok.com" in resolved_url or "douyin.com" in resolved_url):
            tiktok_file = str(temp_dir / "tiktok_video.mp4")
            download_success = await loop.run_in_executor(None, download_tiktok_fallback, resolved_url, tiktok_file)

        downloaded_files = glob.glob(f"{temp_dir}/*")

        if download_success and downloaded_files:
            video_path = downloaded_files[0]
            file_size = os.path.getsize(video_path)

            if file_size > MAX_FILE_SIZE_BYTES:
                await msg.edit_text("❌ ফাইলটি অনেক বড় (৫০ মেগাবাইটের বেশি)! টেলিগ্রামের ফ্রিতে ৫০MB-এর বেশি ফাইল আপলোড করা যায় না বস।")
                return

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

        else:
            await msg.edit_text("❌ এই লিংক থেকে ভিডিও নামানো গেল না বস! হয়তো ভিডিওটি প্রাইভেট (Private) করা বা লিঙ্ক ভুল। পাবলিক কোনো লিংক দিয়ে আবার চেষ্টা করুন!")

    except Exception as exc:
        logger.error(f"Error: {exc}", exc_info=True)
        await msg.edit_text("⚠️ উফ! সার্ভারে একটু খিকটু হয়েছে। আবার একটু কষ্ট করে লিংকটা পাঠান তো দেখি।")

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# ৯. মেইন ফাংশন
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

    print("Universal Ultimate Video Downloader Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()