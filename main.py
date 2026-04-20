import streamlit as st
import telebot
import requests
from threading import Thread
import time

# Необходимые библиотеки (укажи их в requirements.txt):
# pyTelegramBotAPI
# requests
# streamlit

# --- ИНИЦИАЛИЗАЦИЯ ИЗ SECRETS ---
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
except Exception as e:
    st.error("Ошибка: Секреты не настроены в Streamlit Cloud!")
    st.stop()

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ФУНКЦИИ PEXELS ---

def get_pexels_video(query):
    """Поиск видео через Pexels API."""
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1"
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data['videos']:
                # Берем первое видео и его первый файл (обычно самый качественный)
                return data['videos'][0]['video_files'][0]['link']
            return None
    except:
        return None

def get_pexels_photo(query):
    """Поиск фото через Pexels API."""
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data['photos']:
                return data['photos'][0]['src']['large']
    except:
        return None

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "🎬 Привет! Напиши запрос, и я пришлю тебе видео и фото с Pexels!")

@bot.message_handler(func=lambda m: True)
def handle_query(message):
    query = message.text
    bot.send_message(message.chat.id, f"🔎 Ищу контент по запросу: {query}...")

    # Отправляем фото
    photo = get_pexels_photo(query)
    if photo:
        bot.send_photo(message.chat.id, photo, caption="🖼 Фото результат")
    
    # Отправляем видео
    video_url = get_pexels_video(query)
    if video_url:
        bot.send_video(message.chat.id, video_url, caption="📹 Видео результат")
    else:
        bot.send_message(message.chat.id, "❌ Видео по такому запросу не найдено.")

def start_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- ИНТЕРФЕЙС STREAMLIT (Admin Panel) ---

st.title("👨‍✈️ Управление Pexels Ботом")
st.write("Бот запущен и мониторит сообщения.")

if "bot_started" not in st.session_state:
    st.session_state.bot_started = False

if not st.session_state.bot_started:
    thread = Thread(target=start_bot)
    thread.daemon = True
    thread.start()
    st.session_state.bot_started = True
    st.success("Бот успешно запущен в фоновом потоке!")

st.divider()
st.subheader("Проверка контента прямо здесь")
test_q = st.text_input("Введите запрос для теста:", "Cyberpunk")
if st.button("Проверить API"):
    v = get_pexels_video(test_q)
    if v:
        st.video(v)
        st.success("API Pexels работает корректно!")