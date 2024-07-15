const express = require('express');
const axios = require('axios');
const dotenv = require('dotenv');
const { DateTime } = require('luxon');
const winston = require('winston');
const TelegramBot = require('node-telegram-bot-api');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

dotenv.config();  // Загружаем переменные окружения из .env

const app = express();
app.use(express.json());

const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;

// Инициализация Telegram Bot
const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: true });

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

// Инициализация базы данных
const dbPath = path.resolve(__dirname, 'light_states.db');
const db = new sqlite3.Database(dbPath, (err) => {
    if (err) {
        logger.error(`Ошибка подключения к базе данных: ${err.message}`);
    } else {
        logger.info('Успешное подключение к базе данных');
    }
});

// Создание таблицы, если её ещё нет
db.serialize(() => {
    db.run(`CREATE TABLE IF NOT EXISTS light_states (
        chat_id TEXT PRIMARY KEY,
        last_ping_time TEXT,
        light_state TEXT,
        light_start_time TEXT,
        previous_duration TEXT
    )`);
});

// Функция для отправки сообщений в Telegram
function sendTelegramMessage(chatId, message) {
    bot.sendMessage(chatId, message)
        .then(() => {
            logger.info(`Сообщение отправлено: ${message}`);
        })
        .catch((error) => {
            logger.error(`Ошибка отправки сообщения: ${error}`);
        });
}

// Функция для сохранения состояния света в базу данных
function saveLightState(chatId, lastPingTime, lightState, lightStartTime, previousDuration) {
    db.run(`INSERT OR REPLACE INTO light_states (chat_id, last_ping_time, light_state, light_start_time, previous_duration) 
            VALUES (?, ?, ?, ?, ?)`,
        [chatId, lastPingTime.toISO(), lightState, lightStartTime.toISO(), previousDuration ? previousDuration.toISO() : null],
        (err) => {
            if (err) {
                logger.error(`Ошибка сохранения данных в базу: ${err.message}`);
            } else {
                logger.info(`Данные для chat_id ${chatId} сохранены в базу`);
            }
        });
}

// Функция для получения состояния света из базы данных
function getLightState(chatId, callback) {
    db.get(`SELECT * FROM light_states WHERE chat_id = ?`, [chatId], (err, row) => {
        if (err) {
            logger.error(`Ошибка чтения данных из базы: ${err.message}`);
            callback(err);
        } else {
            callback(null, row);
        }
    });
}

// Функция для обновления времени последнего пинга
function updatePingTime(chatId) {
    const now = DateTime.now();
    logger.info(`Получен пинг от ${chatId}`);

    getLightState(chatId, (err, row) => {
        if (err) {
            logger.error(`Ошибка получения данных для chat_id ${chatId}`);
            return;
        }

        if (!row) {
            const lightState = "включен";
            const lightStartTime = now;
            saveLightState(chatId, now, lightState, lightStartTime, null);
            sendTelegramMessage(chatId, `Привет! Текущий статус света: ${lightState}`);
        } else {
            const lastState = row.light_state;
            const lightStartTime = DateTime.fromISO(row.light_start_time);
            if (lastState === "выключен") {
                const previousDuration = now.diff(lightStartTime);
                saveLightState(chatId, now, "включен", now, previousDuration);
                sendTelegramMessage(chatId, `Свет ВКЛЮЧИЛИ. Был выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
                logger.info(`Свет включен для ${chatId}. Выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
            } else {
                saveLightState(chatId, now, "включен", lightStartTime, null);
            }
        }
    });
}

// Определяем интервал проверки состояния света (3 минуты)
const lightCheckInterval = 180000; // 3 минуты в миллисекундах

// Фоновая задача для проверки состояния света
setInterval(() => {
    const now = DateTime.now();
    db.all(`SELECT * FROM light_states`, [], (err, rows) => {
        if (err) {
            logger.error(`Ошибка чтения данных из базы: ${err.message}`);
            return;
        }

        rows.forEach((row) => {
            const chatId = row.chat_id;
            const lastPingTime = DateTime.fromISO(row.last_ping_time);
            if (now.diff(lastPingTime).as('seconds') > 180) {  // 3 минуты
                if (row.light_state === "включен") {
                    const lightStartTime = DateTime.fromISO(row.light_start_time);
                    const previousDuration = now.diff(lightStartTime);
                    saveLightState(chatId, now, "выключен", now, previousDuration);
                    sendTelegramMessage(chatId, `Свет ВЫКЛЮЧИЛИ. Был включен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
                    logger.info(`Свет выключен для ${chatId}. Включен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
                }
            }
        });
    });
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

    getLightState(chatId, (err, row) => {
        if (err || !row) {
            const message = `Данных для chat_id ${chatId} не найдено.`;
            bot.sendMessage(chatId, message);
            logger.warn(message);
            return;
        }

        const lightState = row.light_state;
        const durationCurrent = DateTime.now().diff(DateTime.fromISO(row.light_start_time));
        const previousDuration = row.previous_duration ? DateTime.fromISO(row.previous_duration).toFormat('hh:mm:ss') : 'неизвестно';
        const responseMessage = `Свет ${lightState} на протяжении ${durationCurrent.toFormat('hh:mm:ss')}. Предущий статус длился ${previousDuration}.`;

        bot.sendMessage(chatId, responseMessage);
        logger.info(`Статус отправлен для группы ${chatId}`);
    });
});

// Запуск сервера
const PORT = process.env.PORT || 5002;
const server = app.listen(PORT, () => {
    const address = server.address();
    const host = address.address === '::' ? 'localhost' : address.address;  // Проверяем, если адрес "::" (IPv6), заменяем на "localhost"
    const port = address.port;
    const welcomeChatId = '558625598';  // Укажите нужный chat_id
    sendTelegramMessage(welcomeChatId, `Привет! Бот запущен и готов к работе на адресе http://${host}:${port}`);
    logger.info(`Сервер запущен на адресе http://${host}:${port}`);
});
