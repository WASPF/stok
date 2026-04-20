import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import time

# Список для requirements.txt: pyTelegramBotAPI, requests, streamlit

# --- CONFIG ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
except:
    st.error("Настройте SECRETS (TELEGRAM_TOKEN, PEXELS_API_KEY)!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# --- MESSENGER-X STYLE LOGIC (Character AI) ---

class MediaAssistant:
    """Класс-ассистент, имитирующий логику MessengerX."""
    
    def __init__(self):
        self.name = "MediaExpert AI"
        self.role = "Профессиональный бильд-редактор"

    def get_response(self, text):
        """Логика 'мышления' бота."""
        text = text.lower()
        if "привет" in text:
            return f"Здравствуйте! Я {self.name}. Помогу найти лучшие кадры для вашего проекта. Что ищем?"
        elif "кто ты" in text:
            return f"Я — {self.role}. Моя база включает Pexels и другие библиотеки."
        else:
            return None

# --- BOT LOGIC ---

assistant = MediaAssistant()

@bot.message_handler(commands=['start'])
def start(message):
    welcome = assistant.get_response("привет")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🖼 Найти Фото", "📹 Найти Видео")
    bot.send_message(message.chat.id, welcome, reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_interaction(message):
    chat_id = message.chat.id
    text = message.text

    # Проверяем, не является ли сообщение системным вопросом к ИИ
    ai_reply = assistant.get_response(text)
    if ai_reply and text not in ["🖼 Найти Фото", "📹 Найти Видео"]:
        bot.send_message(chat_id, ai_reply)
        return

    if text == "🖼 Найти Фото":
        msg = bot.send_message(chat_id, "Введите тему для фото (на англ.):")
        bot.register_next_step_handler(msg, process_photo_search)
    elif text == "📹 Найти Видео":
        msg = bot.send_message(chat_id, "Введите тему для видео (на англ.):")
        bot.register_next_step_handler(msg, process_video_search)
    else:
        bot.reply_to(message, "Я пока не понимаю эту команду. Попробуйте нажать кнопку или написать 'Привет'.")

def process_photo_search(message):
    query = message.text
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1&page={random.randint(1,20)}"
    
    try:
        res = requests.get(url, headers=headers).json()
        if res.get('photos'):
            img = res['photos'][0]['src']['large2x']
            bot.send_photo(message.chat.id, img, caption=f"✨ Специально для вас по запросу: {query}")
        else:
            bot.send_message(message.chat.id, "Ничего не найдено. Попробуйте другое слово.")
    except:
        bot.send_message(message.chat.id, "Ошибка связи с базой данных.")

def process_video_search(message):
    query = message.text
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&page={random.randint(1,15)}"
    
    try:
        res = requests.get(url, headers=headers).json()
        if res.get('videos'):
            video = res['videos'][0]['video_files'][0]['link']
            bot.send_video(message.chat.id, video, caption=f"🎬 Видео-результат: {query}")
        else:
            bot.send_message(message.chat.id, "Видео не найдено.")
    except:
        bot.send_message(message.chat.id, "Ошибка загрузки видео.")

# --- STREAMLIT DASHBOARD ---

def run_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

st.set_page_config(page_title="MessengerX Concept", layout="wide")
st.title("🤖 MessengerX Style Interface")

if "active" not in st.session_state:
    Thread(target=run_bot, daemon=True).start()
    st.session_state.active = True

st.success("Интеллектуальный ассистент активен.")
st.write(f"Бот имитирует роль: **{assistant.role}**")

# Статистика сессии
st.divider()
st.subheader("Мониторинг диалогов")
st.info("Здесь будут отображаться логи общения в стиле MessengerX.")
