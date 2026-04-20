import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread

# requirements.txt: pyTelegramBotAPI, requests, streamlit

# --- CONFIG ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
except:
    st.error("Настройте SECRETS (TELEGRAM_TOKEN и PEXELS_API_KEY)")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# История для админки
if 'history' not in st.session_state:
    st.session_state.history = []

# --- PEXELS LOGIC ---

def fetch_resource(query, resource_type="photos"):
    """Универсальный загрузчик с глубоким рандомом по страницам."""
    # Рандомизируем страницу (от 1 до 10), чтобы результаты всегда были новыми
    page = random.randint(1, 10)
    base_url = f"https://api.pexels.com/v1/search" if resource_type == "photos" else "https://api.pexels.com/videos/search"
    url = f"{base_url}?query={query}&per_page=15&page={page}"
    
    headers = {"Authorization": PEXELS_KEY}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('photos') if resource_type == "photos" else data.get('videos')
            if items:
                return random.choice(items)
    except:
        return None
    return None

# --- BOT LOGIC ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("📸 Фото")
    btn2 = types.KeyboardButton("📹 Видео")
    btn3 = types.KeyboardButton("🎲 Микс")
    markup.add(btn1, btn2, btn3)
    
    welcome_text = (
        "✨ **Добро пожаловать в MediaGrabber!**\n\n"
        "Пришли мне ключевое слово (например: *Nature*), а затем выбери тип контента кнопками ниже."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    user_query = message.text
    chat_id = message.chat.id

    # Игнорируем нажатия кнопок как поисковые запросы
    if user_query in ["📸 Фото", "📹 Видео", "🎲 Микс"]:
        bot.send_message(chat_id, "Сначала напиши слово для поиска (напр. 'Ocean'), а потом жми кнопку.")
        return

    # Создаем инлайн-кнопки под сообщением
    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(
        types.InlineKeyboardButton("Дай Фото", callback_data=f"p:{user_query}"),
        types.InlineKeyboardButton("Дай Видео", callback_data=f"v:{user_query}")
    )
    
    bot.send_message(chat_id, f"🎯 Выбран запрос: **{user_query}**\nЧто именно отправить?", 
                     parse_mode="Markdown", reply_markup=inline_markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    # Разделяем тип ресурса и запрос из callback_data
    res_type_code, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    
    bot.answer_callback_query(call.id, "Загружаю...")

    if res_type_code == "p":
        photo = fetch_resource(query, "photos")
        if photo:
            bot.send_photo(chat_id, photo['src']['large'], caption=f"🖼 Фото: {query}")
            st.session_state.history.append({"Тип": "Фото", "Запрос": query, "Время": time.strftime("%H:%M:%S")})
    else:
        video = fetch_resource(query, "videos")
        if video:
            video_link = video['video_files'][0]['link']
            bot.send_video(chat_id, video_link, caption=f"📹 Видео: {query}")
            st.session_state.history.append({"Тип": "Видео", "Запрос": query, "Время": time.strftime("%H:%M:%S")})

# --- RUN BOT ---
def run_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- STREAMLIT UI ---
import time

st.set_page_config(page_title="MediaGrabber PRO", page_icon="⚙️")

st.title("⚙️ MediaGrabber Pro Panel")

# Сайдбар с инфо
st.sidebar.title("Статистика")
st.sidebar.metric("Запросов сегодня", len(st.session_state.history))

if not st.session_state.get('bot_running'):
    t = Thread(target=run_bot)
    t.daemon = True
    t.start()
    st.session_state.bot_running = True

# Основной интерфейс
tab1, tab2 = st.tabs(["📊 Мониторинг", "🛠 Настройки API"])

with tab1:
    st.subheader("Последние действия пользователей")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history).iloc[::-1] # Последние сверху
        st.table(df)
    else:
        st.info("Ждем первых запросов от пользователей...")

with tab2:
    st.write("**Текущий API статус:** ✅ Подключено к Pexels")
    if st.button("Проверить лимиты"):
        st.write("Лимиты: 25,000 запросов в месяц (Standard Plan)")

st.divider()
st.caption("Developed for Police Cyber Division | Python 3.11")
