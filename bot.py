import os
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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
# ১. রুট ছাড়া সার্ভারে FFmpeg লোড করা (FB/Insta অডিও-ভিডিও মার্জ করার জন্য)
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
MAX_FILE_SIZE_BYTES = 48 * 1024 * 1024  # টেলিগ্রাম ফ্রি বটের জন্য ৪৮ এমবি লিমিট

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set()
}

# ---------------------------------------------------------------------------
# ৪. পেট ফাটানো হাসির ও মজাদার ওয়েটিং মেসেজসমূহ (প্রতিবার র্যান্ডম আসবে)
# ---------------------------------------------------------------------------
FUNNY_WAITING_MESSAGES = [
    "☕ এক কাপ চা খান আর একটু হাসুন! ভিডিও নামাতে গিয়ে সার্ভারের তো প্রায় ঘাম ছুটে গেছে...",
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
# ৫. Render Free Web Service পোর্ট ওপেন রাখা (সার্ভার স্লিপ আটকাবে)
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
# ৬. আসল ভিডিও ডাউনলোডার ইঞ্জিন (FB, Insta, TikTok, YouTube 100% Working)
# ---------------------------------------------------------------------------
def download_video_locally(url: str, output_path: str):
    """
    yt-dlp দিয়ে ভিডিও + অডিও সরাসরি লোকাল মেমরিতে ডাউনলোড এবং মার্জ করবে
    """
    ydl_opts = {
        'format': 'bestvideo[filesize<42M][ext=mp4]+bestaudio[ext=m4a]/best[filesize<48M][ext=mp4]/best[filesize<48M]/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
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

def download_tiktok_backup(url: str, save_path: str) -> bool:
    """
    টিকটকের জন্য স্পেশাল ব্যাকআপ মেথড (যাতে কখনো ফেইল না করে)
    """
    try:
        res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10).json()
        if res.get("code") == 0:
            video_url = res["data"]["play"]
            r = requests.get(video_url, stream=True, timeout=20)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# ৭. টেলিগ্রাম মেনু ও স্টার্ট হ্যান্ডলার
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    BOT_STATS["unique_users"].add(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("👤 আমার প্রফাইল", callback_data="my_profile"),
            InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
        ],
        [
            InlineKeyboardButton("💬 অ্যাডমিন যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
        ]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন স্ট্যাটস প্যানেল", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"স্বাগতম, *{user.first_name}*! 🚀\n\n"
        "🤖 এটি আপনার **উন্মুক্ত ও সুপার-ফাস্ট ইউনিভার্সাল ভিডিও ডাউনলোডার বট**!\n\n"
        "💡 **কোনো জটিলতা নেই!** সরাসরি চ্যাটে Facebook Reels/Video, Instagram Reels, TikTok বা YouTube Shorts-এর যেকোনো লিংক পাঠিয়ে দিন!\n\n"
        "👇 নিচের মেনু থেকে প্রয়োজনীয় অপশন দেখতে পারেন:"
    )
    
    try:
        await update.message.delete()
    except Exception:
        pass

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    if query.data == "my_profile":
        profile_text = (
            f"👤 *ইউজার প্রফাইল:*\n\n"
            f"• নাম: {user.first_name}\n"
            f"• আইডি: `{user.id}`\n\n"
            f"🟢 ডাউনলোডার বট সম্পূর্ণ উন্মুক্ত ও সচল আছে।"
        )
        await query.edit_message_text(
            profile_text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]])
        )

    elif query.data == "help_guide":
        guide_text = (
            "📌 *ব্যবহারবিধি:*\n\n"
            "১. কোনো কিছু সিলেক্ট করতে হবে না! সরাসরি ভিডিওর লিংক চ্যাটে পেস্ট করুন।\n"
            "২. ফেসবুক রিলস, ইনস্টাগ্রাম রিলস, টিকটক ও ইউটিউব শর্টস ১০০% সাপোর্ট করবে।\n"
            "৩. প্রাইভেট গ্রুপের ভিডিও ছাড়া যেকোনো পাবলিক ভিডিও নামানো যাবে।"
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
                InlineKeyboardButton("👤 আমার প্রফাইল", callback_data="my_profile"),
                InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
            ],
            [
                InlineKeyboardButton("💬 অ্যাডমিন যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
            ]
        ]
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন স্ট্যাটস প্যানেল", callback_data="admin_panel")])
        
        await query.edit_message_text(
            "স্বাগতম! সরাসরি ভিডিওর লিংক পাঠান অথবা নিচের অপশনগুলো দেখুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

# ---------------------------------------------------------------------------
# ৮. মেসেজ হ্যান্ডলার ও ফানি প্রসেসিং সিস্টেম
# ---------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    # ইউজারের পাঠানো লিংক ডিলিট করে চ্যাট পরিষ্কার রাখা
    try:
        await update.message.delete()
    except Exception:
        pass

    # লিংক ভ্যালিডেশন
    if not (text.startswith("http://") or text.startswith("https://")):
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ ভাইরে ভাই, আবলতাবল কথা না লিখে কাজের মতো ফেসবুক, ইনস্টাগ্রাম বা টিকটকের লিংক পাঠান! 😂"
        )
        if context.job_queue:
            context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 4)
        return

    # প্রতিবার র্যান্ডম ফানি ওয়েটিং মেসেজ পাঠানো
    random_funny_text = random.choice(FUNNY_WAITING_MESSAGES)
    msg = await context.bot.send_message(chat_id=chat_id, text=random_funny_text)

    # ইউনিক ফোল্ডার তৈরি (মাল্টি-ইউজার সেফটি)
    job_id = uuid.uuid4().hex
    temp_dir = Path(f"/tmp/ytdl_{job_id}")
    output_template = str(temp_dir / "%(id)s.%(ext)s")

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

        loop = asyncio.get_running_loop()
        download_success = False

        # ১. মূল yt-dlp দিয়ে ডাউনলোড চেষ্টা (FB, Insta, YouTube, TikTok)
        try:
            await loop.run_in_executor(None, download_video_locally, text, output_template)
            download_success = True
        except Exception as e:
            logger.warning(f"yt-dlp primary error: {e}")

        # ২. যদি টিকটক হয় এবং yt-dlp ফেইল করে, তবে সেকেন্ডারি ব্যাকআপ ট্রাই
        if not download_success and ("tiktok.com" in text or "douyin.com" in text):
            tiktok_file = str(temp_dir / "tiktok_video.mp4")
            download_success = await loop.run_in_executor(None, download_tiktok_backup, text, tiktok_file)

        # ডাউনলোড করা ভিডিও ফাইল খোঁজা
        downloaded_files = glob.glob(f"{temp_dir}/*")

        if download_success and downloaded_files:
            video_path = downloaded_files[0]
            file_size = os.path.getsize(video_path)

            if file_size > MAX_FILE_SIZE_BYTES:
                await msg.edit_text("❌ ফাইলটি অনেক বড় (৫০ মেগাবাইটের বেশি)! টেলিগ্রামের নিয়মে এটি পাঠানো সম্ভব নয় বস।")
                return

            BOT_STATS["total_downloads"] += 1

            # আসল ভিডিও ফাইলটি সরাসরি টেলিগ্রামে পাঠানো
            with open(video_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id, 
                    video=video_file, 
                    caption=f"✨ বসের ভিডিও সফলভাবে হাজির!\n📥 Powered by @{ADMIN_USERNAME}",
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300
                )
            
            # ফানি মেসেজ ডিলিট করা
            await msg.delete()

        else:
            await msg.edit_text("❌ এই লিংক থেকে ভিডিও নামানো গেল না বস! হয়তো ভিডিওটি প্রাইভেট (Private) করা বা লিঙ্ক ভুল। পাবলিক কোনো লিংক দিয়ে আবার চেষ্টা করুন!")

    except Exception as exc:
        logger.error(f"Error handling request: {exc}", exc_info=True)
        await msg.edit_text("⚠️ উফ! সার্ভারে একটু খিকটু হয়েছে। আবার একটু কষ্ট করে লিংকটা পাঠান তো দেখি।")

    finally:
        # প্রসেস শেষ হলে সাথে সাথে ফাইল ডিলিট (সার্ভার ডিস্ক ক্লিন রাখা)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# ৯. মেইন ফাংশন
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    # Render কিপ-অ্যালাইভ সার্ভার থ্রেড চালু
    threading.Thread(target=run_http_server, daemon=True).start()

    # হাই-টাইমআউট রিকোয়েস্ট (বড় ভিডিও আপলোডে যেন টাইমআউট না হয়)
    custom_request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=60.0
    )

    application = ApplicationBuilder().token(TOKEN).request(custom_request).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Universal Video Downloader Bot is running smoothly...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()