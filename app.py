import requests
import time
import os
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import threading

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
user_ips = {}  # Словарь для хранения chat_id и соответствующего IP

# Настройка логирования
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    requests.post(url, data=data)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {'offset': offset}
    response = requests.get(url, params=params)
    return response.json()

@app.route('/user_ips', methods=['GET'])
def view_user_ips():
    return jsonify(user_ips)

@app.route('/ping', methods=['GET'])
def ping():
    ip = request.args.get('ip')
    if ip:
        chat_id = next((chat_id for chat_id, user_ip in user_ips.items() if user_ip == ip), None)
        if chat_id:
            send_telegram_message(chat_id, f"Получен ping от IP: {ip}")
            return "Ping received and message sent.", 200
        else:
            return "No chat_id found for this IP.", 404
    return "IP address is required.", 400

def main():
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates.get('result', []):
            offset = update['update_id'] + 1
            chat_id = update['message']['chat']['id']
            command = update['message'].get('text', '')

            if command == '/start':
                send_telegram_message(chat_id, "Пожалуйста, введите ваш IP-адрес.")
                logging.info(f"User {chat_id} started the conversation.")
            elif command.count('.') == 3 and all(part.isdigit() for part in command.split('.')):  # Проверка формата IP
                user_ips[chat_id] = command  # Сохраняем IP-адрес
                send_telegram_message(chat_id, f"Ваш IP-адрес {command} сохранен.")
                logging.info(f"User {chat_id} saved IP: {command}.")
            else:
                send_telegram_message(chat_id, "Команда не распознана. Пожалуйста, введите ваш IP-адрес.")
                logging.warning(f"User {chat_id} sent an unrecognized command: {command}.")

        time.sleep(1)  # Задержка перед следующим опросом

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000}, daemon=True).start()
    main()
