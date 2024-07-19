import os
import asyncio
import sys
import io
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from flask import Flask, request, jsonify
import logging
import threading
import time
import requests

logging.basicConfig(level=logging.INFO)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
group_id = int(os.getenv('GROUP_ID'))
bot_token = os.getenv('TELEGRAM_TOKEN')
bot_target = 'DTEKOdeskiElektromerezhiBot'
string_session = os.getenv('STRING_SESSION')
monitoring_password = os.getenv('MONITORING_PASSWORD')

app = Flask(__name__)
message_queue = asyncio.Queue()
last_request_time = 0
is_processing = False  # Флаг обработки
monitoring_enabled = False  # Флаг мониторинга

loop = asyncio.get_event_loop()

async def send_message(client, message):
    try:
        sent_message = await client.send_message(bot_target, message)
        logging.info(f"Сообщение '{message}' отправлено в бот!")
        await asyncio.sleep(2)
        await client.delete_messages(bot_target, sent_message.id)
        logging.info(f"Сообщение '{message}' с ID {sent_message.id} удалено.")
        return sent_message.id
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")
        return None

async def wait_for_bot_response(client):
    logging.info("Ожидание ответа от бота...")
    while True:
        message = await client.get_messages(bot_target, limit=1)
        if message and message[0].text:
            logging.info(f"Получен ответ от бота: {message[0].text}")
            return message[0]
        await asyncio.sleep(1)

def send_message_to_group(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    response = requests.post(url, json=payload)
    return response.json()

last_dtek_request_time = 0  # Время последнего запроса /dtek

async def handle_dtek_command(client, event):
    global is_processing, last_dtek_request_time

    current_time = time.time()

    if is_processing:
        logging.info("Запрос к /dtek проигнорирован, так как он уже обрабатывается.")
        await event.delete()  # Удаляем сообщение
        return

    if current_time - last_dtek_request_time < 30:
        logging.info("Запрос к /dtek проигнорирован, так как он поступает слишком быстро.")
        await event.delete()  # Удаляем сообщение
        return

    last_dtek_request_time = current_time  # Обновляем время последнего запроса
    is_processing = True
    logging.info("Команда '/dtek' получена.")
    
    await message_queue.put("☰ Меню")
    attempts = 0

    try:
        while True:
            response_message = await wait_for_bot_response(client)
            response_text = response_message.text
            logging.info(f"Ответ от бота: {response_text}")

            # Ожидание после получения ответа
            await asyncio.sleep(2)

            if "Оберіть потрібний розділ, натиснувши кнопку нижче👇" in response_text:
                await client.delete_messages(bot_target, response_message.id)
                logging.info("Сообщение 'Оберіть потрібний розділ, натиснувши кнопку нижче👇' удалено.")

                await message_queue.put("💡Можливі відключення")

                while True:
                    response_message = await wait_for_bot_response(client)
                    response_text = response_message.text
                    logging.info(f"Ответ от бота: {response_text}")

                    # Ожидание после получения ответа
                    await asyncio.sleep(2)

                    if "Петра Ніщинського" in response_text:
                        send_message_to_group(bot_token, group_id, response_text)
                        logging.info("Ответ от бота с 'Петра Ніщинського' отправлен в группу.")
                        
                        await client.delete_messages(bot_target, response_message.id)
                        logging.info(f"Ответ от бота с ID {response_message.id} удалён.")
                        break
                    
                    elif "Повідомити про відсутність світла" in response_text:
                        send_message_to_group(bot_token, group_id, response_text)
                        logging.info("Сообщение 'Повідомити про відсутність світла' отправлено в группу.")
                        
                        await client.delete_messages(bot_target, response_message.id)
                        logging.info(f"Ответ от бота с ID {response_message.id} удалён.")
                        break
                    
                    else:
                        attempts += 1
                        logging.info("Ответ не содержит нужные фразы, проверяем снова.")
                        if attempts >= 5:
                            logging.info("Достигнуто максимальное количество попыток, завершение обработки.")
                            break
                        await asyncio.sleep(2)
                break
            else:
                attempts += 1
                logging.info("Ответ не содержит нужную фразу, проверяем снова.")
                if attempts >= 5:
                    logging.info("Достигнуто максимальное количество попыток, завершение обработки.")
                    break
                await asyncio.sleep(2)

    finally:
        is_processing = False

async def process_event(client):
    global is_processing, last_dtek_request_time, monitoring_enabled

    @client.on(events.NewMessage(chats=group_id, pattern='/dtek'))
    async def handler(event):
        if monitoring_enabled:
            await handle_dtek_command(client, event)
        else:
            logging.info("Мониторинг отключен, команда /dtek проигнорирована.")
            await event.delete()

    @client.on(events.NewMessage(chats=group_id))
    async def monitor_handler(event):
        if monitoring_enabled:
            message_text = event.message.message.lower()
            logging.info(f"Получено сообщение: {message_text}")

            if "свет выключили" in message_text:
                logging.info("Получено сообщение 'свет выключили'.")
                await handle_dtek_command(client, event)
            else:
                logging.info("Сообщение не содержит триггерной фразы.")
        else:
            logging.info("Мониторинг сообщений отключен, сообщение игнорируется.")

    @client.on(events.NewMessage(chats=group_id, pattern='/startstop'))
    async def startstop_handler(event):
        global monitoring_enabled
        message_text = event.message.message.lower()
        if monitoring_password and message_text.startswith(f'/startstop {monitoring_password}'):
            monitoring_enabled = not monitoring_enabled
            status = "включен" if monitoring_enabled else "отключен"
            await event.respond(f"Мониторинг сообщений {status}.")
            logging.info(f"Мониторинг сообщений {status}.")
        else:
            await event.respond("Неверный пароль для команды /startstop.")
            logging.info("Попытка запуска/остановки мониторинга с неверным паролем.")

async def process_queue(client):
    while True:
        message = await message_queue.get()
        await send_message(client, message)
        message_queue.task_done()

async def main():
    async with TelegramClient(StringSession(string_session), api_id, api_hash) as client:
        asyncio.create_task(process_queue(client))
        await process_event(client)
        logging.info("Слушаем новые сообщения в группе...")
        await client.run_until_disconnected()

def start_telegram_client():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

@app.route('/dtek', methods=['POST'])
def ping():
    global last_request_time
    current_time = time.time()

    if current_time - last_request_time < 60:
        logging.info("Запрос к /dtek проигнорирован, так как он поступает слишком часто.")
        return jsonify({"status": "ignored", "message": "Запрос к /dtek проигнорирован, так как он поступает слишком часто."}), 429

    last_request_time = current_time

    # Помещаем команду в очередь сообщений
    loop.create_task(message_queue.put("💡Можливі відключення"))

    logging.info("Команда '/dtek' получена.")
    return jsonify({"status": "received", "message": "Команда '/dtek' успешно обработана."}), 200

if __name__ == '__main__':
    # Запускаем клиент Telegram в отдельном потоке
    telegram_thread = threading.Thread(target=start_telegram_client)
    telegram_thread.start()
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
