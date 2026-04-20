import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import time
import pandas as pd

# Библиотеки: pyTelegramBotAPI, requests, streamlit, pandas

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
except Exception as e:
    st.error("Настройте SECRETS в Streamlit (TELEGRAM_TOKEN и PEXELS_API_KEY)!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# Глобальное хранилище логов для Streamlit
if 'bot_logs' not in st.session_state:
    st.session_state.bot_logs = []

# --- КЛАСС ПЕРСОНАЖА (MESSENGER-X STYLE) ---

class MediaScout:
    def __init__(self):
        self.headers = {"Authorization": PEXELS_KEY}

    def find_video(self, query):
        """Поиск видео с защитой от пустых ответов."""
        page = random.randint(1, 20)
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=10&page={page}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                videos = data.get('videos', [])
                if videos:
                    v_item = random.choice(videos)
                    # Выбираем HD качество (обычно второй или третий файл в списке)
                    # Фильтруем, чтобы найти ссылку, которая заканчивается на .mp4
                    for f in v_item['video_files']:
                        if f['width'] and 720 <= f['width'] <= 1920:
                            return f['link']
                    return v_item['video_files'][0]['link']
            return None
        except Exception as e:
            return f"Error: {e}"

    def find_photo(self, query):
        """Поиск фото."""
        page = random.randint(1, 20)
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=10&page={page}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                photos = data.get('photos', [])
                if photos:
                    return random.choice(photos)['src']['large2x']
            return None
        except:
            return None

scout = MediaScout()

# --- ОБРАБОТКА ТЕЛЕГРАМ ---

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Поиск медиа")
    bot.send_message(
        message.chat.id, 
        "🤖 **MediaScout v1.1** на связи.\nНапиши тему (на англ.), и я подберу контент!", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: True)
def get_query(message):
    query = message.text
    if query == "🔍 Поиск медиа":
        bot.send_message(message.chat.id, "Жду твое ключевое слово...")
        return

    # Создаем инлайн-кнопки с уникальным callback_data
    markup = types.InlineKeyboardMarkup()
    btn_img = types.InlineKeyboardButton("🖼 Фото", callback_data=f"img|{query}")
    btn_vid = types.InlineKeyboardButton("🎬 Видео", callback_data=f"vid|{query}")
    markup.add(btn_img, btn_vid)
    
    bot.send_message(message.chat.id, f"🎯 Запрос принят: **{query}**\nЧто прислать?", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    # Разделяем по символу '|', чтобы не было конфликтов с ":" в тексте
    data_parts = call.data.split("|")
    action = data_parts[0]
    query = data_parts[1]
    
    bot.answer_callback_query(call.id, "Выполняю... 🚀")
    
    if action == "img":
        bot.send_chat_action(call.message.chat.id, 'upload_photo')
        url = scout.find_photo(query)
        if url:
            bot.send_photo(call.message.chat.id, url, caption=f"✅ Фото по запросу: {query}")
            st.session_state.bot_logs.append({"Тип": "Фото", "Запрос": query, "Статус": "Ок"})
        else:
            bot.send_message(call.message.chat.id, "❌ Фото не найдено.")
            
    elif action == "vid":
        bot.send_chat_action(call.message.chat.id, 'upload_video')
        video_url = scout.find_video(query)
        
        if video_url and not video_url.startswith("Error"):
            try:
                bot.send_video(call.message.chat.id, video_url, caption=f"✅ Видео: {query}", supports_streaming=True)
                st.session_state.bot_logs.append({"Тип": "Видео", "Запрос": query, "Статус": "Ок"})
            except Exception as e:
                bot.send_message(call.message.chat.id, "⚠️ Ошибка отправки: файл слишком тяжелый.")
                st.session_state.bot_logs.append({"Тип": "Видео", "Запрос": query, "Статус": "Fail"})
        else:
            bot.send_message(call.message.chat.id, "❌ Видео не найдено или произошла ошибка API.")

# --- ЗАПУСК ПОТОКА ---
def start_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- ИНТЕРФЕЙС STREAMLIT ---
st.set_page_config(page_title="MediaScout Console", layout="wide")
st.title("🛰 MediaScout Admin Dashboard")

if "thread_started" not in st.session_state:
    t = Thread(target=start_bot, daemon=True)
    t.start()
    st.session_state.thread_started = True

# Панель логов
st.subheader("Логи активности")
if st.session_state.bot_logs:
    st.table(pd.DataFrame(st.session_state.bot_logs).iloc[::-1])
else:
    st.info("Бот запущен. Ожидаем действий пользователей в Telegram.")

if st.button("Обновить"):
    st.rerun()
