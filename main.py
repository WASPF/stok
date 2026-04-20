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

# --- 1. ПЕРВИЧНАЯ НАСТРОЙКА ---
st.set_page_config(page_title="Media AI Master PRO", layout="wide")

if 'bot_history' not in st.session_state:
    st.session_state['bot_history'] = []

SHARED_LOGS = []

try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN
except Exception as e:
    st.error("Настройте SECRETS!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# --- 2. ENGINE ---

class VideoAI:
    @staticmethod
    def get_stock(query):
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            vids = r.get('videos', [])
            return vids[0]['video_files'][0]['link'] if vids else None
        except: return None

    @staticmethod
    def run_luma_reframe(chat_id, video_url, prompt, status_msg_id):
        """Асинхронный запуск Luma с уведомлениями."""
        try:
            # Запускаем модель
            model = replicate.models.get("luma/reframe-video")
            version = model.versions.get("e19a6d45903b708d7486e9273574c81f08e5399587440e53a251e67e9b047a0b")
            
            prediction = replicate.predictions.create(
                version=version,
                input={
                    "prompt": prompt,
                    "video_url": video_url,
                    "aspect_ratio": "9:16"
                }
            )

            # Цикл проверки статуса
            start_time = time.time()
            while prediction.status not in ["succeeded", "failed", "canceled"]:
                time.sleep(10) # Проверяем каждые 10 секунд
                prediction.reload()
                elapsed = int(time.time() - start_time)
                
                # Обновляем статус в ТГ, чтобы пользователь не скучал
                try:
                    bot.edit_message_text(f"🧬 Luma работает... (прошло {elapsed} сек.)\nСтатус: {prediction.status}", chat_id, status_msg_id)
                except: pass
                
                if elapsed > 300: # Лимит 5 минут
                    bot.send_message(chat_id, "⚠️ Время ожидания вышло. Попробуйте другой ролик.")
                    return

            if prediction.status == "succeeded":
                result_url = prediction.output
                bot.send_video(chat_id, result_url, caption=f"🔥 Luma Reframe готов!")
                SHARED_LOGS.append({"Запрос": prompt, "Тип": "Luma", "Статус": "Успех"})
            else:
                bot.send_message(chat_id, f"❌ Ошибка генерации: {prediction.error}")
        
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Критическая ошибка: {str(e)}")

# --- 3. HANDLERS ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "stock":
        res = VideoAI.get_stock(query)
        if res: bot.send_video(chat_id, res)
    
    elif action == "luma":
        status_msg = bot.send_message(chat_id, "🔎 Ищу исходное видео...")
        source_video = VideoAI.get_stock(query)
        
        if source_video:
            # Запускаем обработку в отдельном потоке, чтобы бот не вис!
            Thread(target=VideoAI.run_luma_reframe, args=(chat_id, source_video, query, status_msg.message_id)).start()
        else:
            bot.edit_message_text("❌ Видео-исходник не найден.", chat_id, status_msg.message_id)

# --- Остальной код (start, run_bot_forever, streamlit) оставляем как был ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎬 Начать поиск")
    bot.send_message(message.chat.id, "🤖 Бот обновлен. Теперь я присылаю статус работы Luma!", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✨ Luma (9:16)", callback_data=f"luma:{query}"),
               types.InlineKeyboardButton("📦 Сток", callback_data=f"stock:{query}"))
    bot.send_message(message.chat.id, f"Выбран запрос: {query}", reply_markup=markup)

def run_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

st.title("Admin Panel v7.5")
if "active" not in st.session_state:
    Thread(target=run_bot, daemon=True).start()
    st.session_state.active = True

if SHARED_LOGS:
    for log in SHARED_LOGS: st.session_state.bot_history.append(log)
    SHARED_LOGS.clear()
if st.session_state.bot_history:
    st.table(pd.DataFrame(st.session_state.bot_history))
