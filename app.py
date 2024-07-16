import os
import asyncio
import sys
import io
from dotenv import load_dotenv
from telethon import TelegramClient, events
from flask import Flask, request, jsonify
import logging
from threading import Thread

logging.basicConfig(level=logging.INFO)
# Устанавливаем кодировку для вывода в консоль
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Загружаем переменные окружения из файла .env
load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE_NUMBER')
group_id = int(os.getenv('GROUP_ID'))
bot_target = 'DTEKOdeskiElektromerezhiBot'  # Имя бота

app = Flask(__name__)

async def send_message(client, message):
    try:
        sent_message = await client.send_message(bot_target, message)
        logging.info(f"Сообщение '{message}' отправлено в бот!")
        await asyncio.sleep(2)  # Пауза 2 секунды
        return sent_message.id
    except Exception as e:
        logging.info(f"Ошибка при отправке сообщения: {e}")
        return None

async def wait_for_bot_response(client):
    while True:
        message = await client.get_messages(bot_target, limit=1)
        if message and message[0].text:
            return message[0]
        await asyncio.sleep(1)  # Ожидание 1 секунда

async def process_event(client):
    @client.on(events.NewMessage(chats=group_id, pattern='/dtek'))
    async def handler(event):
        logging.info("Команда '/dtek' получена.")
        
        # Отправляем "☰ Меню"
        sent_menu_message_id = await send_message(client, "☰ Меню")
        if sent_menu_message_id is not None:
            await client.delete_messages(bot_target, sent_menu_message_id)
            logging.info(f"Сообщение '☰ Меню' с ID {sent_menu_message_id} удалено.")

        # Ждем ответа от бота
        while True:
            response_message = await wait_for_bot_response(client)
            response_text = response_message.text
            logging.info(f"Ответ от бота: {response_text}")

            if "Оберіть потрібний розділ, натиснувши кнопку нижче👇" in response_text:
                await client.delete_messages(bot_target, response_message.id)
                logging.info("Сообщение 'Оберіть потрібний розділ, натиснувши кнопку нижче👇' удалено.")

                # Отправляем "💡Можливі відключення"
                sent_vydkl_message_id = await send_message(client, "💡Можливі відключення")
                if sent_vydkl_message_id is not None:
                    await client.delete_messages(bot_target, sent_vydkl_message_id)
                    logging.info(f"Сообщение '💡Можливі відключення' с ID {sent_vydkl_message_id} удалено.")

                # Ждем ответа от бота после отправки "💡Можливі відключення"
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
                        logging.info("Ответ не содержит нужные фразы, проверяем снова.")
                break
            else:
                logging.info("Ответ не содержит нужную фразу, проверяем снова.")

async def main():
    async with TelegramClient('session_name', api_id, api_hash) as client:
        await process_event(client)
        logging.info("Слушаем новые сообщения в группе...")
        await client.run_until_disconnected()

@app.route('/dtek', methods=['POST'])
def ping():
    thread = Thread(target=lambda: asyncio.run(main()))
    thread.start()

    # Ответ при успешном выполнении
    logging.info("Команда '/dtek' получена.")
    return jsonify({"status": "received", "message": "Команда '/dtek' успешно обработана."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
