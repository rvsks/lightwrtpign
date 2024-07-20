import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from flask import Flask

# Загрузка переменных окружения
load_dotenv()

# Получение токена из переменной окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Инициализация состояния разговора
conversation_state = {}

async def wait_for_element(page, selector, timeout=60000):
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except TimeoutError:
        print(f"Элемент {selector} не появился вовремя.")
        return False

async def interact_with_autocomplete(page, query, input_selector, autocomplete_selector, min_length=3):
    await page.fill(input_selector, query)
    
    if not await wait_for_element(page, autocomplete_selector, timeout=5000):
        return None
    
    suggestions = await page.evaluate(f"""
        () => {{
            const items = document.querySelectorAll('{autocomplete_selector} div');
            return Array.from(items).map(item => {{
                return {{
                    text: item.textContent,
                    value: item.querySelector('input[type="hidden"]').value
                }};
            }});
        }}
    """)
    
    if suggestions and len(suggestions) == 1:
        await page.click(f"{autocomplete_selector} div")
        return [suggestions[0]]
    
    return suggestions if suggestions else None

async def get_outage_info(page):
    if await wait_for_element(page, '#showCurOutage'):
        info_element = await page.query_selector('#showCurOutage p')
        info_text = await info_element.inner_text()
        return info_text
    else:
        return "Информация об отключениях не найдена."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Добро пожаловать! Для начала поиска информации об отключениях, введите /search")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conversation_state[user_id] = {"step": "city"}
    
    p = await async_playwright().start()
    browser = await p.chromium.launch()
    page = await browser.new_page()
    
    url = "https://www.dtek-oem.com.ua/ua/shutdowns"
    await page.goto(url, timeout=120000)
    
    conversation_state[user_id]["playwright"] = p
    conversation_state[user_id]["browser"] = browser
    conversation_state[user_id]["page"] = page
    
    await update.message.reply_text("Введите город:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message_text = update.message.text

    if user_id not in conversation_state:
        await update.message.reply_text("Пожалуйста, начните поиск с команды /search")
        return

    state = conversation_state[user_id]

    if state["step"] == "city":
        await process_city(update, context, message_text)
    elif state["step"] == "street":
        await process_street(update, context, message_text)
    elif state["step"] == "house":
        await process_house(update, context, message_text)

async def process_city(update: Update, context: ContextTypes.DEFAULT_TYPE, city_query: str) -> None:
    user_id = update.effective_user.id
    state = conversation_state[user_id]
    page = state["page"]

    if len(city_query) < 3:
        await update.message.reply_text("Введите не менее 3 символов для названия города.")
        return

    suggestions = await interact_with_autocomplete(page, city_query, 'input#city', '#cityautocomplete-list', min_length=3)

    if not suggestions:
        await update.message.reply_text("Город не найден. Попробуйте еще раз.")
        return

    if len(suggestions) == 1:
        state['city'] = suggestions[0]['value']
        state['step'] = 'street'
        await update.message.reply_text(f"Выбран город: {suggestions[0]['text']}. Теперь введите улицу:")
    else:
        keyboard = [
            [InlineKeyboardButton(suggestion['text'], callback_data=f"city_{suggestion['value']}")]
            for suggestion in suggestions[:10]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите город из списка:", reply_markup=reply_markup)

async def process_street(update: Update, context: ContextTypes.DEFAULT_TYPE, street_query: str) -> None:
    user_id = update.effective_user.id
    state = conversation_state[user_id]
    page = state["page"]

    if len(street_query) < 3:
        await update.message.reply_text("Введите не менее 3 символов для названия улицы.")
        return

    street_input_selector = 'input.form__input[name="street"]'
    suggestions = await interact_with_autocomplete(page, street_query, street_input_selector, '#streetautocomplete-list', min_length=3)

    if not suggestions:
        await update.message.reply_text("Улица не найдена. Попробуйте еще раз.")
        return

    if len(suggestions) == 1:
        state['street'] = suggestions[0]['value']
        state['step'] = 'house'
        await update.message.reply_text(f"Выбрана улица: {suggestions[0]['text']}. Теперь введите номер дома:")
    else:
        keyboard = [
            [InlineKeyboardButton(suggestion['text'], callback_data=f"street_{suggestion['value']}")]
            for suggestion in suggestions[:10]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите улицу из списка:", reply_markup=reply_markup)

async def process_house(update: Update, context: ContextTypes.DEFAULT_TYPE, house_query: str) -> None:
    user_id = update.effective_user.id
    state = conversation_state[user_id]
    page = state["page"]

    house_input_selector = 'input#house_num'
    suggestions = await interact_with_autocomplete(page, house_query, house_input_selector, '#house_numautocomplete-list', min_length=1)
    
    if not suggestions:
        await update.message.reply_text("Номер дома не найден. Попробуйте еще раз.")
        return

    if len(suggestions) == 1:
        state['house'] = suggestions[0]['value']
        outage_info = await get_outage_info(page)
        address = f"{state.get('city', '')}, {state.get('street', '')}, {state.get('house', '')}"
        await update.message.reply_text(f"По адресу {address}:\n{outage_info}")
        await state["browser"].close()
        await state["playwright"].stop()
        del conversation_state[user_id]
    else:
        keyboard = [
            [InlineKeyboardButton(suggestion['text'], callback_data=f"house_{suggestion['value']}")]
            for suggestion in suggestions[:10]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите номер дома из списка:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = conversation_state[user_id]
    page = state["page"]

    if query.data.startswith("city_"):
        city_value = query.data[5:]
        await page.fill('input#city', city_value)
        await page.click('input#city')
        await page.keyboard.press('Enter')
        state['city'] = city_value
        state['step'] = 'street'
        await query.edit_message_text(f"Выбран город: {city_value}. Теперь введите улицу:")
    elif query.data.startswith("street_"):
        street_value = query.data[7:]
        street_input_selector = 'input.form__input[name="street"]'
        await page.fill(street_input_selector, street_value)
        await page.click(street_input_selector)
        await page.keyboard.press('Enter')
        state['street'] = street_value
        state['step'] = 'house'
        await query.edit_message_text(f"Выбрана улица: {street_value}. Теперь введите номер дома:")
    elif query.data.startswith("house_"):
        house_value = query.data[6:]
        house_input_selector = 'input#house_num'
        await page.fill(house_input_selector, house_value)
        await page.click(house_input_selector)
        await page.keyboard.press('Enter')
        state['house'] = house_value
        outage_info = await get_outage_info(page)
        address = f"{state.get('city', '')}, {state.get('street', '')}, {state.get('house', '')}"
        await query.edit_message_text(f"По адресу {address}:\n{outage_info}")
        await state["browser"].close()
        await state["playwright"].stop()
        del conversation_state[user_id]

# Flask app для поддержания веб-сервера
app = Flask(__name__)

@app.route('/')
def index():
    return "Telegram bot is running!"

def main() -> None:
    port = int(os.environ.get('PORT', '8443'))
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Запуск бота в отдельном потоке
    loop = asyncio.get_event_loop()
    loop.create_task(application.run_polling())

    # Запуск Flask-сервера
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
