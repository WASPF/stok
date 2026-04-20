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
st.set_page_config(page_title="AI Video Studio 2026", layout="wide")

if 'bot_history' not in st.session_state:
    st.session_state['bot_history'] = []

# Очередь для логов между потоком бота и Streamlit
SHARED_LOGS = []

try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN
except Exception as e:
    st.error("Ошибка Secrets! Проверьте токены в панели Streamlit Cloud.")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# --- 2. ENGINE (ЛОГИКА API) ---

class VideoAI:
    @staticmethod
    def get_stock(query):
        """Поиск видео на Pexels."""
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=10"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            vids = r.get('videos', [])
            if vids:
                return vids[0]['video_files'][0]['link']
            return None
        except: return None

    @staticmethod
    def generate_ai(prompt):
        """Генерация через стабильную модель AnimateDiff (Replicate)."""
        try:
            # Используем AnimateDiff — она сейчас самая надежная для текстовых промптов
            output = replicate.run(
                "lucataco/animate-diff:be11f4a83af975733448351da254923f773400a4e17743f0290130638e967b0b",
                input={
                    "prompt": prompt,
                    "n_prompt": "bad quality, low resolution, blurry",
                    "steps": 25,
                    "guidance_scale": 7.5
                }
            )
            # Модель возвращает список ссылок, берем первую
            if isinstance(output, list) and len(output) > 0:
                return output[0]
            return output # Если вернулась одна строка
        except Exception as e:
            return f"Error: {str(e)}"

# --- 3. ТЕЛЕГРАМ ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🖼 Найти", "🧠 Создать (ИИ)")
    bot.send_message(message.chat.id, "🤖 **Media AI Studio v6.1**\nОбновил нейросеть! Теперь ошибки 422 быть не должно.", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    if query in ["🖼 Найти", "🧠 Создать (ИИ)"]:
        bot.send_message(message.chat.id, "Напиши тему на английском (напр. *Forest fire at night*):")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📦 Сток Pexels", callback_data=f"f:{query}"),
        types.InlineKeyboardButton("🤖 Нейросеть AI", callback_data=f"g:{query}")
    )
    bot.send_message(message.chat.id, f"🎯 Твой запрос: **{query}**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "f":
        bot.send_message(chat_id, "🔎 Ищу на стоках...")
        res = VideoAI.get_stock(query)
        if res:
            bot.send_video(chat_id, res, caption=f"✅ Найдено: {query}")
            SHARED_LOGS.append({"Запрос": query, "Тип": "Сток", "Статус": "Успех"})
        else:
            bot.send_message(chat_id, "❌ Ничего не найдено.")

    elif action == "g":
        status_msg = bot.send_message(chat_id, "🚀 Нейросеть AnimateDiff запущена...\nЭто займет около 40-80 секунд.")
        bot.send_chat_action(chat_id, 'record_video')
        
        result = VideoAI.generate_ai(query)
        
        if result and not str(result).startswith("Error"):
            try:
                bot.send_video(chat_id, result, caption=f"🔥 Готово! Модель: AnimateDiff\nЗапрос: {query}")
                SHARED_LOGS.append({"Запрос": query, "Тип": "ИИ", "Статус": "Успех"})
            except:
                bot.send_message(chat_id, f"🔗 Видео готово, но файл слишком большой. Вот ссылка: {result}")
        else:
            bot.edit_message_text(f"⚠️ Ошибка API: {result}", chat_id, status_msg.message_id)
            SHARED_LOGS.append({"Запрос": query, "Тип": "ИИ", "Статус": f"Ошибка: {result}"})

# --- 4. ЗАПУСК БОТА ---

def run_bot_forever():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- 5. ИНТЕРФЕЙС STREAMLIT ---

st.title("🖥 Media AI Master Dashboard")

if "bot_thread_active" not in st.session_state:
    thread = Thread(target=run_bot_forever, daemon=True)
    thread.start()
    st.session_state.bot_thread_active = True

# Перенос логов
if SHARED_LOGS:
    for log in SHARED_LOGS:
        st.session_state.bot_history.append(log)
    SHARED_LOGS.clear()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Логи запросов")
    if st.session_state.bot_history:
        df = pd.DataFrame(st.session_state.bot_history).iloc[::-1]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Активности пока нет.")

with col2:
    st.subheader("🛠 Контроль")
    st.success("Бот Онлайн ✅")
    if st.button("Очистить историю"):
        st.session_state.bot_history = []
        st.rerun()

st.caption("v6.1: Исправлена ошибка 422. Переход на модель AnimateDiff.")
