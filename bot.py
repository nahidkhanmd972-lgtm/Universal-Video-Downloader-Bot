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

# ফ্রি ও ফাস্ট সোশ্যাল মিডিয়া ডাউনলোডার এপিআই ফাংশন
async def get_video_download_link(url: str):
    try:
        # ফ্রি পাবলিক ভিডিও ডাউনলোডার এপিআই ব্যবহার করা হচ্ছে (যাতে সার্ভার ক্র্যাশ না করে)
        api_url = f"https://tikwm.com/api/?url={encode_url(url)}"
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            # টিকটক বা অন্যান্য সোশ্যাল মিডিয়ার ডাইরেক্ট ভিডিও লিংক রিটার্ন করবে
            video_url = data["data"]["play"]
            return video_url
    except Exception as e:
        print(f"API Error: {e}")
    return None

def encode_url(url):
    import urllib.parse
    return urllib.parse.quote(url, safe='')

# /start কমান্ড হ্যান্ডলার
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    keyboard = [
        [
            InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
            InlineKeyboardButton("📌 ব্যবহারবিধি", callback_data="help_guide")
        ],
        [
            InlineKeyboardButton("💬 সরাসরি যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
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
        "⚡ এটি আপনার নেক্সট-জেনারেশন সোশ্যাল মিডিয়া ভিডিও ডাউনলোডার বট।\n"
        "টিকটক বা ফেসবুকের যেকোনো ভিডিওর লিংক এখানে পাঠান, কোনো ল্যাগ বা ক্র্যাশ ছাড়াই ইনস্ট্যান্ট পেয়ে যাবেন!\n\n"
        "👇 নিচের মেনু থেকে অপশন বেছে নিন:"
    )
    
    try:
        await update.message.delete()
    except:
        pass

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# ইনলাইন বাটন হ্যান্ডলার
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
            f"✨ আপনি এই হাই-স্পিড বটের একজন মূল্যবান ব্যবহারকারী!"
        )
        await query.edit_message_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 *সহজ ব্যবহারবিধি:*\n\n"
            "১. যেকোনো টিকটক বা রিলস ভিডিওর লিংক কপি করুন।\n"
            "২. সরাসরি এই চ্যাটে পেস্ট করে পাঠিয়ে দিন।\n"
            "৩. বট ম্যাজিকের মতো আপনার লিংকটি প্রসেস করে ভিডিও পাঠিয়ে দেবে এবং চ্যাট একদম পরিষ্কার রাখবে।\n\n"
            "💡 *বিশেষত্ব:* এটি কোনো ভারী ডাউনলোড প্রসেস চালায় না, তাই সার্ভার ১০০% ফাস্ট ও নিরাপদ থাকে।"
        )
        await query.edit_message_text(guide_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "bot_status":
        await query.edit_message_text(
            "🟢 *বটের বর্তমান অবস্থা:*\n\n"
            "• সার্ভার ক্লাউড: আল্ট্রা-ফাস্ট ও অপ্টিমাইজড\n"
            "• মেমোরি লিক: জিরো (শূন্য)\n"
            "• সিস্টেম: এপিআই ড্রাইভড\n\n"
            "সবকিছু একদম নিখুঁতভাবে কাজ করছে!", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 হোম মেনুতে ফিরে যান", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            await query.edit_message_text(
                "🛠️ *অ্যাডমিন কন্ট্রোল প্যানেল:*\n\n"
                "• ওনার: @NahidDevOfficial\n"
                "• স্ট্যাটাস: সুপারভাইজর এক্সেস গ্রান্টেড\n"
                "• প্রটোকল: জিরো-ক্র্যাশ এপিআই মোড", 
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
                InlineKeyboardButton("💬 সরাসরি যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME}")
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

# লিংক ও মেসেজ হ্যান্ডলার (ইনস্ট্যান্ট এপিআই প্রসেসিং ও অটো-ডিলিট)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id

    # যদি লিংক না হয়, তবে মেসেজ সাথে সাথে ডিলিট
    if not (url.startswith("http://") or url.startswith("https://")):
        try:
            await update.message.delete()
        except:
            pass
        return

    # প্রসেসিং মেসেজ
    msg = await update.message.reply_text("⚡ ভিডিও ফেচ করা হচ্ছে, একটু অপেক্ষা করুন...")
    
    try:
        # ইউজারের পাঠানো লিংক মেসেজ মুছে ফেলা যাতে চ্যাট পরিষ্কার থাকে
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=user_msg_id)
        except Exception:
            pass

        # এপিআই থেকে ভিডিওর ডাইরেক্ট লিংক নিয়ে আসা
        direct_video_url = await get_video_download_link(url)
        
        if direct_video_url:
            # সরাসরি লিংক দিয়ে ভিডিও পাঠিয়ে দেওয়া (সার্ভারে কোনো ফাইল ডাউনলোডের ঝামেলা নেই!)
            await context.bot.send_video(chat_id=chat_id, video=direct_video_url, caption="✨ আপনার ভিডিও সফলভাবে ডাউনলোড করা হয়েছে!")
            await msg.delete()
        else:
            await msg.edit_text("❌ এই লিংকটি থেকে ভিডিও সংগ্রহ করা সম্ভব হয়নি। অন্য কোনো লিংক দিয়ে চেষ্টা করুন।")
            
    except Exception as e:
        await msg.edit_text("⚠️ প্রসেসিংয়ের সময় সামান্য সমস্যা হয়েছে। আবার চেষ্টা করুন।")
        print(f"Error: {e}")

# মেইন ফাংশন
def main():
    TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Super-Smooth API Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()