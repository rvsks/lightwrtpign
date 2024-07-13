from flask import Flask, request, jsonify
import requests
import os
import sqlite3
from dotenv import load_dotenv
from datetime import datetime, timedelta
import threading
import time

load_dotenv()  # Загружаем переменные окружения из .env

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
light_check_interval = int(os.getenv('LIGHT_CHECK_INTERVAL', 30))  
ping_timeout = int(os.getenv('PING_TIMEOUT', 30)) 

# Глобальные переменные для состояния
last_ping_times = {}
light_states = {}
light_durations = {}
light_check_interval = 60  # Проверка каждые 10 секунд

# Функция для отправки сообщения в Telegram
def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    requests.post(url, data=data)

# Функция для обновления времени последнего пинга
def update_ping_time(chat_id):
    global last_ping_times, light_states, light_durations
    now = datetime.now()
    
    if chat_id not in last_ping_times:
        last_ping_times[chat_id] = now
        light_states[chat_id] = "on"
        light_durations[chat_id] = {'on': timedelta(), 'off': timedelta()}

        # Отправляем статус света новому chat_id
        send_telegram_message(chat_id, "Welcome! Your light status is currently ON.")
        print(f"[{now}] New chat_id: {chat_id} - Light ON")
    else:
        last_ping_time = last_ping_times[chat_id]
        duration = now - last_ping_time
        state = light_states[chat_id]
        light_durations[chat_id][state] += duration
        last_ping_times[chat_id] = now

    if light_states[chat_id] == "off":
        duration_off = light_durations[chat_id]['off']
        light_durations[chat_id]['off'] = timedelta()
        light_states[chat_id] = "on"
        send_telegram_message(chat_id, f"Light ON. Light was OFF for {duration_off}")
        print(f"[{now}] Light ON for {chat_id}. Light was OFF for {duration_off}")

# Фоновая задача для проверки состояния света
def check_light_state():
    while True:
        now = datetime.now()
        for chat_id, last_time in list(last_ping_times.items()):
            if (now - last_time).total_seconds() > ping_timeout:  # Используйте переменную ping_timeout
                if light_states[chat_id] == "on":
                    duration_on = light_durations[chat_id]['on']
                    light_durations[chat_id]['on'] = timedelta()
                    light_states[chat_id] = "off"
                    send_telegram_message(chat_id, f"Light OFF. Light was ON for {duration_on}")
                    print(f"[{now}] Light OFF for {chat_id}. Light was ON for {duration_on}")
        time.sleep(light_check_interval)  # Используйте переменную light_check_interval

@app.route('/ping', methods=['GET', 'POST'])
def ping():
    if request.method == 'GET':
        chat_id = request.args.get('chat_id', 'нет chat_id')
    else:  # POST
        chat_id = request.form.get('chat_id', 'нет chat_id')
    
    update_ping_time(chat_id)  # Обновляем время последнего пинга
    return "Ping received!", 200

@app.route('/status', methods=['GET'])
def status():
    chat_id = request.args.get('chat_id')
    if chat_id not in light_states:
        return jsonify({"error": "chat_id not found"}), 404
    
    status_info = {
        "chat_id": chat_id,
        "last_ping_time": last_ping_times.get(chat_id).strftime('%Y-%m-%d %H:%M:%S'),
        "light_state": light_states[chat_id],
        "light_durations": {
            "on": str(light_durations[chat_id]['on']),
            "off": str(light_durations[chat_id]['off'])
        }
    }
    return jsonify(status_info)

if __name__ == '__main__':
    threading.Thread(target=check_light_state, daemon=True).start()
    app.run(debug=True)
