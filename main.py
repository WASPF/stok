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
st.set_page_config(page_title="Media AI Master: Luma Stable", layout="wide")

if 'bot_history' not in st.session_state:
    st.session_state['bot_history'] = []

# Очередь для передачи данных в Streamlit из потока бота
SHARED_LOGS = []

try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    PEXELS_KEY = st.secrets["PEXELS_API_KEY"]
    REPLICATE_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN
except Exception as e:
    st.error("Настройте SECRETS (TELEGRAM_TOKEN, PEXELS_API_KEY, REPLICATE_API_TOKEN)!")
    st.stop()

bot = telebot.TeleBot(TOKEN)

# --- 2. ENGINE (ЛОГИКА API) ---

class VideoAI:
    @staticmethod
    def get_stock(query):
        """Поиск видео на Pexels."""
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
        try:
            r = requests.get(url, headers=headers, timeout=10).json()
            vids = r.get('videos', [])
            if vids:
                return vids[0]['video_files'][0]['link']
            return None
        except: return None

    @staticmethod
    def run_luma_reframe(chat_id, video_url, prompt, status_msg_id):
        """Асинхронный запуск Luma БЕЗ жесткой привязки к версии (защита от 404)."""
        try:
            # Используем упрощенный вызов: replicate.run автоматически находит актуальную версию
            # Мы вызываем его через создание предикшена, чтобы отслеживать прогресс
            
            prediction = replicate.predictions.create(
                model="luma/reframe-video", # Используем только имя модели
                input={
                    "prompt": prompt,
                    "video_url": video_url,
                    "aspect_ratio": "9:16"
                }
            )

            start_time = time.time()
            while prediction.status not in ["succeeded", "failed", "canceled"]:
                time.sleep(10) 
                prediction.reload()
                elapsed = int(time.time() - start_time)
                
                try:
                    bot.edit_message_text(
                        f"🧬 Luma работает над вашим Reels...\n"
                        f"⏱ Прошло времени: {elapsed} сек.\n"
                        f"📊 Статус: `{prediction.status}`", 
                        chat_id, 
                        status_msg_id,
                        parse_mode="Markdown"
                    )
                except: pass
                
                if elapsed > 600: # Лимит 10 минут
                    bot.send_message(chat_id, "⚠️ Увы, Luma слишком долго думает. Попробуйте позже.")
                    return

            if prediction.status == "succeeded":
                # У модели Luma результат может быть как строкой, так и объектом
                result_url = prediction.output
                bot.send_video(chat_id, result_url, caption=f"🔥 Luma Reframe 9:16 готов!\nТема: {prompt}")
                SHARED_LOGS.append({"Запрос": prompt, "Тип": "Luma", "Статус": "Успех"})
            else:
                bot.send_message(chat_id, f"❌ Ошибка нейросети: {prediction.error}")
                SHARED_LOGS.append({"Запрос": prompt, "Тип": "Luma", "Статус": "Ошибка"})
        
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Критическая ошибка: {str(e)}")
            SHARED_LOGS.append({"Запрос": prompt, "Тип": "Luma", "Статус": "Крит. ошибка"})

# --- 3. HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎬 Начать поиск")
    bot.send_message(message.chat.id, "🛰 **Media AI Hub v7.6**\nИсправил ошибку 404. Теперь система сама находит рабочую версию Luma!", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    query = message.text
    if query == "🎬 Начать поиск":
        bot.reply_to(message, "Введите ключевое слово (на англ.):")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✨ Luma Reframe (9:16)", callback_data=f"luma:{query}"),
        types.InlineKeyboardButton("📦 Обычный Сток", callback_data=f"stock:{query}")
    )
    bot.send_message(message.chat.id, f"🎯 Твой запрос: **{query}**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    action, query = call.data.split(":", 1)
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if action == "stock":
        bot.send_message(chat_id, "🔎 Ищу видео...")
        res = VideoAI.get_stock(query)
        if res:
            bot.send_video(chat_id, res, caption=f"✅ Сток: {query}")
        else:
            bot.send_message(chat_id, "❌ Не найдено.")

    elif action == "luma":
        status_msg = bot.send_message(chat_id, "🔎 Сначала подбираю видео-исходник...")
        source_video = VideoAI.get_stock(query)
        
        if source_video:
            # Запускаем в отдельном потоке
            Thread(target=VideoAI.run_luma_reframe, args=(chat_id, source_video, query, status_msg.message_id)).start()
        else:
            bot.edit_message_text("❌ Исходное видео не найдено в Pexels.", chat_id, status_msg.message_id)

# --- 4. RUN ---

def run_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

st.title("🖥 Media AI Master Hub: Stable v7.6")

if "bot_active" not in st.session_state:
    Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_active = True

# Перенос логов в таблицу Streamlit
if SHARED_LOGS:
    for log in SHARED_LOGS:
        st.session_state.bot_history.append(log)
    SHARED_LOGS.clear()

if st.session_state.bot_history:
    st.table(pd.DataFrame(st.session_state.bot_history).iloc[::-1])
