import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import replicate
import time
import pandas as pd
import os

# requirements.txt: pyTelegramBotAPI, requests, streamlit, replicate, pandas

# --- 1. ПЕРВИЧНАЯ НАСТРОЙКА ---
st.set_page_config(page_title="Media AI Master: Luma Edition", layout="wide")

if 'bot_history' not in st.session_state:
    st.session_state['bot_history'] = []

SHARED_LOGS = []

try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN
except Exception as e:
    st.error("Настройте SECRETS (TELEGRAM_TOKEN, PEXELS_API_KEY, REPLICATE_API_TOKEN)!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# --- 2. ENGINE (ЛОГИКА API) ---

class VideoAI:
    @staticmethod
    def get_stock(query):
        """Поиск видео на Pexels."""
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            vids = r.get('videos', [])
            if vids:
                return vids[0]['video_files'][0]['link']
            return None
        except: return None

    @staticmethod
    def luma_reframe(video_url, prompt="Focus on the main subject"):
        """Использование Luma Reframe API для изменения формата видео."""
        try:
            output = replicate.run(
                "luma/reframe-video",
                input={
                    "prompt": prompt,
                    "video_url": video_url,
                    "aspect_ratio": "9:16" # Делаем вертикальным для Reels/Shorts
                }
            )
            # У Luma вывод — это объект с атрибутом .url
            return output.url if hasattr(output, 'url') else str(output)
        except Exception as e:
            return f"Error: {str(e)}"

# --- 3. ТЕЛЕГРАМ ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎬 Найти и Рефреймить (Luma)", "🖼 Просто Сток")
    bot.send_message(message.chat.id, "🤖 **Media Master + Luma AI**\nЯ могу найти видео и переделать его под вертикальный формат 9:16!", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    if query in ["🎬 Найти и Рефреймить (Luma)", "🖼 Просто Сток"]:
        bot.send_message(message.chat.id, "Напиши тему видео (на англ.):")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✨ Luma Reframe (9:16)", callback_data=f"luma:{query}"),
        types.InlineKeyboardButton("📦 Обычный Сток", callback_data=f"stock:{query}")
    )
    bot.send_message(message.chat.id, f"🎯 Запрос: **{query}**\nВыбери режим:", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "stock":
        bot.send_message(chat_id, "🔎 Ищу видео...")
        res = VideoAI.get_stock(query)
        if res:
            bot.send_video(chat_id, res, caption=f"✅ Сток: {query}")
            SHARED_LOGS.append({"Запрос": query, "Тип": "Сток", "Статус": "Успех"})
        else:
            bot.send_message(chat_id, "❌ Не найдено.")

    elif action == "luma":
        status_msg = bot.send_message(chat_id, "⚙️ Сначала ищу видео, затем отправляю в Luma AI...")
        
        # 1. Находим видео-источник
        source_video = VideoAI.get_stock(query)
        
        if source_video:
            bot.edit_message_text("🧬 Видео найдено. Luma AI начинает рефрейминг в 9:16...", chat_id, status_msg.message_id)
            bot.send_chat_action(chat_id, 'record_video')
            
            # 2. Отправляем в Luma
            result_url = VideoAI.luma_reframe(source_video, f"Follow the subject in {query}")
            
            if result_url and "http" in result_url:
                bot.send_video(chat_id, result_url, caption=f"🔥 Luma Reframe Готов!\nФормат: 9:16 (Vertical)\nТема: {query}")
                SHARED_LOGS.append({"Запрос": query, "Тип": "Luma", "Статус": "Успех"})
            else:
                bot.send_message(chat_id, f"⚠️ Ошибка Luma: {result_url}")
                SHARED_LOGS.append({"Запрос": query, "Тип": "Luma", "Статус": "Ошибка"})
        else:
            bot.send_message(chat_id, "❌ Не удалось найти исходное видео для обработки.")

# --- 4. ЗАПУСК БОТА ---

def run_bot_forever():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- 5. ИНТЕРФЕЙС STREAMLIT ---

st.title("🖥 Media Master Dashboard: Luma & Pexels")

if "bot_thread_active" not in st.session_state:
    thread = Thread(target=run_bot_forever, daemon=True)
    thread.start()
    st.session_state.bot_thread_active = True

if SHARED_LOGS:
    for log in SHARED_LOGS:
        st.session_state.bot_history.append(log)
    SHARED_LOGS.clear()

st.subheader("📊 История обработки")
if st.session_state.bot_history:
    df = pd.DataFrame(st.session_state.bot_history).iloc[::-1]
    st.dataframe(df, use_container_width=True)

st.sidebar.subheader("Статус API")
st.sidebar.write("Luma AI (Replicate): ✅")
st.sidebar.write("Pexels: ✅")

if st.sidebar.button("Очистить историю"):
    st.session_state.bot_history = []
    st.rerun()
