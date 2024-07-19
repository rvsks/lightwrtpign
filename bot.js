import express from 'express';
import bodyParser from 'body-parser';
import TelegramBot from 'node-telegram-bot-api';
import fetch from 'node-fetch';
import dotenv from 'dotenv';

// Загрузка переменных окружения из .env файла
dotenv.config();

// Конфигурация
const TOKEN = process.env.TELEGRAM_BOT_TOKEN; // Замените на токен вашего бота
const WEBHOOK_URL = process.env.WEBHOOK_URL; // URL вашего Flask приложения
const PORT = process.env.PORT || 5000;

// Создание и настройка бота
const bot = new TelegramBot(TOKEN);
const app = express();

app.use(bodyParser.json());

// Установка вебхука
bot.setWebHook(`${WEBHOOK_URL}/${TOKEN}`);

// Обработчик текстовых сообщений
bot.on('message', async (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;

  // Пример обработки сообщений
  if (text === '/start') {
    bot.sendMessage(chatId, "Привет! Введите город, улицу и номер дома.");
  } else {
    // Взаимодействие с Flask API
    try {
      const response = await fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
      });

      const data = await response.json();
      bot.sendMessage(chatId, `Ответ от сервера: ${data.message}`);
    } catch (error) {
      bot.sendMessage(chatId, 'Ошибка при обработке запроса.');
    }
  }
});

// Обработка вебхуков
app.post(`/${TOKEN}`, (req, res) => {
  bot.processUpdate(req.body);
  res.sendStatus(200);
});

// Запуск сервера
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
