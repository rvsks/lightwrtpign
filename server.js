const express = require('express');
const axios = require('axios');
const dotenv = require('dotenv');
const { DateTime, Duration } = require('luxon');
const winston = require('winston');

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
const lightDurations = {};
const lightCheckInterval = 10000;  // Проверка каждые 10 секунд

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
        lightStates[chatId] = "on";
        lightDurations[chatId] = { on: Duration.fromMillis(0), off: Duration.fromMillis(0) };

        // Отправляем сообщение со статусом света
        sendTelegramMessage(chatId, `Привет! Текущий статус света: ${lightStates[chatId]}`);
    } else {
        const lastPingTime = lastPingTimes[chatId];
        const duration = now.diff(lastPingTime);
        const state = lightStates[chatId];
        lightDurations[chatId][state] = lightDurations[chatId][state].plus(duration);
        lastPingTimes[chatId] = now;

        if (lightStates[chatId] === "off") {
            const durationOff = lightDurations[chatId]['off'];
            lightDurations[chatId]['off'] = Duration.fromMillis(0);
            lightStates[chatId] = "on";
            sendTelegramMessage(chatId, `Свет ВКЛЮЧИЛИ. Свет был ВЫКЛЮЧЕН ${durationOff.toFormat('hh:mm:ss')}`);
            logger.info(`Свет включен для ${chatId}. Свет был выключен на ${durationOff.toFormat('hh:mm:ss')}`);
        }
    }
}

// Фоновая задача для проверки состояния света
setInterval(() => {
    const now = DateTime.now();
    for (const chatId in lastPingTimes) {
        if (now.diff(lastPingTimes[chatId]).as('seconds') > 180) {  // 3 минуты
            if (lightStates[chatId] === "on") {
                const durationOn = lightDurations[chatId]['on'];
                lightDurations[chatId]['on'] = Duration.fromMillis(0);
                lightStates[chatId] = "off";
                sendTelegramMessage(chatId, `Свет ВЫКЛЮЧИЛИ. Свет был Включен на протяжении  ${durationOn.toFormat('hh:mm:ss')}`);
                logger.info(`Свет выключен для ${chatId}. Свет был включен на протяжении ${durationOn.toFormat('hh:mm:ss')}`);
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

app.get('/status', (req, res) => {
    const chatId = req.query.chat_id;
    if (!(chatId in lightStates)) {
        logger.warn(`chat_id ${chatId} не найден`);
        return res.status(404).json({ error: "chat_id not found" });
    }

    const statusInfo = {
        chat_id: chatId,
        last_ping_time: lastPingTimes[chatId].toFormat('yyyy-MM-dd HH:mm:ss'),
        light_state: lightStates[chatId],
        light_durations: {
            on: lightDurations[chatId]['on'].toFormat('hh:mm:ss'),
            off: lightDurations[chatId]['off'].toFormat('hh:mm:ss')
        }
    };
    logger.info(`Статус для ${chatId}: ${JSON.stringify(statusInfo)}`);
    res.json(statusInfo);
});

// Запуск сервера
const PORT = process.env.PORT || 5002;
app.listen(PORT, () => {
    // Отправляем приветственное сообщение
    const welcomeChatId = '558625598';  // Укажите нужный chat_id
    sendTelegramMessage(welcomeChatId, "Привет! Бот запущен и готов к работе!");
    logger.info(`Сервер запущен на порту ${PORT}`);
});
