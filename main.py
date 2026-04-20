import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import replicate
import time
import pandas as pd

# Библиотеки для requirements.txt: 
# pyTelegramBotAPI, requests, streamlit, replicate, pandas

# --- ИНИЦИАЛИЗАЦИЯ ИЗ SECRETS ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
    
    # Настройка клиента нейросети
    replicate_client = replicate.Client(api_token=REPLICATE_TOKEN)
except Exception as e:
    st.error("Настройте SECRETS: TELEGRAM_TOKEN, PEXELS_API_KEY, REPLICATE_API_TOKEN")
    st.stop()

bot = telebot.TeleBot(TOKEN)

if 'logs' not in st.session_state:
    st.session_state.logs = []

# --- MEDIA & AI ENGINE ---

class AICreator:
    @staticmethod
    def search_pexels(query, m_type="video"):
        """Поиск готового контента."""
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            vids = r.get('videos', [])
            return vids[0]['video_files'][0]['link'] if vids else None
        except: return None

    @staticmethod
    def generate_video_ai(prompt):
        """Генерация видео через Replicate (нейросеть ZeroScope)."""
        try:
            # Используем модель ZeroScope для быстрой генерации
            output = replicate.run(
                "anotherjesse/zeroscope-v2-xl:9f742d46474161b405b5f058cf57028170e30c416e04439c74077797c774304b",
                input={
                    "prompt": prompt,
                    "num_frames": 24,
                    "fps": 8,
                    "width": 576,
                    "height": 320
                }
            )
            # Модель возвращает список ссылок, берем первую
            return output[0] if output else None
        except Exception as e:
            return f"Error: {str(e)}"

# --- BOT HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔎 Поиск", "🤖 Генерация ИИ")
    bot.send_message(message.chat.id, "🚀 **MediaScout AI** активен!\nЯ могу найти видео или СГЕНЕРИРОВАТЬ его сам.", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    if query == "🔎 Поиск":
        bot.reply_to(message, "Что найти на стоках?")
        return
    if query == "🤖 Генерация ИИ":
        bot.reply_to(message, "Опиши видео, которое мне создать (на англ.)?")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📦 Найти на Pexels", callback_data=f"find:{query}"),
        types.InlineKeyboardButton("🧠 Сгенерировать ИИ", callback_data=f"gen:{query}")
    )
    bot.send_message(message.chat.id, f"Выбран запрос: **{query}**", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_logic(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "find":
        bot.send_message(chat_id, "🔍 Ищу на стоках...")
        url = AICreator.search_pexels(query)
        if url:
            bot.send_video(chat_id, url, caption=f"✅ Найдено на Pexels: {query}")
        else:
            bot.send_message(chat_id, "❌ Ничего не найдено.")

    elif action == "gen":
        bot.send_message(chat_id, "🧪 Нейросеть начала магию... Это займет 30-60 секунд. Ждите!")
        bot.send_chat_action(chat_id, 'record_video')
        
        video_url = AICreator.generate_video_ai(query)
        
        if video_url and not str(video_url).startswith("Error"):
            bot.send_video(chat_id, video_url, caption=f"🔥 Сгенерировано ИИ: {query}")
            st.session_state.logs.append({"Запрос": query, "Тип": "Генерация", "Результат": "Успех"})
        else:
            bot.send_message(chat_id, f"⚠️ Ошибка генерации. Возможно, лимит исчерпан или запрос заблокирован.")
            st.session_state.logs.append({"Запрос": query, "Тип": "Генерация", "Результат": "Ошибка"})

# --- BACKGROUND RUN ---
def run_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

# --- STREAMLIT DASHBOARD ---
st.title("🛰 AI Video Hub Dashboard")
if "active" not in st.session_state:
    Thread(target=run_bot, daemon=True).start()
    st.session_state.active = True

st.subheader("Мониторинг нейросети")
if st.session_state.logs:
    st.table(pd.DataFrame(st.session_state.logs))
else:
    st.info("Бот ожидает запросов на генерацию...")

st.sidebar.write(f"API Token: `...{REPLICATE_TOKEN[-5:]}`")
