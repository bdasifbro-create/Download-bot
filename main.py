# -*- coding: utf-8 -*-
import telebot
import yt_dlp
import os
import time
import threading
from telebot import types
from collections import defaultdict
from flask import Flask
from threading import Thread

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN") or "BOT_TOKEN"
ADMIN_ID = 8627605535

bot = telebot.TeleBot(BOT_TOKEN)

USER_FILE = "users.txt"
REFER_FILE = "referrals.txt"

url_storage = defaultdict(dict)
user_locks = defaultdict(threading.Lock)

# ================= WEB SERVER =================
app = Flask('')

@app.route('/')
def home():
    return "✅ BOT IS RUNNING"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ================= USER SYSTEM =================
def add_user(user_id):
    if not os.path.exists(USER_FILE):
        open(USER_FILE, "w").close()

    users = open(USER_FILE).read().splitlines()
    if str(user_id) not in users:
        with open(USER_FILE, "a") as f:
            f.write(f"{user_id}\n")

def get_points(user_id):
    if os.path.exists(REFER_FILE):
        for line in open(REFER_FILE):
            if ":" in line:
                uid, pts = line.strip().split(":")
                if uid == str(user_id):
                    return int(pts)
    return 0

# ================= MENU =================
def main_menu(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📥 Facebook", "📸 Instagram")
    markup.add("📺 YouTube", "🎵 TikTok")
    markup.add("📊 Stats", "🎁 Referral")
    markup.add("📞 Support", "📢 Update Channel")
    if is_admin:
        markup.add("⚙️ Admin Panel")
    return markup

# ================= DOWNLOAD =================
def progress_hook(d, chat_id, msg_id):
    if d['status'] == 'downloading':
        try:
            bot.edit_message_text(
                f"📥 {d.get('_percent_str','')}\n⚡ {d.get('_speed_str','')}",
                chat_id, msg_id
            )
        except:
            pass

def download_video(call_message, url, mode="HD"):
    user_id = call_message.from_user.id

    if not user_locks[user_id].acquire(blocking=False):
        bot.send_message(call_message.chat.id, "⚠️ Already processing!")
        return

    msg = bot.send_message(call_message.chat.id, "🚀 Processing...")

    file_name = f"vid_{user_id}_{int(time.time())}.mp4"

    ydl_opts = {
        'outtmpl': file_name,
        'quiet': True,
        'progress_hooks': [lambda d: progress_hook(d, call_message.chat.id, msg.message_id)],
    }

    if mode == "HD":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif mode == "SD":
        ydl_opts['format'] = 'best[height<=720]+bestaudio/best'
    else:
        ydl_opts['format'] = 'bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        with open(file_name, 'rb') as f:
            bot.send_video(call_message.chat.id, f)

        bot.delete_message(call_message.chat.id, msg.message_id)

    except Exception as e:
        bot.send_message(call_message.chat.id, f"Error: {str(e)[:100]}")

    finally:
        user_locks[user_id].release()
        if os.path.exists(file_name):
            os.remove(file_name)

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    add_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "Welcome!\n\n📢 Join Update Channel: https://t.me/new_bangla_mod",
        reply_markup=main_menu(message.from_user.id == ADMIN_ID)
    )

# ================= MESSAGE =================
@bot.message_handler(func=lambda m: True)
def handle(message):
    text = message.text.strip()
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)

    if text.startswith("http"):
        sid = str(int(time.time()))[-6:]
        url_storage[user_id][sid] = text

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("HD", callback_data=f"hd|{sid}"),
            types.InlineKeyboardButton("SD", callback_data=f"sd|{sid}")
        )
        markup.add(types.InlineKeyboardButton("Audio", callback_data=f"audio|{sid}"))

        bot.send_message(message.chat.id, "Select Quality:", reply_markup=markup)

    elif text == "📊 Stats":
        total = len(open(USER_FILE).readlines()) if os.path.exists(USER_FILE) else 0
        bot.send_message(message.chat.id, f"📊 Users: {total}")

    elif text == "🎁 Referral":
        username = bot.get_me().username
        link = f"https://t.me/{username}?start={user_id}"
        points = get_points(user_id)
        bot.send_message(message.chat.id, f"Points: {points}\n{link}")

    elif text == "📞 Support":
        bot.send_message(message.chat.id, "Admin: https://t.me/banglaadmin01")

    elif text == "📢 Update Channel":
        bot.send_message(message.chat.id, "Join 👉 https://t.me/new_bangla_mod")

    elif text == "⚙️ Admin Panel" and is_admin:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Broadcast", callback_data="broadcast"))
        markup.add(types.InlineKeyboardButton("Users", callback_data="users"))
        bot.send_message(message.chat.id, "Admin Panel", reply_markup=markup)

    else:
        bot.send_message(message.chat.id, "Send Link", reply_markup=main_menu(is_admin))

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = call.data
    user_id = call.from_user.id

    if "|" in data:
        mode, sid = data.split("|")
        url = url_storage[user_id].get(sid)

        bot.delete_message(call.message.chat.id, call.message.message_id)
        threading.Thread(target=download_video, args=(call.message, url, mode.upper())).start()

    elif data == "broadcast" and user_id == ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "Send message:")
        bot.register_next_step_handler(msg, do_broadcast)

    elif data == "users" and user_id == ADMIN_ID:
        if os.path.exists(USER_FILE):
            bot.send_document(call.message.chat.id, open(USER_FILE, 'rb'))

def do_broadcast(message):
    users = open(USER_FILE).read().splitlines()
    for uid in users:
        try:
            bot.send_message(uid, message.text)
        except:
            pass

# ================= RUN =================
print("Bot Running...")
keep_alive()
bot.infinity_polling()
