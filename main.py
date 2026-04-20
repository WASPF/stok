import streamlit as st
import telebot
from telebot import types
import requests
import random
from threading import Thread
import replicate
import time
import pandas as pd

# requirements.txt: pyTelegramBotAPI, requests, streamlit, replicate, pandas

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
except Exception as e:
    st.error("Настройте SECRETS в Streamlit Cloud!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

if 'history' not in st.session_state:
    st.session_state.history = []

# --- MEDIA ENGINE ---

class AIStudio:
    @staticmethod
    def search_pexels(query):
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            videos = r.get('videos', [])
            return videos[0]['video_files'][0]['link'] if videos else None
        except: return None

    @staticmethod
    def generate_video(prompt):
        """Генерация через стабильную модель Stable Video Diffusion."""
        try:
            # Устанавливаем токен явно в окружение
            import os
            os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN
            
            # Попробуем модель zeroscope (она быстрее для тестов)
            # Если она не сработает, в консоли Streamlit будет видна точная ошибка
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
            # Результат — это список, берем первый элемент
            if isinstance(output, list) and len(output) > 0:
                return output[0]
            return None
        except Exception as e:
            # Выводим реальную ошибку в консоль Streamlit для диагностики
            print(f"DEBUG AI ERROR: {e}")
            return f"Error: {str(e)}"

# --- BOT LOGIC ---

@bot.message_handler(commands=['start'])
def start_bot(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🖼 Найти", "🧠 Создать ИИ")
    bot.send_message(message.chat.id, "🤖 **MediaScout AI** готов к работе!", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def router(message):
    query = message.text
    if query in ["🖼 Найти", "🧠 Создать ИИ"]:
        bot.reply_to(message, "Напиши тему (на английском):")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📦 Сток", callback_data=f"f:{query}"),
        types.InlineKeyboardButton("🤖 ИИ Генерация", callback_data=f"g:{query}")
    )
    bot.send_message(message.chat.id, f"Запрос: **{query}**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "f":
        bot.send_message(chat_id, "🔎 Ищу видео...")
        url = AIStudio.search_pexels(query)
        if url: bot.send_video(chat_id, url)
        else: bot.send_message(chat_id, "Ничего не найдено.")

    elif action == "g":
        status_msg = bot.send_message(chat_id, "🧪 Нейросеть начала работу (40-60 сек)...")
        bot.send_chat_action(chat_id, 'record_video')
        
        result = AIStudio.generate_video(query)
        
        if result and not str(result).startswith("Error"):
            bot.send_video(chat_id, result, caption=f"🔥 Готово: {query}")
            st.session_state.history.append({"Query": query, "Status": "Success"})
        else:
            error_text = "Лимит исчерпан или сервер перегружен."
            if "401" in str(result): error_text = "Ошибка токена (Unauthorized)."
            bot.edit_message_text(f"❌ Ошибка: {error_text}", chat_id, status_msg.message_id)
            st.session_state.history.append({"Query": query, "Status": f"Fail: {result}"})

# --- RUN ---
def bot_loop():
    bot.remove_webhook()
    bot.polling(none_stop=True)

st.title("🛰 AI Video Hub")
if "init" not in st.session_state:
    Thread(target=bot_loop, daemon=True).start()
    st.session_state.init = True

if st.session_state.history:
    st.write("### Логи ошибок и успехов")
    st.dataframe(pd.DataFrame(st.session_state.history))
