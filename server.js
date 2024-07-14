const express = require('express');
const axios = require('axios');
const dotenv = require('dotenv');
const { DateTime } = require('luxon');
const winston = require('winston');
const TelegramBot = require('node-telegram-bot-api');

dotenv.config();  // Загружаем переменные окружения из .env

const app = express();
app.use(express.json());

const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;

// Настройка логгера
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.File({ filename: 'logs.log' }),
        new winston.transports.Console()
    ],
});

// Глобальные переменные для состояния
const lastPingTimes = {};
const lightStates = {};
const lightStartTimes = {};
const previousDurations = {};
const lightCheckInterval = 10000;  // Проверка каждые 10 секунд

// Создайте экземпляр бота
const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: true });

// Функция для отправки сообщения в Telegram
async function sendTelegramMessage(chatId, message) {
    const url = `https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`;
    logger.info(`Отправка сообщения в Telegram: ${message}`);

    try {
        await axios.post(url, { chat_id: chatId, text: message });
        logger.info(`Сообщение успешно отправлено в Telegram чату ${chatId}`);
    } catch (error) {
        logger.error(`Ошибка при отправке сообщения в Telegram: ${error.response ? error.response.data : error.message}`);
    }
}

// Функция для обновления времени последнего пинга
function updatePingTime(chatId) {
    const now = DateTime.now();
    logger.info(`Получен пинг от ${chatId}`);

    if (!lastPingTimes[chatId]) {
        lastPingTimes[chatId] = now;
        lightStates[chatId] = "включен";  
        lightStartTimes[chatId] = now; // Запоминаем время включения света
        sendTelegramMessage(chatId, `Привет! Текущий статус света: ${lightStates[chatId]}`);
    } else {
        const lastState = lightStates[chatId];

        if (lastState === "выключен") {
            const previousDuration = now.diff(lightStartTimes[chatId]);
            previousDurations[chatId] = previousDuration;
            lightStates[chatId] = "включен";  // Включаем свет
            lightStartTimes[chatId] = now; // Обновляем время включения
            sendTelegramMessage(chatId, `Свет ВКЛЮЧИЛИ.Был выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
            logger.info(`Свет включен для ${chatId}. Выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
        }

        lastPingTimes[chatId] = now;  
    }
}

// Фоновая задача для проверки состояния света
setInterval(() => {
    const now = DateTime.now();
    for (const chatId in lastPingTimes) {
        if (now.diff(lastPingTimes[chatId]).as('seconds') > 10) {  // 3 минуты
            if (lightStates[chatId] === "включен") {
                const previousDuration = now.diff(lightStartTimes[chatId]);
                previousDurations[chatId] = previousDuration;
                lightStates[chatId] = "выключен";
                lightStartTimes[chatId] = now; // Запоминаем время выключения
                sendTelegramMessage(chatId, `Свет ВЫКЛЮЧИЛИ. Был включен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
                logger.info(`Свет выключен для ${chatId}. Включен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
            }
        }
    }
}, lightCheckInterval);

app.post('/ping', (req, res) => {
    const chatId = req.body.chat_id || 'нет chat_id';
    updatePingTime(chatId);
    res.send("Ping received!");
});

app.get('/ping', (req, res) => {
    const chatId = req.query.chat_id || 'нет chat_id';
    updatePingTime(chatId);
    res.send("Ping received!");
});

// Обработчик команды /status
bot.onText(/\/status/, (msg) => {
    const chatId = msg.chat.id;  
    logger.info(`Команда /status получена от группы с chat_id ${chatId}`);

    if (!(chatId in lightStates)) {
        const message = `Данных для chat_id ${chatId} не найдено.`;
        bot.sendMessage(chatId, message);
        logger.warn(message);
        return;
    }

    const lightState = lightStates[chatId];
    const durationCurrent = DateTime.now().diff(lightStartTimes[chatId]);
    const previousDuration = previousDurations[chatId] ? previousDurations[chatId].toFormat('hh:mm:ss') : 'неизвестно';
    const responseMessage = `Свет ${lightState} на протяжении ${durationCurrent.toFormat('hh:mm:ss')}. Предущий статус длился ${previousDuration}.`;

    bot.sendMessage(chatId, responseMessage);
    logger.info(`Статус отправлен для группы ${chatId}`);
});

// Запуск сервера
const PORT = process.env.PORT || 5002;
app.listen(PORT, () => {
    const welcomeChatId = '558625598';  // Укажите нужный chat_id
    sendTelegramMessage(welcomeChatId, "Привет! Бот запущен и готов к работе!");
    logger.info(`Сервер запущен на порту ${PORT}`);
});
