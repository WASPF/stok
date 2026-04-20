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
    st.error("Настройте SECRETS (TELEGRAM_TOKEN и PEXELS_API_KEY) в панели Streamlit!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# История для админки в Streamlit
if 'history' not in st.session_state:
    st.session_state.history = []

# --- PEXELS LOGIC ---

def fetch_resource(query, resource_type="photos"):
    """Загрузчик с выбором качественного контента."""
    page = random.randint(1, 15)
    base_url = "https://api.pexels.com/v1/search" if resource_type == "photos" else "https://api.pexels.com/videos/search"
    url = f"{base_url}?query={query}&per_page=15&page={page}"
    
    headers = {"Authorization": PEXELS_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('photos') if resource_type == "photos" else data.get('videos')
            if items:
                return random.choice(items)
    except Exception as e:
        print(f"Ошибка API: {e}")
    return None

# --- BOT LOGIC ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📸 Фото", "📹 Видео")
    
    welcome_msg = (
        "🎬 **Media Pro Bot**\n\n"
        "Отправь мне ключевое слово на английском, а затем выбери формат.\n"
        "Я постараюсь прислать видео в максимально возможном качестве!"
    )
    bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    # Если пользователь нажал на кнопку без ввода слова
    if query in ["📸 Фото", "📹 Видео"]:
        bot.reply_to(message, "Сначала напиши тему (например: 'Space'), а потом жми кнопку.")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🖼 Картинка", callback_data=f"img:{query}"),
        types.InlineKeyboardButton("🎞 Видео (MP4)", callback_data=f"vid:{query}")
    )
    bot.send_message(message.chat.id, f"🔍 Ищу контент по запросу: *{query}*", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def process_callback(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    
    bot.answer_callback_query(call.id, "Обработка запроса...")

    if action == "img":
        item = fetch_resource(query, "photos")
        if item:
            # Отправляем фото в высоком разрешении
            img_url = item['src']['large2x'] 
            bot.send_photo(chat_id, img_url, caption=f"✅ Фото: {query}")
            st.session_state.history.append({"Тип": "Фото", "Запрос": query, "Время": time.strftime("%H:%M:%S")})
    
    elif action == "vid":
        item = fetch_resource(query, "videos")
        if item:
            # Выбираем HD файл из списка доступных файлов видео
            # Фильтруем файлы, чтобы найти самое высокое разрешение
            files = item['video_files']
            # Сортируем по ширине, чтобы взять лучшее качество
            best_video = max(files, key=lambda x: x['width'] if x['width'] else 0)
            video_url = best_video['link']
            
            try:
                # Попытка отправить как видео (с поддержкой стриминга)
                bot.send_video(
                    chat_id, 
                    video_url, 
                    caption=f"✅ Видео: {query}\nКачество: {best_video['width']}p",
                    supports_streaming=True
                )
            except:
                # Если Telegram не ест ссылку напрямую, пишем ошибку
                bot.send_message(chat_id, "⚠️ Не удалось загрузить это видео, попробуйте еще раз.")
            
            st.session_state.history.append({"Тип": "Видео", "Запрос": query, "Время": time.strftime("%H:%M:%S")})

# --- THREADED BOT RUN ---
def start_polling():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- STREAMLIT PANEL ---
st.set_page_config(page_title="Media Master Admin", layout="wide")

if "bot_active" not in st.session_state:
    thread = Thread(target=start_polling)
    thread.daemon = True
    thread.start()
    st.session_state.bot_active = True

st.title("📹 Media Master: Dashboard")

col1, col2 = st.columns([1, 3])

with col1:
    st.metric("Запросов в этой сессии", len(st.session_state.history))
    if st.button("Очистить логи"):
        st.session_state.history = []
        st.rerun()

with col2:
    st.subheader("Лог последних действий")
    if st.session_state.history:
        st.dataframe(pd.DataFrame(st.session_state.history).iloc[::-1], use_container_width=True)
    else:
        st.info("Бот ожидает активности пользователей...")

st.divider()
st.write("🔧 **Техническая информация:**")
st.code(f"Python 3.11 | pyTelegramBotAPI | Pexels API High-Res Mode")
