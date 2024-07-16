import os
import asyncio
import sys
import io
from dotenv import load_dotenv
from telethon import TelegramClient, events
from flask import Flask, request, jsonify
import logging
from threading import Thread
import time

logging.basicConfig(level=logging.INFO)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE_NUMBER')
group_id = int(os.getenv('GROUP_ID'))
bot_target = 'DTEKOdeskiElektromerezhiBot'

app = Flask(__name__)
message_queue = asyncio.Queue()
last_request_time = 0
is_processing = False  # Флаг обработки

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
    while True:
        message = await client.get_messages(bot_target, limit=1)
        if message and message[0].text:
            return message[0]
        await asyncio.sleep(1)

last_dtek_request_time = 0  # Время последнего запроса /dtek

async def process_event(client):
    global is_processing, last_dtek_request_time

    @client.on(events.NewMessage(chats=group_id, pattern='/dtek'))
    async def handler(event):
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

                if "Оберіть потрібний розділ, натиснувши кнопку нижче👇" in response_text:
                    await client.delete_messages(bot_target, response_message.id)
                    logging.info("Сообщение 'Оберіть потрібний розділ, натиснувши кнопку нижче👇' удалено.")

                    await message_queue.put("💡Можливі відключення")

                    while True:
                        response_message = await wait_for_bot_response(client)
                        response_text = response_message.text
                        logging.info(f"Ответ от бота: {response_text}")

                        if "Петра Ніщинського" in response_text:
                            await client.send_message(group_id, response_text)
                            logging.info("Ответ от бота с 'Петра Ніщинського' отправлен в группу.")
                            
                            await client.delete_messages(bot_target, response_message.id)
                            logging.info(f"Ответ от бота с ID {response_message.id} удалён.")
                            break
                        
                        elif "Повідомити про відсутність світла" in response_text:
                            await client.send_message(group_id, response_text)
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

async def process_queue(client):
    while True:
        message = await message_queue.get()
        await send_message(client, message)
        message_queue.task_done()

async def main():
    async with TelegramClient('session_file', api_id, api_hash) as client:
        asyncio.create_task(process_queue(client))
        await process_event(client)
        logging.info("Слушаем новые сообщения в группе...")
        await client.run_until_disconnected()

@app.route('/dtek', methods=['POST'])
def ping():
    global last_request_time
    current_time = time.time()

    if current_time - last_request_time < 60:
        logging.info("Запрос к /dtek проигнорирован, так как он поступает слишком часто.")
        return jsonify({"status": "ignored", "message": "Запрос к /dtek проигнорирован, так как он поступает слишком часто."}), 429

    last_request_time = current_time

    thread = Thread(target=lambda: asyncio.run(main()))
    thread.start()

    logging.info("Команда '/dtek' получена.")
    return jsonify({"status": "received", "message": "Команда '/dtek' успешно обработана."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
