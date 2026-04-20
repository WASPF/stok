import streamlit as st
import telebot
import requests
import random
from threading import Thread

# Библиотеки для requirements.txt:
# pyTelegramBotAPI
# requests
# streamlit

# --- ИНИЦИАЛИЗАЦИЯ ИЗ SECRETS ---
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
except Exception as e:
    st.error("Ошибка: Секреты (Secrets) не настроены в Streamlit Cloud!")
    st.stop()

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ФУНКЦИИ PEXELS С РАНДОМОМ ---

def get_pexels_video(query):
    """Поиск случайного видео по запросу."""
    # Запрашиваем 15 вариантов вместо одного
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15"
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data['videos']:
                # Выбираем случайное видео из списка полученных
                random_video = random.choice(data['videos'])
                return random_video['video_files'][0]['link']
            return None
    except:
        return None

def get_pexels_photo(query):
    """Поиск случайного фото по запросу."""
    # Запрашиваем 15 вариантов
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=15"
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data['photos']:
                # Выбираем случайное фото
                random_photo = random.choice(data['photos'])
                return random_photo['src']['large']
    except:
        return None

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "🎬 Я обновился! Теперь на один и тот же запрос я буду присылать разные материалы. Попробуй!")

@bot.message_handler(func=lambda m: True)
def handle_query(message):
    query = message.text
    bot.send_message(message.chat.id, f"🔎 Ищу что-то новенькое по запросу: {query}...")

    # Получаем случайное фото
    photo = get_pexels_photo(query)
    if photo:
        bot.send_photo(message.chat.id, photo, caption="🖼 Случайное фото")
    
    # Получаем случайное видео
    video_url = get_pexels_video(query)
    if video_url:
        bot.send_video(message.chat.id, video_url, caption="📹 Случайное видео")
    else:
        bot.send_message(message.chat.id, "❌ Видео по запросу не найдено.")

def start_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- ИНТЕРФЕЙС STREAMLIT ---

st.title("👨‍✈️ Управление Pexels Ботом (v2.0)")
st.write("Теперь бот выдает рандомные результаты из топ-15 совпадений.")

if "bot_started" not in st.session_state:
    st.session_state.bot_started = False

if not st.session_state.bot_started:
    thread = Thread(target=start_bot)
    thread.daemon = True
    thread.start()
    st.session_state.bot_started = True
    st.success("Бот перезапущен с функцией рандома!")

st.divider()
st.subheader("Тест рандомайзера")
test_q = st.text_input("Введите запрос (нажми кнопку несколько раз):", "Space")
if st.button("Выдать случайный контент"):
    v = get_pexels_video(test_q)
    if v:
        st.video(v)
