import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import time
import pandas as pd

# Библиотеки: pyTelegramBotAPI, requests, streamlit, pandas

# --- CONFIG ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
except:
    st.error("Настройте SECRETS (TELEGRAM_TOKEN и PEXELS_API_KEY)!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

if 'history' not in st.session_state:
    st.session_state.history = []

# --- PEXELS LOGIC ---

def fetch_resource(query, resource_type="photos"):
    """Загрузчик контента с обработкой ошибок."""
    page = random.randint(1, 20)
    base_url = "https://api.pexels.com/v1/search" if resource_type == "photos" else "https://api.pexels.com/videos/search"
    url = f"{base_url}?query={query}&per_page=15&page={page}"
    
    headers = {"Authorization": PEXELS_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('photos') if resource_type == "photos" else data.get('videos')
            if items:
                return random.choice(items)
    except Exception as e:
        st.error(f"Ошибка API: {e}")
    return None

# --- BOT LOGIC ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🖼 Поиск")
    
    msg = "🎮 **Media Hunter v3.0**\nНапиши любое слово (на англ.), а потом выбери формат!"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    if query == "🖼 Поиск":
        bot.reply_to(message, "Просто напиши тему поиска (например: Cars)")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🖼 Картинка", callback_data=f"img:{query}"),
        types.InlineKeyboardButton("🎞 Видео", callback_data=f"vid:{query}")
    )
    bot.send_message(message.chat.id, f"🎯 Запрос: **{query}**", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def process_callback(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    
    # Визуальный отклик в ТГ, что работа началась
    bot.answer_callback_query(call.id, "🎬 Загружаю контент...")
    bot.send_chat_action(chat_id, 'upload_video' if action == "vid" else 'upload_photo')

    if action == "img":
        item = fetch_resource(query, "photos")
        if item:
            bot.send_photo(chat_id, item['src']['large2x'], caption=f"✅ {query}")
            st.session_state.history.append({"Тип": "Фото", "Запрос": query, "Статус": "Успех"})
    
    elif action == "vid":
        item = fetch_resource(query, "videos")
        if item:
            # Ищем видео среднего размера (HD), чтобы Telegram его пропустил по ссылке
            # Telegram Cloud не любит файлы > 20MB при отправке по URL
            files = item['video_files']
            # Выбираем видео с шириной около 1280 (HD)
            target_video = None
            for f in files:
                if f['width'] and 1280 >= f['width'] >= 720:
                    target_video = f
                    break
            
            # Если HD не нашли, берем любое самое маленькое, чтобы точно отправилось
            if not target_video:
                target_video = min(files, key=lambda x: x['width'] if x['width'] else 9999)

            try:
                bot.send_video(
                    chat_id, 
                    target_video['link'], 
                    caption=f"📹 Видео: {query}\nКачество: {target_video['width']}p",
                    timeout=20, # Таймаут 20 секунд, чтобы не висеть вечно
                    supports_streaming=True
                )
                st.session_state.history.append({"Тип": "Видео", "Запрос": query, "Статус": "Успех"})
            except Exception as e:
                bot.send_message(chat_id, "⚠️ Видео слишком тяжелое для Telegram. Попробуй еще раз!")
                st.session_state.history.append({"Тип": "Видео", "Запрос": query, "Статус": f"Ошибка: {str(e)}"})

# --- BACKGROUND RUN ---
def start_polling():
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=1)

# --- STREAMLIT DASHBOARD ---
st.set_page_config(page_title="Admin Console", layout="wide")

if "active" not in st.session_state:
    t = Thread(target=start_polling)
    t.daemon = True
    t.start()
    st.session_state.active = True

st.title("🖥 Media Grabber Admin Panel")

tab1, tab2 = st.tabs(["📊 Логи", "⚙️ Статус"])

with tab1:
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history).iloc[::-1]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("История пуста")

with tab2:
    st.write(f"Бот запущен в: {time.strftime('%H:%M:%S')}")
    if st.button("Перезагрузить интерфейс"):
        st.rerun()

st.divider()
st.caption("v3.1: Исправлена проблема зависания видео")
