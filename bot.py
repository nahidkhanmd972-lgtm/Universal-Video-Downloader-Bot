import os
import random
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# বটের টোকেন এনভায়রনমেন্ট থেকে রিড করা
TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set()
}

# ইউজারদের হাসানোর জন্য পেট ফাটানো হাসির ও মজাদার ওয়েটিং মেসেজসমূহ
FUNNY_WAITING_MESSAGES = [
    "☕ এক কাপ চা খান আর একটু হাসুন! ভিডিও নামাতে গিয়ে সার্ভারের তো প্রায় ঘাম ছুটে গেছে...",
    "🏃‍♂️ ধরো ধরো! ভিডিও চোর লিংক নিয়ে রকেটের বেগে দৌড় দিয়েছে আপনার দিকে...",
    "🧙‍♂️ জাদুকরী মন্ত্র পড়া চলছে: আব্রাবি-কা-ডাব্রা, ভিডিও হয়ে যা উধাও থেকে সরাসরি এখানে!",
    "🍔 একটা আস্ত বার্গার চিবিয়ে শেষ করতে যতোক্ষণ লাগবে, তার আগেই ভিডিও হাজির হচ্ছে...",
    "🚀 ইলন মাস্কের রকেটও লজ্জা পাবে ভাই, একটু ফুরফুরে মেجাজে অপেক্ষা করুন...",
    "🐒 বানর নাচ দেখতে দেখতেই ভিডিও ডাউনলোড হয়ে যাবে, একটু চিল করুন বস!",
    "🐢 কচ্ছপ নয় ভাই, এবার একদম চিতাবাঘের গতিতে ভিডিও ফেচ করা হচ্ছে...",
    "😎 আপনার লিংকের আকর্ষণে সার্ভারের নাকি ক্রাশ খাওয়ার অবস্থা, একটু ধৈর্য ধরুন!",
    "🔮 জাদুর হাড়ি থেকে ভিডিও বের করা হচ্ছে, একটু বাতাস লাগুক ফাইলটায়...",
    "💡 হুট করে কারেন্ট চলে যাওয়ার আগে ভিডিও নামিয়ে ফেলছি, সাথে থাকুন!"
]

# ==========================================
# yt-dlp ভিত্তিক শক্তিশালী ভিডিও ডাউনলোডার লজিক
# ==========================================

def fetch_video_ytdlp(url: str):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # ডাইরেক্ট ভিডিও স্ট্রিম বা ডাউনলোড ইউআরএল রিটার্ন করা
            if 'url' in info:
                return info['url']
            elif 'requested_formats' in info:
                return info['requested_formats'][0]['url']
    except Exception as e:
        print(f"yt-dlp Error: {e}")
    return None

async def fetch_universal_video(url: str):
    # প্রথমে ডেডিকেটেড yt-dlp প্রযুক্তি দিয়ে ট্রাই করা (Facebook, Insta, YouTube, TikTok সবকিছুর জন্য)
    video_url = fetch_video_ytdlp(url)
    if video_url:
        return video_url

    # যদি কোনো কারণে yt-dlp ফেইল করে, তবে টিকটকের জন্য ব্যাকআপ এপিআই
    if "tiktok.com" in url or "douyin.com" in url or "vm.tiktok.com" in url:
        try:
            res = requests.get(f"https://tikwm.com/api/?url={url}", timeout=6).json()
            if res.get("code") == 0:
                return res["data"]["play"]
        except:
            pass

    return None

# ==========================================
# টেলিগ্রাম ইন্টারফেস ও ইনফো মেনু সিস্টেম
# ==========================================

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
        "🤖 এটি আপনার একদম **উন্মুক্ত ও সুপার-পাওয়ারফুল ইউনিভার্সাল ভিডিও ডাউনলোডার বট**!\n\n"
        "💡 **কোনো বাটন বা ঝামেলা নেই!** সরাসরি চ্যাটে Facebook Reels, Instagram Reels, YouTube Shorts বা TikTok-এর যেকোনো লিংক পেস্ট করে পাঠিয়ে দিন!\n\n"
        "👇 নিচের মেনু থেকে বটের তথ্য বা সাহায্য দেখতে পারেন:"
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
    
    if query.data == "my_profile":
        profile_text = (
            f"👤 *ইউজার প্রফাইল:*\n\n"
            f"• নাম: {user.first_name}\n"
            f"• আইডি: `{user.id}`\n\n"
            f"🟢 ডাউনলোডার বট সম্পূর্ণ উন্মুক্ত ও সচল আছে।"
        )
        await query.edit_message_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 *ব্যবহারবিধি:*\n\n"
            "১. কোনো কিছু সিলেক্ট করা লাগবে না! সরাসরি যেকোনো ভিডিওর লিংক চ্যাটে পেস্ট করুন।\n"
            "২. ফেসবুক, ইনস্টাগ্রাম, ইউটিউব শর্টস, টিকটক—সব লিংক সরাসরি কাজ করবে।\n"
            "৩. চ্যাট বক্স পরিষ্কার রাখতে আপনার পাঠানো লিংক সাথে সাথে ভ্যানিশ হয়ে যাবে।"
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
            parse_mode="Markdown"
        )

# ==========================================
# ডিরেক্ট লিংক হ্যান্ডলার ও ফানি প্রসেসিং সিস্টেম
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    chat_id = update.effective_chat.id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    # ইউজারের পাঠানো টেক্সট বা লিংক সাথে সাথে ডিলিট করে দেওয়া (চ্যাট বক্স পরিষ্কার রাখার জন্য)
    try:
        await update.message.delete()
    except Exception:
        pass

    # যদি লেখাটি কোনো লিংক না হয়
    if not (text.startswith("http://") or text.startswith("https://")):
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ ভাইরে ভাই, আবলতাবল কথা না লিখে একটা কাজের মতো ফেসবুক, ইনস্টাগ্রাম বা ইউটিউবের লিংক পাঠান! 😂"
        )
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 
            4
        )
        return

    # র্যান্ডম ফানি ওয়েটিং মেসেজ পাঠানো
    random_funny_text = random.choice(FUNNY_WAITING_MESSAGES)
    msg = await context.bot.send_message(chat_id=chat_id, text=random_funny_text)
    
    try:
        direct_video_url = await fetch_universal_video(text)

        if direct_video_url:
            BOT_STATS["total_downloads"] += 1
            
            # ডাউনলোড করা ভিডিওটি পাঠানো হবে (চ্যাটে স্থায়ী থাকবে)
            await context.bot.send_video(
                chat_id=chat_id, 
                video=direct_video_url, 
                caption=f"✨ বসের ভিডিও সফলভাবে হাজির!\n📥 Powered by @{ADMIN_USERNAME}"
            )
            # ফানি প্রসেসিং মেসেজটি ডিলিট করে দেওয়া
            await msg.delete()
        else:
            await msg.edit_text("❌ এই লিংক থেকে ভিডিও নামানো গেল না বস! হয়তো ভিডিওটি প্রাইভেট করা আছে বা লিংক ভুল। পাবলিক লিংক দিয়ে আবার চেষ্টা করুন।")
            context.job_queue.run_once(
                lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id), 
                5
            )
            
    except Exception as e:
        await msg.edit_text("⚠️ উফ! সার্ভারে একটু খিকটু হয়েছে। আবার একটু কষ্ট করে লিংকটা পাঠান তো দেখি।")
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
    
    print("Advanced yt-dlp Video Downloader Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()