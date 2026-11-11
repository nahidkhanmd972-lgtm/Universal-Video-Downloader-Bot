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

# এনভায়রনমেন্ট ভেরিয়েবল থেকে টোকেন ও এপিআই কি রিড করা
TOKEN = os.getenv("BOT_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")

ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"

BOT_STATS = {
    "total_downloads": 0,
    "unique_users": set(),
    "ai_chats": 0
}

WAITING_MESSAGES = [
    "☕ এক কাপ চা খান, ভিডিও নামছে...",
    "🚀 রকেটের গতিতে লিংক থেকে ভিডিও ফেচ করা হচ্ছে...",
    "⏳ একটু ধৈর্য ধরুন, ফাইল প্রসেসিং চলছে...",
    "🎬 আপনার ভিডিও প্রস্তুত করা হচ্ছে, ম্যাজিক দেখুন...",
    "🔥 দ্রুত সার্ভার থেকে ভিডিও নামানো হচ্ছে, সাথে থাকুন..."
]

# ==========================================
# ১. ভিডিও ডাউনলোডার লজিক
# ==========================================

async def fetch_tiktok(url: str):
    apis = [
        f"https://tikwm.com/api/?url={url}",
        "https://api.cobalt.tools/api/json"
    ]
    try:
        res = requests.get(apis[0], timeout=6).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except:
        pass
    try:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        res = requests.post(apis[1], json={"url": url}, headers=headers, timeout=6).json()
        if "url" in res:
            return res["url"]
    except:
        pass
    return None

async def fetch_facebook(url: str):
    apis = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json",
        "https://cobalt.api.rossix.net/api/json"
    ]
    for api in apis:
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

async def fetch_instagram(url: str):
    apis = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json"
    ]
    for api in apis:
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            payload = {"url": url}
            res = requests.post(api, json=payload, headers=headers, timeout=8).json()
            if "url" in res:
                return res["url"]
            elif "picker" in res:
                return res["picker"][0]["url"]
        except:
            continue
    return None

# ==========================================
# ২. Grok AI চ্যাট হ্যান্ডলার
# ==========================================

async def ask_grok_ai(user_text: str, user_name: str):
    if not GROK_API_KEY:
        return f"আরে {user_name}! আমি আপনার নিজস্ব ভিডিও ডাউনলোডার বট।"

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        f"You are the intelligent, witty, funny, and friendly AI core of a Telegram video downloader bot. "
        f"Your creator and owner is Nahid. "
        f"CRITICAL RULE: NEVER EVER mention that you are Grok, xAI, or trained by anyone else. If anyone asks who you are, "
        f"you must say you are 'নাহিদ এআই ভিডিও ডাউনলোডার বট' (Nahid AI Video Downloader Bot) created by Nahid. "
        f"The user you are chatting with is named {user_name}. "
        f"Keep the conversation lively, entertaining, playful, and prevent the user from getting bored. "
        f"Always reply in fluent Bengali language with a friendly and casual tone."
    )

    payload = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.8
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        res_data = response.json()
        if "choices" in res_data:
            return res_data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Grok API Error: {e}")
    
    return f"হা হা, {user_name}! আপনার কথা দারুণ লেগেছে। বলুন কীভাবে সাহায্য করতে পারি?"

# ==========================================
# ৩. টেলিগ্রাম ইন্টারফেস ও মেনু
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    BOT_STATS["unique_users"].add(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("🎵 TikTok Download", callback_data="mode_tiktok"),
            InlineKeyboardButton("📘 Facebook Download", callback_data="mode_fb")
        ],
        [
            InlineKeyboardButton("📸 Instagram Download", callback_data="mode_insta")
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
        keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন স্ট্যাটস ও প্যানেল", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"স্বাগতম, *{user.first_name}*! 🚀\n\n"
        "🤖 এটি আপনার প্রিমিয়াম মাল্টি-প্ল্যাটফর্ম ভিডিও ডাউনলোডার ও এআই চ্যাট বট!\n"
        "ভিডিও ডাউনলোড করতে চাইলে নিচের বাটন থেকে প্ল্যাটফর্ম সিলেক্ট করুন। আর এমনিতেই আড্ডা দিতে চাইলে সরাসরি কিছু লিখে পাঠান!\n\n"
        "👇 নিচে অপশনগুলো দেওয়া হলো:"
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
    
    if query.data == "mode_tiktok":
        context.user_data['download_mode'] = 'tiktok'
        await query.edit_message_text(
            "🎵 *TikTok মোড সিলেক্ট করা হয়েছে!*\n\nএখন আপনার টিকটক ভিডিওর লিংকটি সরাসরি চ্যাটে পেস্ট করে পাঠিয়ে দিন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "mode_fb":
        context.user_data['download_mode'] = 'facebook'
        await query.edit_message_text(
            "📘 *Facebook মোড সিলেক্ট করা হয়েছে!*\n\nএখন আপনার ফেসবুক ভিডিও বা রিলসের লিংকটি চ্যাটে পেস্ট করে পাঠিয়ে দিন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "mode_insta":
        context.user_data['download_mode'] = 'instagram'
        await query.edit_message_text(
            "📸 *Instagram মোড সিলেক্ট করা হয়েছে!*\n\nএখন আপনার ইনস্টাগ্রাম রিলস বা পোস্টের লিংকটি চ্যাটে পেস্ট করে পাঠিয়ে দিন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "my_profile":
        profile_text = (
            f"👤 *ইউজার প্রফাইল:*\n\n"
            f"• নাম: {user.first_name}\n"
            f"• আইডি: `{user.id}`\n\n"
            f"🟢 নাহিদ এআই ভিডিও ডাউনলোডার সিস্টেম সম্পূর্ণ সচল আছে।"
        )
        await query.edit_message_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 *ব্যবহারবিধি:*\n\n"
            "১. ভিডিও নামাতে চাইলে মেনু থেকে প্ল্যাটফর্ম সিলেক্ট করে লিংক পাঠান।\n"
            "২. বটের সাথে আড্ডা দিতে চাইলে যেকোনো সাধারণ মেসেজ পাঠান—আমি আপনার সাথে চ্যাট করব!\n"
            "৩. সার্ভার ও চ্যাট বক্স পরিষ্কার রাখতে ইউজারের পাঠানো টেক্সট ও এআই উত্তর স্বয়ংক্রিয়ভাবে মুছে ফেলা হয়।"
        )
        await query.edit_message_text(guide_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            stats_text = (
                f"🛠️ *অ্যাডমিন স্ট্যাটিস্টিক্স প্যানেল:*\n\n"
                f"👥 মোট ইউনিক ইউজার: `{len(BOT_STATS['unique_users'])} জন`\n"
                f"📥 মোট সফল ডাউনলোড: `{BOT_STATS['total_downloads']} টি`\n"
                f"💬 এআই চ্যাট রিকোয়েস্ট: `{BOT_STATS['ai_chats']} বার`\n"
                f"🟢 সার্ভার স্ট্যাটাস: Online & Secured"
            )
            await query.edit_message_text(
                stats_text, 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেনুতে ফিরে যান", callback_data="back_home")]]))
        else:
            await query.answer("আপনার এই এক্সেস নেই!", show_alert=True)

    elif query.data == "back_home":
        context.user_data.pop('download_mode', None)
        
        keyboard = [
            [
                InlineKeyboardButton("🎵 TikTok Download", callback_data="mode_tiktok"),
                InlineKeyboardButton("📘 Facebook Download", callback_data="mode_fb")
            ],
            [
                InlineKeyboardButton("📸 Instagram Download", callback_data="mode_insta")
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
            keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন স্ট্যাটস ও প্যানেল", callback_data="admin_panel")])
        
        await query.edit_message_text(
            "স্বাগতম! নিচের অপশনগুলো থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ==========================================
# ৪. অটো-ডিলিট মেসেজ ও লিংক হ্যান্ডলার
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    user = update.effective_user

    BOT_STATS["unique_users"].add(user.id)

    # ইউজার মেসেজটি সাথে সাথে ডিলিট করে দেওয়া
    try:
        await update.message.delete()
    except Exception:
        pass

    # এআই চ্যাট প্রসেসিং (যদি লিংক না হয়)
    if not (text.startswith("http://") or text.startswith("https://")):
        BOT_STATS["ai_chats"] += 1
        typing_msg = await context.bot.send_message(chat_id=chat_id, text="🤖 ভাবছি...")
        
        ai_reply = await ask_grok_ai(text, user.first_name)
        
        # এআই উত্তর আপডেট করা
        await typing_msg.edit_text(ai_reply)
        
        # এআই-এর উত্তরটি ৬ সেকেন্ড পর স্বয়ংক্রিয়ভাবে ডিলিট হয়ে যাবে
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=typing_msg.message_id), 
            6
        )
        return

    current_mode = context.user_data.get('download_mode')
    if not current_mode:
        warning_msg = await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ প্রথমে মেনু থেকে প্ল্যাটফর্ম (TikTok/Facebook/Instagram) সিলেক্ট করুন!"
        )
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=warning_msg.message_id), 
            5
        )
        return

    random_wait_text = random.choice(WAITING_MESSAGES)
    msg = await context.bot.send_message(chat_id=chat_id, text=random_wait_text)
    
    try:
        direct_video_url = None
        platform_name = ""

        if current_mode == 'tiktok':
            direct_video_url = await fetch_tiktok(text)
            platform_name = "🎵 TikTok"
        elif current_mode == 'facebook':
            direct_video_url = await fetch_facebook(text)
            platform_name = "📘 Facebook"
        elif current_mode == 'instagram':
            direct_video_url = await fetch_instagram(text)
            platform_name = "📸 Instagram"

        context.user_data.pop('download_mode', None)

        if direct_video_url:
            BOT_STATS["total_downloads"] += 1
            
            # ভিডিও পাঠানো হবে (এটি চ্যাটে স্থায়ী থাকবে)
            await context.bot.send_video(
                chat_id=chat_id, 
                video=direct_video_url, 
                caption=f"✨ {platform_name} ভিডিও সফলভাবে ডাউনলোড করা হয়েছে!\n📥 Powered by @{ADMIN_USERNAME}"
            )
            # প্রসেসিং মেসেজটি ডিলিট করে দেওয়া
            await msg.delete()
        else:
            await msg.edit_text("❌ এই লিংক থেকে ভিডিও সংগ্রহ করা সম্ভব হয়নি। সঠিক লিংক দিয়ে আবার চেষ্টা করুন।")
            context.job_queue.run_once(
                lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id), 
                5
            )
            
    except Exception as e:
        await msg.edit_text("⚠️ প্রসেসিংয়ের সময় সামান্য সমস্যা হয়েছে। আবার চেষ্টা করুন।")
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id), 
            5
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
    
    print("Nahid AI Video Downloader & Chat Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()