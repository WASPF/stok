import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import time

# Необходимые библиотеки: pyTelegramBotAPI, requests, streamlit

# --- CONFIGURATION ---
try:
    # Берем токены из секретов Streamlit
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
except Exception as e:
    st.error("Ошибка: Проверьте TELEGRAM_TOKEN и PEXELS_API_KEY в Secrets!")
    st.stop()

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- MESSENGER-X CHARACTER ENGINE ---
# Имитация работы с платформой messengerx.io

class StockCharacter:
    """
    Класс персонажа в стиле MessengerX. 
    Отвечает за 'личность' бота и обработку команд.
    """
    def __init__(self):
        self.name = "MediaScout"
        self.version = "1.0.4"
        self.instruction = "Я твой ассистент по поиску визуального контента. Использую Pexels API."

    def get_headers(self):
        """Заголовки для внешних API (имитация MessengerX Auth)"""
        return {
            "Authorization": PEXELS_API_KEY,
            "Content-Type": "application/json"
        }

    def search_media(self, query, media_type="photo"):
        """Метод поиска, адаптированный под логику SDK."""
        page = random.randint(1, 10)
        if media_type == "photo":
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&page={page}"
        else:
            url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&page={page}"
            
        try:
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data.get('photos' if media_type == "photo" else 'videos')
                return random.choice(items) if items else None
            return None
        except Exception as e:
            st.error(f"Ошибка поиска: {e}")
            return None

# Инициализируем нашего персонажа
scout = StockCharacter()

# --- TELEGRAM BOT HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Приветствие в стиле диалогового ИИ."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📸 Найти Фото", "📹 Найти Видео")
    
    welcome_text = (
        f"🤖 Привет! Я — **{scout.name}** (v{scout.version}).\n\n"
        f"{scout.instruction}\n\n"
        "Просто напиши, что ты хочешь найти, или нажми на кнопку ниже."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_dialogue(message):
    """Основной цикл обработки сообщений (MessengerX Dispatcher)."""
    text = message.text
    chat_id = message.chat.id

    if text == "📸 Найти Фото":
        msg = bot.send_message(chat_id, "🔍 Введи тему для фото (на английском):")
        bot.register_next_step_handler(msg, process_photo)
    elif text == "📹 Найти Видео":
        msg = bot.send_message(chat_id, "🔍 Введи тему для видео (на английском):")
        bot.register_next_step_handler(msg, process_video)
    else:
        # Если пользователь просто пишет текст, предлагаем быстрые действия
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🖼 Искать Фото", callback_data=f"img:{text}"),
            types.InlineKeyboardButton("🎬 Искать Видео", callback_data=f"vid:{text}")
        )
        bot.send_message(chat_id, f"Понял запрос: **{text}**. Что именно найти?", 
                         parse_mode="Markdown", reply_markup=markup)

def process_photo(message):
    query = message.text
    bot.send_chat_action(message.chat.id, 'upload_photo')
    res = scout.search_media(query, "photo")
    if res:
        bot.send_photo(message.chat.id, res['src']['large2x'], caption=f"🖼 Фото по запросу: {query}")
    else:
        bot.send_message(message.chat.id, "😔 Ничего не нашел. Попробуй другое слово.")

def process_video(message):
    query = message.text
    bot.send_chat_action(message.chat.id, 'upload_video')
    res = scout.search_media(query, "video")
    if res:
        # Выбираем HD качество для стабильности
        video_url = res['video_files'][0]['link']
        bot.send_video(message.chat.id, video_url, caption=f"📹 Видео по запросу: {query}", supports_streaming=True)
    else:
        bot.send_message(message.chat.id, "😔 Видео не найдено.")

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    """Обработка инлайн-кнопок."""
    action, query = call.data.split(":")
    bot.answer_callback_query(call.id, "Выполняю поиск...")
    
    if action == "img":
        res = scout.search_media(query, "photo")
        if res: bot.send_photo(call.message.chat.id, res['src']['large2x'])
    elif action == "vid":
        res = scout.search_media(query, "video")
        if res: 
            video_url = res['video_files'][0]['link']
            bot.send_video(call.message.chat.id, video_url, supports_streaming=True)

# --- STREAMLIT DASHBOARD ---

def run_bot():
    """Запуск бота в фоновом режиме."""
    bot.remove_webhook()
    bot.polling(none_stop=True)

st.set_page_config(page_title="MessengerX Bot Hub", page_icon="🤖")

st.title("🤖 MessengerX Style Media Hub")
st.write("Этот интерфейс имитирует панель управления ИИ-персонажем.")

if "bot_thread" not in st.session_state:
    thread = Thread(target=run_bot, daemon=True)
    thread.start()
    st.session_state.bot_thread = True
    st.success("Бот 'MediaScout' успешно запущен и готов к работе!")

# Админ-функции
st.divider()
st.subheader("Настройки персонажа")
st.text_input("Имя бота", value=scout.name, disabled=True)
st.text_area("Инструкция (System Prompt)", value=scout.instruction, disabled=True)

st.sidebar.title("Управление")
if st.sidebar.button("Перезагрузить страницу"):
    st.rerun()

st.sidebar.divider()
st.sidebar.info("Используется логика MessengerX для управления диалогами.")
