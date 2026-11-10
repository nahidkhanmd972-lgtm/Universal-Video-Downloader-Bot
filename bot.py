import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভ্যারিয়েবল থেকে টোকেন এবং ইউজারনেম রিড করা (গিটহাবের জন্য নিরাপদ)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "NahidDevOfficial")

# Start Command & Main Menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"👋 Hello **{user.first_name}**!\n\n"
        "🚀 **Welcome to your All-in-One Video Downloader Bot.**\n"
        "You can download videos effortlessly from **YouTube, TikTok, Facebook, Instagram, Twitter/X**, and more!\n\n"
        "👇 *Please choose an option below to get started:*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📥 How to Download", callback_data="menu_download")],
        [InlineKeyboardButton("🌐 Supported Platforms", callback_data="menu_platforms"),
         InlineKeyboardButton("ℹ️ Help & Guide", callback_data="menu_help")],
        [InlineKeyboardButton("👨‍💻 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# Button Callback Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "menu_download":
        text = (
            "📥 **How to Download:**\n\n"
            "Simply send me a direct video link from any supported platform, and I will instantly process and send the video file to you!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Home", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "menu_platforms":
        text = (
            "🌐 **Fully Supported Platforms:**\n\n"
            "• **YouTube** (Videos, Shorts & Playlists)\n"
            "• **TikTok** (Without Watermark)\n"
            "• **Facebook** (Public Videos & Reels)\n"
            "• **Instagram** (Reels, Posts & Stories)\n"
            "• **Twitter / X** (Media & Videos)\n\n"
            "Just paste any link from these platforms in the chat!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Home", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "menu_help":
        text = (
            "ℹ️ **Help & Information:**\n\n"
            "1. Send a valid video URL.\n"
            "2. Wait a few seconds while yt-dlp extracts the media.\n"
            "3. Receive your video file directly in chat.\n\n"
            "If you encounter any issues, click below to contact the admin."
        )
        keyboard = [
            [InlineKeyboardButton("👨‍💻 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="menu_home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "menu_home":
        await start(update, context)

# Video Downloader Engine
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith("http"):
        await update.message.reply_text("⚠️ Please send a valid video URL starting with http:// or https://")
        return

    status_message = await update.message.reply_text("⏳ *Processing your link... Fetching video from platform.*", parse_mode="Markdown")
    
    output_template = "downloaded_video.mp4"
    
    if os.path.exists(output_template):
        os.remove(output_template)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'noplaylist': False,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await status_message.edit_text("⬇️ *Downloading video... Please wait.*", parse_mode="Markdown")
            ydl.download([url])
            
        if os.path.exists(output_template):
            await status_message.edit_text("📤 *Uploading video to Telegram...*", parse_mode="Markdown")
            with open(output_template, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file, 
                    caption="✅ *Downloaded successfully via your Bot!*", 
                    parse_mode="Markdown"
                )
            await status_message.delete()
        else:
            await status_message.edit_text("❌ Failed to download the video. The file could not be processed.")
            
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        error_msg = str(e)
        if "File is too large" in error_msg:
            await status_message.edit_text("❌ *Error:* The video file size exceeds Telegram's 50MB limit.")
        else:
            await status_message.edit_text(f"❌ *An error occurred:* `{error_msg[:120]}`", parse_mode="Markdown")
        
    finally:
        if os.path.exists(output_template):
            os.remove(output_template)

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN environment variable not found!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via Docker...")
    application.run_polling()

if __name__ == "__main__":
    main()
          
