import os
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

# আপনার আসল টেলিগ্রাম ইউজার আইডি
ADMIN_ID = 8815124111

# আপনার যোগাযোগের অফিশিয়াল ইউজারনেম
ADMIN_USERNAME = "NahidDevOfficial"

# yt-dlp অপশনস - র‍্যাম ও সার্ভার সুরক্ষিত রাখতে হালকা রেজোলিউশন
def get_ydl_opts(output_path):
    return {
        'format': 'best[height<=360]', # সর্বোচ্চ 360p, যাতে সার্ভার ওভারলোড বা ক্র্যাশ না করে
        'outtmpl': output_path,
        'noplaylist': True,
        'socket_timeout': 30,
    }

async def download_video(url: str, output_path: str):
    ydl_opts = get_ydl_opts(output_path)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"Download Error: {e}")
        return False

# /start কমান্ড হ্যান্ডলার
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    # প্রফেশনাল ইনলাইন বাটনসমূহ
    keyboard = [
        [
            InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
            InlineKeyboardButton("📌 ডাউনলোড গাইড", callback_data="help_guide")
        ],
        [
            InlineKeyboardButton("💬 কন্টাক্ট অ্যাডমিন", url=f"https://t.me/{ADMIN_USERNAME}")
        ],
        [
            InlineKeyboardButton("🟢 বটের লাইভ স্ট্যাটাস", callback_data="bot_status")
        ]
    ]
    
    # যদি ইউজার নিজেই অ্যাডমিন (আপনি) হন, তবে এক্সট্রা অ্যাডমিন প্যানেল বাটন যোগ হবে
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন কন্ট্রোল প্যানেল", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"স্বাগতম, *{user_name}*! 👋\n\n"
        "🎬 এটি আপনার পার্সোনাল সোশ্যাল মিডিয়া ভিডিও ডাউনলোডার বট।\n"
        "যেকোনো ভিডিওর লিংক এখানে পাঠান, মুহূর্তের মধ্যে ডাউনলোড করে দেওয়া হবে!\n\n"
        "👇 নিচের বাটনগুলো থেকে যেকোনো অপশন বেছে নিতে পারেন:"
    )
    
    # আগের মেসেজ থাকলে তা ডিলিট করার চেষ্টা
    try:
        await update.message.delete()
    except:
        pass

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# ইনলাইন বাটন ক্লিক হ্যান্ডলার
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    if query.data == "my_profile":
        profile_text = (
            f"👤 **আপনার ইউজার প্রফাইল:**\n\n"
            f"• নাম: {user.first_name}\n"
            f"• ইউজারনেম: @{user.username if user.username else 'নেই'}\n"
            f"• আইডি: `{user.id}`\n\n"
            f"✨ আপনি এই বটের একজন মূল্যবান ব্যবহারকারী!"
        )
        await query.edit_message_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]]))

    elif query.data == "help_guide":
        guide_text = (
            "📌 **ব্যবহারের সহজ নিয়ম:**\n\n"
            "১. TikTok বা Facebook থেকে যেকোনো ভিডিওর লিংক কপি করুন।\n"
            "২. সরাসরি এই চ্যাটে লিংকটি পেস্ট করে পাঠিয়ে দিন।\n"
            "৩. বট স্বয়ংক্রিয়ভাবে আপনার লিংক মুছে ফেলবে এবং ভিডিও প্রসেস করে পাঠিয়ে দেবে।\n\n"
            "⚠️ *নোট:* সার্ভার সচল রাখতে ছোট ভিডিও বা রিলস লিংক ব্যবহার করুন।"
        )
        await query.edit_message_text(guide_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]]))

    elif query.data == "bot_status":
        await query.edit_message_text(
            "🟢 **বটের বর্তমান অবস্থা:**\n\n"
            "• সার্ভার: সচল রয়েছে\n"
            "• মেমোরি অপ্টিমাইজেশান: সক্রিয়\n"
            "• অটো-ক্লিনআপ: অন\n\n"
            "যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করতে পারেন।", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]]))

    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            await query.edit_message_text(
                "🛠️ **অ্যাডমিন কন্ট্রোল প্যানেল:**\n\n"
                "• ওনার: @NahidDevOfficial\n"
                "• স্ট্যাটাস: ফুল কন্ট্রোল (Verified Admin)\n"
                "• সিস্টেম: ক্লাউড অপ্টিমাইজড", 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]]))
        else:
            await query.edit_message_text("❌ আপনার এই প্যানেলে ঢোকার অনুমতি নেই!")

    elif query.data == "back_home":
        keyboard = [
            [
                InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
                InlineKeyboardButton("📌 ডাউনলোড গাইড", callback_data="help_guide")
            ],
            [
                InlineKeyboardButton("💬 কন্টাক্ট অ্যাডমিন", url=f"https://t.me/{ADMIN_USERNAME}")
            ],
            [
                InlineKeyboardButton("🟢 বটের লাইভ স্ট্যাটাস", callback_data="bot_status")
            ]
        ]
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠️ অ্যাডমিন কন্ট্রোল প্যানেল", callback_data="admin_panel")])
        
        await query.edit_message_text(
            f"স্বাগতম! 👋\n\nনিচের অপশনগুলো থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# লিংক ও মেসেজ হ্যান্ডলার (ভিডিও ডাউনলোড ও অটো-ডিলিট সিস্টেম)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id

    # যদি লেখাটি কোনো লিংক না হয় (যেমন সাধারণ চ্যাট বা হাই-হ্যালো), সাথে সাথে ডিলিট করে দেওয়া
    if not (url.startswith("http://") or url.startswith("https://")):
        try:
            await update.message.delete()
        except:
            pass
        return

    # প্রসেসিং মেসেজ পাঠানো
    msg = await update.message.reply_text("📥 ভিডিও প্রসেস হচ্ছে, একটু অপেক্ষা করুন...")
    
    file_name = f"video_{update.effective_user.id}.mp4"
    
    try:
        # ইউজারের পাঠানো মূল লিংক মেসেজটি সাথে সাথে চ্যাট থেকে ডিলিট করে দেওয়া
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=user_msg_id)
        except Exception:
            pass

        # দ্রুত গতিতে ভিডিও ডাউনলোড করা
        success = await download_video(url, file_name)
        
        if success and os.path.exists(file_name):
            # ভিডিও পাঠানো
            with open(file_name, 'rb') as video_file:
                await context.bot.send_video(chat_id=chat_id, video=video_file)
            # প্রসেসিং মেসেজটি ডিলিট করে দেওয়া
            await msg.delete()
        else:
            await msg.edit_text("❌ ভিডিওটি ডাউনলোড করা সম্ভব হয়নি। দয়া করে ছোট বা অন্য কোনো লিংক দিন।")
            
    except Exception as e:
        await msg.edit_text("⚠️ সার্ভারে অতিরিক্ত চাপের কারণে প্রসেসটি সম্পন্ন হয়নি। দয়া করে একটু পরে চেষ্টা করুন।")
        print(f"Error: {e}")
        
    finally:
        # কাজ শেষ হওয়ার সাথে সাথে সার্ভার থেকে ভিডিও ফাইল মুছে ফেলা (র‍্যাম খালি রাখার জন্য)
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
            except Exception as cleanup_error:
                print(f"Cleanup Error: {cleanup_error}")

# মেইন ফাংশন
def main():
    # আপনার টেলিগ্রাম বট টোকেন এখানে বসাবেন অথবা এনভায়রনমেন্ট ভেরিয়েবল থেকে রিড করবে
    TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # হ্যান্ডলারসমূহ রেজিস্টার করা
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running successfully...")
    application.run_polling()

if __name__ == '__main__':
    main()