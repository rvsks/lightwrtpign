import express from 'express';
import { DateTime } from 'luxon';
import winston from 'winston';
import TelegramBot from 'node-telegram-bot-api';
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(express.json());
app.use(express.static('public'));

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

export async function getProfileLink(chatId) {
    const url = `https://api.telegram.org/bot${TELEGRAM_TOKEN}/getChat?chat_id=${chatId}`;
    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.ok) {
            const user = data.result;
            return user.username ? `https://t.me/${user.username}` : null;
        } else {
            throw new Error(data.description);
        }
    } catch (error) {
        throw new Error(error.message);
    }
}

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);

async function sendTelegramMessage(chatId, message) {
    return bot.sendMessage(chatId, message)
        .then(() => logger.info(`Сообщение отправлено: ${message}`))
        .catch((error) => logger.error(`Ошибка отправки сообщения: ${error}`));
}

async function saveLightState(chatId, lastPingTime, lightState, lightStartTime, previousDuration, profileUrl) {
    const { error } = await supabase
        .from('light_states')
        .upsert({
            chat_id: chatId,
            last_ping_time: lastPingTime ? lastPingTime.toISO() : null,
            light_state: lightState,
            light_start_time: lightStartTime ? lightStartTime.toISO() : null,
            previous_duration: previousDuration ? previousDuration.toFormat("hh:mm:ss") : null,
            profile_url: profileUrl
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
        const profileLink = await getProfileLink(chatId);
        await saveLightState(chatId, now, true, now, null, profileLink);
        return sendTelegramMessage(chatId, `Привет! Свет включен.`);
    }

    const lightStartTime = DateTime.fromISO(row.light_start_time);

    if (row.light_state) {  // Если свет уже включен
        await saveLightState(chatId, now, true, lightStartTime, row.previous_duration ? DateTime.fromISO(row.previous_duration) : null);
    } else {  // Если свет выключен
        const previousDuration = now.diff(lightStartTime);
        await saveLightState(chatId, now, true, now, previousDuration);
        await sendTelegramMessage(chatId, `Свет ВКЛЮЧИЛИ. Был выключен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
    }
}

const lightCheckInterval = 30000; // Период проверки в миллисекундах

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
        
        if (now.diff(lastPingTime).as('seconds') > 180 && row.light_state) {  // Если свет включен
            const lightStartTime = DateTime.fromISO(row.light_start_time);
            const previousDuration = now.diff(lightStartTime);
            await saveLightState(chatId, now, false, now, previousDuration);
            await sendTelegramMessage(chatId, `Свет ВЫКЛЮЧИЛИ. Был включен на протяжении ${previousDuration.toFormat('hh:mm:ss')}.`);
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

// Обработка текстовых сообщений
bot.on('message', async (msg) => {
    const chatId = msg.chat.id;

    const row = await getLightState(chatId);
    if (!row) {
        const profileLink = await getProfileLink(chatId); // Получаем ссылку на профиль
        await saveLightState(chatId, null, null, null, null, profileLink); // Сохраняем только профиль
        sendTelegramMessage(chatId, `Привет! Ваш профиль: ${profileLink}`);
    }
});

bot.onText(/\/status/, async (msg) => {
    const chatId = msg.chat.id;
    logger.info(`Команда /status получена от группы с chat_id ${chatId}`);

    const row = await getLightState(chatId);
    if (!row) {
        return bot.sendMessage(chatId, `Данных для chat_id ${chatId} не найдено.`);
    }

    const lightState = row.light_state ? 'включен' : 'выключен';
    const durationCurrent = DateTime.now().diff(DateTime.fromISO(row.light_start_time));
    const previousDuration = row.previous_duration || 'неизвестно';
    const responseMessage = `Свет ${lightState} на протяжении ${durationCurrent.toFormat('hh:mm:ss')}. Предыдущий статус длился ${previousDuration}.`;

    bot.sendMessage(chatId, responseMessage);
    logger.info(`Статус отправлен для группы ${chatId}`);
});

const PORT = process.env.PORT || 5002;
app.listen(PORT, () => {
    logger.info(`Сервер запущен на порту ${PORT}`);
    sendTelegramMessage('558625598', `Привет! Бот запущен и готов к работе`);
});
