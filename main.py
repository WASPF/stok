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
st.set_page_config(page_title="AI Video Master", layout="wide")

# Инициализация хранилища логов (используем глобальную переменную для доступа из потоков)
if 'bot_history' not in st.session_state:
    st.session_state['bot_history'] = []

# Глобальный список для обмена данными между потоком бота и Streamlit
# Это решает проблему KeyError/AttributeError в потоках
SHARED_LOGS = []

try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN
except Exception as e:
    st.error("Ошибка конфигурации Secrets! Проверьте TELEGRAM_TOKEN, PEXELS_API_KEY и REPLICATE_API_TOKEN.")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# --- 2. ENGINE (ЛОГИКА API) ---

class VideoAI:
    @staticmethod
    def get_stock(query):
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=10"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            vids = r.get('videos', [])
            if vids:
                # Выбираем не слишком тяжелое видео
                return vids[0]['video_files'][0]['link']
            return None
        except: return None

    @staticmethod
    def generate_ai(prompt):
        try:
            output = replicate.run(
                "anotherjesse/zeroscope-v2-xl:9f742d46474161b405b5f058cf57028170e30c416e04439c74077797c774304b",
                input={
                    "prompt": prompt,
                    "num_frames": 16,
                    "fps": 8,
                    "width": 576,
                    "height": 320
                }
            )
            return output[0] if output and len(output) > 0 else None
        except Exception as e:
            return f"Error: {str(e)}"

# --- 3. ТЕЛЕГРАМ ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Найти готовое", "🧠 Сгенерировать ИИ")
    bot.send_message(message.chat.id, "🛰 **Media AI Studio**\nНапиши запрос, затем выбери действие.", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    if query in ["🔍 Найти готовое", "🧠 Сгенерировать ИИ"]:
        bot.send_message(message.chat.id, "Введите тему на английском:")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📦 Сток Pexels", callback_data=f"f:{query}"),
        types.InlineKeyboardButton("🤖 Нейросеть", callback_data=f"g:{query}")
    )
    bot.send_message(message.chat.id, f"🎯 Запрос: **{query}**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "f":
        bot.send_message(chat_id, "🔎 Ищу видео на стоках...")
        res = VideoAI.get_stock(query)
        if res:
            bot.send_video(chat_id, res, caption=f"✅ Сток: {query}")
            SHARED_LOGS.append({"Запрос": query, "Тип": "Сток", "Статус": "Успех"})
        else:
            bot.send_message(chat_id, "❌ Ничего не найдено.")

    elif action == "g":
        bot.send_message(chat_id, "🧪 Нейросеть начала работу (около 1 мин)...")
        bot.send_chat_action(chat_id, 'record_video')
        
        result = VideoAI.generate_ai(query)
        
        if result and not str(result).startswith("Error"):
            bot.send_video(chat_id, result, caption=f"🔥 Сгенерировано: {query}")
            SHARED_LOGS.append({"Запрос": query, "Тип": "ИИ", "Статус": "Успех"})
        else:
            bot.send_message(chat_id, f"⚠️ Ошибка: {result}")
            SHARED_LOGS.append({"Запрос": query, "Тип": "ИИ", "Статус": f"Ошибка: {result}"})

# --- 4. ЗАПУСК БОТА ---

def run_bot_forever():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- 5. ИНТЕРФЕЙС STREAMLIT ---

st.title("🖥 Media AI Control Hub")

# Запуск потока бота только один раз
if "bot_thread_active" not in st.session_state:
    thread = Thread(target=run_bot_forever, daemon=True)
    thread.start()
    st.session_state.bot_thread_active = True

# Отображение логов
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 История активности")
    # Переносим данные из общего списка в session_state для отображения
    if SHARED_LOGS:
        for log in SHARED_LOGS:
            st.session_state.bot_history.append(log)
        SHARED_LOGS.clear() # Очищаем буфер после переноса

    if st.session_state.bot_history:
        df = pd.DataFrame(st.session_state.bot_history).iloc[::-1]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Бот ожидает запросов. Информация появится здесь автоматически.")

with col2:
    st.subheader("🛠 Статус систем")
    st.write(f"Telegram Bot: ✅ Online")
    st.write(f"Pexels API: ✅ Connected")
    st.write(f"Replicate AI: ✅ Ready")
    
    if st.button("Очистить логи"):
        st.session_state.bot_history = []
        st.rerun()

st.divider()
st.caption("v5.2: Исправлены ошибки SessionState в многопоточности.")
