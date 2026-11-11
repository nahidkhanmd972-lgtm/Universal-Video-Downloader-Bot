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