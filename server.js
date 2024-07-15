const express = require('express');
const dotenv = require('dotenv');
const { DateTime } = require('luxon');
const winston = require('winston');
const TelegramBot = require('node-telegram-bot-api');
const { createClient } = require('@supabase/supabase-js');

dotenv.config();

const app = express();
app.use(express.json());

const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;

const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: true });

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

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

function sendTelegramMessage(chatId, message) {
    bot.sendMessage(chatId, message)
        .then(() => {
            logger.info(`Сообщение отправлено: ${message}`);
        })
        .catch((error) => {
            logger.error(`Ошибка отправки сообщения: ${error}`);
        });
}

async function saveLightState(chatId, lastPingTime, lightState, lightStartTime, previousDuration) {
    const formattedLastPingTime = lastPingTime.toISO();  // Преобразуем в ISO формат для сохранения
    const formattedLightStartTime = lightStartTime.toISO();  // Аналогично

    let formattedPreviousDuration = null;
    if (previousDuration) {
        formattedPreviousDuration = previousDuration.toFormat("hh:mm:ss"); // Преобразуем в строку формата hh:mm:ss
    }

    const { error } = await supabase
        .from('light_states')
        .upsert({
            chat_id: chatId,
            last_ping_time: formattedLastPingTime,
            light_state: lightState,
            light_start_time: formattedLightStartTime,
            previous_duration: formattedPreviousDuration // Храним как текст
        });

    if (error) {
        logger.error(`Ошибка сохранения данных в базу: ${error.message}`);
    } else {
        logger.info(`Данные для chat_id ${chatId} сохранены в базу`);
    }
}

async function getLightState(chatId) {
    const { data, error } = await supabase
        .from('light_states')
        .select('*')
        .eq('chat_id', chatId)
        .single();

    if (error) {
        logger.error(`Ошибка чтения данных из базы: ${error.message}`);
        return null;
    }
    return data;
}

async function updatePingTime(chatId) {
    const now = DateTime.now();
    logger.info(`Получен пинг от ${chatId}`);

    const row = await getLightState(chatId);
    if (!row) {
        await saveLightState(chatId, now, true, now, null);
        sendTelegramMessage(chatId, `Привет! Свет включен.`);
    } else {
        const lastState = row.light_state;  // true/false
        const lightStartTime = DateTime.fromISO(row.light_start_time);
        if (!lastState) {  // если свет выключен
            const previousDuration = now.diff(lightStartTime);
            await saveLightState(chatId, now, true, now, previousDuration);
            sendTelegramMessage(chatId, `Свет ВКЛЮЧИЛИ. Был выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
            logger.info(`Свет включен для ${chatId}. Выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
        } else {
            // Если свет уже включен, просто обновляем время последнего пинга
            await saveLightState(chatId, now, lastState, lightStartTime, null);
        }
    }
}

const lightCheckInterval = 30000; // 10 секунд

setInterval(async () => {
    const now = DateTime.now();
    const { data: rows, error } = await supabase
        .from('light_states')
        .select('*');

    if (error) {
        logger.error(`Ошибка чтения данных из базы: ${error.message}`);
        return;
    }

    for (const row of rows) {
        const chatId = row.chat_id;
        const lastPingTime = DateTime.fromISO(row.last_ping_time);
        if (now.diff(lastPingTime).as('seconds') > 180) {  // Период проверки в секундах
            if (row.light_state) {  // если свет включен
                const lightStartTime = DateTime.fromISO(row.light_start_time);
                const previousDuration = now.diff(lightStartTime);
                await saveLightState(chatId, now, false, now, previousDuration);
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

bot.onText(/\/status/, async (msg) => {
    const chatId = msg.chat.id;  
    logger.info(`Команда /status получена от группы с chat_id ${chatId}`);

    const row = await getLightState(chatId);
    if (!row) {
        const message = `Данных для chat_id ${chatId} не найдено.`;
        bot.sendMessage(chatId, message);
        logger.warn(message);
        return;
    }

    const lightState = row.light_state ? 'включен' : 'выключен';
    const durationCurrent = DateTime.now().diff(DateTime.fromISO(row.light_start_time));
    const previousDuration = row.previous_duration || 'неизвестно';
    const responseMessage = `Свет ${lightState} на протяжении ${durationCurrent.toFormat('hh:mm:ss')}. Предыдущий статус длился ${previousDuration}.`;

    bot.sendMessage(chatId, responseMessage);
    logger.info(`Статус отправлен для группы ${chatId}`);
});

const PORT = process.env.PORT || 5002;
const server = app.listen(PORT, () => {
    const address = server.address();
    const host = address.address === '::' ? 'localhost' : address.address;
    const port = address.port;
    const welcomeChatId = '558625598';  // Укажите нужный chat_id
    sendTelegramMessage(welcomeChatId, `Привет! Бот запущен и готов к работе на адресе http://${host}:${port}`);
    logger.info(`Сервер запущен на адресе http://${host}:${port}`);
});
