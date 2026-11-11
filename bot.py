import os
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

# আপনার আসল টেলিগ্রাম ইউজার আইডি
ADMIN_ID = 8815124111
ADMIN_USERNAME = "NahidDevOfficial"

# ==========================================
# মাল্টি-এপিআই ফলব্যাক সিস্টেম (Multi-API System)
# ==========================================

# ১. টিকটক ডাউনলোডার (একাধিক এপিআই ব্যাকআপ সহ)
async def fetch_tiktok(url: str):
    apis = [
        f"https://tikwm.com/api/?url={url}",
        f"https://api.cobalt.tools/api/json" # ব্যাকআপ
    ]
    
    # প্রথম এপিআই (TikWM) ট্রাই করা
    try:
        res = requests.get(apis[0], timeout=6).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except:
        pass
        
    # দ্বিতীয় এপিআই (Cobalt) ট্রাই করা
    try:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        res = requests.post(apis[1], json={"url": url}, headers=headers, timeout=6).json()
        if "url" in res:
            return res["url"]
    except:
        pass
        
    return None

# ২. ফেসবুক ডাউনলোডার (একাধিক এপিআই ব্যাকআপ সহ - ফেসবুকের জন্য এক্সট্রা সিকিউরড)
async def fetch_facebook(url: str):
    # ফেসবুক এবং সোশ্যাল মিডিয়ার জন্য Cobalt এবং অন্যান্য ওপেন এপিআই
    apis = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json" # আরেকটি পাবলিক ইনস্ট্যান্স
    ]
    
    for api in apis:
        try:
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            payload = {"url": url}
            res = requests.post(api, json=payload, headers=headers, timeout=7).json()
            if "url" in res:
                return res["url"]
            elif "picker" in res_data if 'res_data' in locals() else False:
                return res["picker"][0]["url"]
        except:
            continue
            
    return None

# ৩. ইনস্টাগ্রাম ডাউনলোডার
async def fetch_instagram(url: str):
    try:
        api_endpoint = "https://api.cobalt.tools/api/json"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        res = requests.post(api_endpoint, json={"url": url}, headers=headers, timeout=7).json()
        
        if "url" in res:
            return res["url"]
        elif "picker" in res:
            return res["picker"][0]["url"]
    except:
        pass
    return None

# ৪. ইউটিউব ডাউনলোডার (শর্টস বা ভিডিও)
async def fetch_youtube(url: str):
    try:
        api_endpoint = "https://api.cobalt.tools/api/json"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        # ইউটিউবের জন্য অডিও/ভিডিও কনফিগারেশনসহ পেলোড
        payload = {"url": url, "vQuality": "360"}
        res = requests.post(api_endpoint, json=payload, headers=headers, timeout=8).json()
        
        if "url" in res:
            return res["url"]
    except:
        pass
    return None

# লিংকের ধরন বুঝে সঠিক এপিআই সিলেক্ট করার মাস্টার ফাংশন
async def get_universal_video(url: str):
    url_lower = url.lower()
    video_link = None
    
    if "tiktok.com" in url_lower or "douyin.com" in url_lower:
        video_link = await fetch_tiktok(url)
    elif "facebook.com" in url_lower or "fb.watch" in url_lower or "fbdl" in url_lower:
        video_link = await fetch_facebook(url)
    elif "instagram.com" in url_lower:
        video_link = await fetch_instagram(url)
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        video_link = await fetch_youtube(url)
    else:
        # যদি অন্য কোনো লিংক হয়, তবে সার্বজনীন Cobalt এপিআই দিয়ে ট্রাই করবে
        video_link = await fetch_facebook(url)
        
    return video_link

# ==========================================
# টেলিগ্রাম বট ইন্টারফেস ও হ্যান্ডলারসমূহ
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    keyboard = [
        [
            InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
            InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
        ],
        [
            InlineKeyboardButton("💬 অ্যাডমিন যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
        ],
        [
            InlineKeyboardButton("🟢 সার্ভার লাইভ স্ট্যাটাস", callback_data="bot_status")
        ]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন কন্ট্রোল প্যানেল", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"স্বাগতম, *{user_name}*! 🚀\n\n"
        "⚡ এটি আপনার মাল্টি-এপিআই পাওয়ার্ড সোশ্যাল মিডিয়া ভিডিও ডাউনলোডার বট।\n"
        "• টিকটক, ফেসবুক, ইনস্টাগ্রাম ও ইউটিউব লিংক দিন\n"
        "• ইনস্ট্যান্ট ভিডিও ডাউনলোডের ম্যাজিক দেখুন!\n\n"
        "👇 নিচের মেনু থেকে অপশন বেছে নিন:"
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
            f"👤 *আপনার ইউজার প্রফাইল:*\n\n"
            f"• নাম: {user.first_name}\n"
            f"• ইউজারনেম: @{user.username if user.username else 'নেই'}\n"
            f"• আইডি: `{user.id}`\n\n"
            f"✨ আপনি এই মাল্টি-এপিআই সিস্টেমের একজন বিশেষ ব্যবহারকারী!"
        )
        await query.edit_message_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 *সহজ ব্যবহারবিধি:*\n\n"
            "১. TikTok, Facebook, Instagram বা YouTube থেকে যেকোনো ভিডিওর লিংক কপি করুন।\n"
            "২. সরাসরি এই চ্যাটে পেস্ট করে পাঠিয়ে দিন।\n"
            "৩. বট স্বয়ংক্রিয়ভাবে মাল্টিপল এপিআই সুইচ করে সেরা ভিডিওটি আপনার কাছে পৌঁছে দেবে!\n\n"
            "🛡️ *বিশেষত্ব:* সার্ভারে কোনো ভারী ফাইল ডাউনলোড হয় না, তাই এটি আজীবন ফ্রি ও সুপার ফাস্ট।"
        )
        await query.edit_message_text(guide_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "bot_status":
        await query.edit_message_text(
            "🟢 *বটের বর্তমান অবস্থা:*\n\n"
            "• ক্লাউড সার্ভার: অপ্টিমাইজড ও সচল\n"
            "• এপিআই ফলব্যাক সিস্টেম: সক্রিয় (Active)\n"
            "• মেমোরি লিক: শূন্য (Zero Crash)", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            await query.edit_message_text(
                "🛠️ *অ্যাডমিন কন্ট্রোল প্যানেল:*\n\n"
                "• ওনার: @NahidDevOfficial\n"
                "• স্ট্যাটাস: সুপারভাইজর এক্সেস গ্রান্টেড\n"
                "• প্রটোকল: মাল্টি-এপিআই মোড", 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))
        else:
            await query.edit_message_text("❌ আপনার এই প্যানেলে ঢোকার অনুমতি নেই!")

    elif query.data == "back_home":
        keyboard = [
            [
                InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
                InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
            ],
            [
                InlineKeyboardButton("💬 অ্যাডমিন যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
            ],
            [
                InlineKeyboardButton("🟢 সার্ভার লাইভ স্ট্যাটাস", callback_data="bot_status")
            ]
        ]
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন কন্ট্রোল প্যানেল", callback_data="admin_panel")])
        
        await query.edit_message_text(
            f"স্বাগতম! আবার নিচের অপশনগুলো থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id

    # লিংক না হলে মেসেজ ডিলিট
    if not (url.startswith("http://") or url.startswith("https://")):
        try:
            await update.message.delete()
        except:
            pass
        return

    msg = await update.message.reply_text("⚡ মাল্টি-এপিআই প্রসেসিং চলছে, একটু অপেক্ষা করুন...")
    
    try:
        # ইউজারের পাঠানো লিংক মেসেজ মুছে ফেলা
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=user_msg_id)
        except Exception:
            pass

        # ইউনিভার্সাল এপিআই থেকে ভিডিও ফেচ করা
        direct_video_url = await get_universal_video(url)
        
        if direct_video_url:
            await context.bot.send_video(
                chat_id=chat_id, 
                video=direct_video_url, 
                caption="✨ ভিডিও সফলভাবে ডাউনলোড করা হয়েছে!"
            )
            await msg.delete()
        else:
            await msg.edit_text("❌ এই লিংক থেকে ভিডিও সংগ্রহ করা সম্ভব হয়নি। অন্য কোনো লিংক দিয়ে চেষ্টা করুন।")
            
    except Exception as e:
        await msg.edit_text("⚠️ প্রসেসিংয়ের সময় সামান্য সমস্যা হয়েছে। আবার চেষ্টা করুন।")
        print(f"Error: {e}")

def main():
    TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Multi-API Fallback Bot is running successfully...")
    application.run_polling()

if __name__ == '__main__':
    main()