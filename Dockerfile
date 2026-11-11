# পাইথনের অফিশিয়াল লাইটওয়েট ইমেজ ব্যবহার করা
FROM python:3.10-slim

# ওয়ার্কিং ডিরেক্টরি সেট করা
WORKDIR /app

# প্রজেক্টের সব ফাইল কপি করে কন্টেইনারে নিয়ে যাওয়া
COPY . /app

# প্রয়োজনীয় পাইথন লাইব্রেরি ইনস্টল করা
RUN pip install --no-cache-dir -r requirements.txt

# বট স্টার্ট করার কমান্ড
CMD ["python", "bot.py"]