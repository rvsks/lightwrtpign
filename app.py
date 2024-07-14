from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()  # Загружаем переменные окружения из .env

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Глобальные переменные для состояния
last_ping_times = {}
light_states = {}
light_durations = {}

# Функция для отправки сообщения в Telegram
def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")

# Функция для обновления времени последнего пинга
def update_ping_time(chat_id):
    global last_ping_times, light_states, light_durations
    now = datetime.now()
    
    if chat_id not in last_ping_times:
        last_ping_times[chat_id] = now
        light_states[chat_id] = "on"
        light_durations[chat_id] = {'on': timedelta(), 'off': timedelta()}
        send_telegram_message(chat_id, f"Привет! Текущий статус света: {light_states[chat_id]}")
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

# Функция для проверки состояния света
def check_light_state():
    now = datetime.now()
    for chat_id, last_time in list(last_ping_times.items()):
        if (now - last_time).total_seconds() > 10:
            if light_states[chat_id] == "on":
                duration_on = light_durations[chat_id]['on']
                light_durations[chat_id]['on'] = timedelta()
                light_states[chat_id] = "off"
                send_telegram_message(chat_id, f"Light OFF. Light was ON for {duration_on}")

@app.route('/ping', methods=['GET', 'POST'])
def ping():
    chat_id = request.args.get('chat_id') if request.method == 'GET' else request.form.get('chat_id')
    update_ping_time(chat_id)
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
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_light_state, trigger="interval", seconds=10)
    scheduler.start()

    welcome_chat_id = '558625598'
    send_telegram_message(welcome_chat_id, "Привет! Бот запущен и готов к работе!")
    
    try:
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5002)))
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
