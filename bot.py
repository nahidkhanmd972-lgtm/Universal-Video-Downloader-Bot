import os
import random
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# বটের টোকেন এবং আপনার RapidAPI Key
TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = "4c9f903088mshf63f5b4780b69e2p1a9597jsna0c90125621d"

ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set()
}

WAITING_MESSAGES = [
    "☕ এক কাপ চা খান, ভিডিও নামছে...",
    "🚀 রকেটের গতিতে লিংক থেকে ভিডিও ফেচ করা হচ্ছে...",
    "⏳ একটু ধৈর্য ধরুন, ফাইল প্রসেসিং চলছে...",
    "🎬 আপনার ভিডিও প্রস্তুত করা হচ্ছে, ম্যাজিক দেখুন...",
    "🔥 দ্রুত সার্ভার থেকে ভিডিও নামানো হচ্ছে, সাথে থাকুন..."
]

# ==========================================
# RapidAPI (`downloadMedia`) ও ব্যাকআপ লজিক
# ==========================================

async def fetch_universal_video(url: str):
    # ১. টিকটকের জন্য ডেডিকেটেড ব্যাকআপ
    if "tiktok.com" in url or "douyin.com" in url or "vm.tiktok.com" in url:
        try:
            res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=6).json()
            if res.get("code") == 0:
                return res["data"]["play"]
        except:
            pass

    # ২. আপনার সঠিক RapidAPI Host এবং Endpoint দিয়ে রিকোয়েস্ট পাঠানো
    rapid_api_url = "https://all-in-one-media-downloader-api.p.rapidapi.com/downloadMedia"
    rapid_api_host = "all-in-one-media-downloader-api.p.rapidapi.com"

    try:
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": rapid_api_host,
            "Content-Type": "application/json"
        }
        response = requests.get(rapid_api_url, headers=headers, params={"url": url}, timeout=10)
        res_data = response.json()
        
        # এপিআই রেসপন্স থেকে বিভিন্ন ফরম্যাটে ভিডিও লিংক খুঁজে বের করা
        if "data" in res_data:
            if isinstance(res_data["data"], str) and res_data["data"].startswith("http"):
                return res_data["data"]
            elif isinstance(res_data["data"], dict):
                for key in ["url", "link", "download", "play", "video"]:
                    if key in res_data["data"]:
                        return res_data["data"][key]
        
        if "url" in res_data:
            return res_data["url"]
        elif "link" in res_data:
            return res_data["link"]
        elif "medias" in res_data and len(res_data["medias"]) > 0:
            return res_data["medias"][0]["url"]
    except Exception as e:
        print(f"RapidAPI Error: {e}")

    # ৩. পাবলিক ব্যাকআপ এপিআই (Cobalt)
    public_apis = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json"
    ]
    for api in public_apis:
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            payload = {"url": url, "videoQuality": "max"}
            res = requests.post(api, json=payload, headers=headers, timeout=8).json()
            if "url" in res:
                return res["url"]
            elif "picker" in res:
                return res["picker"][0]["url"]
        except:
            continue

    return None

# ==========================================
# টেলিগ্রাম মেনু ও ইন্টারফেস সিস্টেম
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    BOT_STATS["unique_users"].add(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("📥 ভিডিও ডাউনলোডার (Universal)", callback_data="start_downloader")
        ],
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
        "🤖 এটি আপনার প্রিমিয়াম ও সুপার-পাওয়ারফুল ভিডিও ডাউনলোডার বট!\n"
        "YouTube, Facebook, TikTok বা Instagram—যেকোনো প্ল্যাটফর্মের ভিডিও নামাতে চাইলে নিচের বাটনটি ব্যবহার করুন।\n\n"
        "👇 অপশনটি সিলেক্ট করুন:"
    )
    
    try:
        await update.message.delete()
    except:
        pass

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    if query.data == "start_downloader":
        context.user_data['waiting_for_link'] = True
        await query.edit_message_text(
            "📥 *ভিডিও ডাউনলোডার মোড সচল আছে!*\n\nএখন YouTube, Facebook, TikTok বা Instagram-এর যেকোনো ভিডিও বা রিলসের লিংকটি সরাসরি চ্যাটে পেস্ট করে পাঠিয়ে দিন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "my_profile":
        profile_text = (
            f"👤 *ইউজার প্রফাইল:*\n\n"
            f"• নাম: {user.first_name}\n"
            f"• আইডি: `{user.id}`\n\n"
            f"🟢 ডাউনলোডার বট পুরোপুরি সচল ও নিরাপদ আছে।"
        )
        await query.edit_message_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 *ব্যবহারবিধি:*\n\n"
            "১. মেনু থেকে **ভিডিও ডাউনলোডার** বাটনে ক্লিক করুন।\n"
            "২. এরপর আপনার পছন্দের যেকোনো প্ল্যাটফর্মের লিংক পাঠান।\n"
            "৩. চ্যাট বক্স পরিষ্কার রাখতে আপনার লিংক ও প্রসেসিং টেক্সট স্বয়ংক্রিয়ভাবে মুছে যাবে।"
        )
        await query.edit_message_text(guide_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            stats_text = (
                f"🛠️ *অ্যাডমিন স্ট্যাটিস্টিক্স প্যানেল:*\n\n"
                f"👥 মোট ইউনিক ইউজার: `{len(BOT_STATS['unique_users'])} জন`\n"
                f"📥 মোট সফল ডাউনলোড: `{BOT_STATS['total_downloads']} টি`\n"
                f"🟢 সার্ভার স্ট্যাটাস: Online & Secured"
            )
            await query.edit_message_text(
                stats_text, 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))
        else:
            await query.answer("আপনার এই এক্সেস নেই!", show_alert=True)

    elif query.data == "back_home":
        context.user_data.pop('waiting_for_link', None)
        
        keyboard = [
            [
                InlineKeyboardButton("📥 ভিডিও ডাউনলোডার (Universal)", callback_data="start_downloader")
            ],
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
            "স্বাগতম! নিচের অপশনগুলো থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ==========================================
# মেসেজ ও অটো-ডিলিট হ্যান্ডলার
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    chat_id = update.effective_chat.id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    try:
        await update.message.delete()
    except Exception:
        pass

    if not context.user_data.get('waiting_for_link'):
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ দয়া করে প্রথমে মেনু থেকে **ভিডিও ডাউনলোডার** বাটনে ক্লিক করুন!"
        )
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 
            4
        )
        return

    if not (text.startswith("http://") or text.startswith("https://")):
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="❌ এটি কোনো সঠিক ভিডিওর লিংক নয়! দয়া করে সঠিক লিংক পাঠান।"
        )
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 
            4
        )
        return

    random_wait_text = random.choice(WAITING_MESSAGES)
    msg = await context.bot.send_message(chat_id=chat_id, text=random_wait_text)
    
    try:
        direct_video_url = await fetch_universal_video(text)
        context.user_data.pop('waiting_for_link', None)

        if direct_video_url:
            BOT_STATS["total_downloads"] += 1
            
            await context.bot.send_video(
                chat_id=chat_id, 
                video=direct_video_url, 
                caption=f"✨ সফলভাবে ভিডিও ডাউনলোড করা হয়েছে!\n📥 Powered by @{ADMIN_USERNAME}"
            )
            await msg.delete()
        else:
            await msg.edit_text("❌ এই লিংক থেকে ভিডিও সংগ্রহ করা সম্ভব হয়নি। পাবলিক ভিডিওর লিংক দিয়ে আবার চেষ্টা করুন।")
            context.job_queue.run_once(
                lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id), 
                5
            )
            
    except Exception as e:
        await msg.edit_text("⚠️ প্রসেসিংয়ের সময় সামান্য সমস্যা হয়েছে। আবার চেষ্টা করুন।")
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id), 
            4
        )
        print(f"Error: {e}")

def main():
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Universal RapidAPI Video Downloader Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()