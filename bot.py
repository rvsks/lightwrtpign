import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение токена из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Путь к ChromeDriver
chrome_driver_path = "/app/chromedriver/chromedriver"  # Замените на путь, который у вас будет на Render

# Этапы для ConversationHandler
CITY, STREET, HOUSE_NUM = range(3)

# Глобальная переменная для WebDriver
driver = None

# Функция для создания кнопок
def create_buttons(options):
    keyboard = [[InlineKeyboardButton(option, callback_data=option)] for option in options]
    return InlineKeyboardMarkup(keyboard)

# Функция для получения предложений из автокомплита
def get_suggestions(input_element, driver):
    try:
        input_element.send_keys("")  # Обновляем список предложений

        # Ожидание появления списка автозаполнения
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.autocomplete-items"))
        )
        
        autocomplete_list = driver.find_element(By.CSS_SELECTOR, "div.autocomplete-items")
        options = autocomplete_list.find_elements(By.TAG_NAME, "div")
        
        suggestions = []
        for option in options:
            hidden_input = option.find_element(By.TAG_NAME, "input")
            suggestions.append(hidden_input.get_attribute("value"))
        
        return suggestions
    
    except Exception as e:
        raise RuntimeError(f"Ошибка при получении предложений: {e}")

# Функция для выбора элемента из автозаполнения
def select_autocomplete_option(option_text, input_element, driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.autocomplete-items"))
        )
        
        autocomplete_list = driver.find_element(By.CSS_SELECTOR, "div.autocomplete-items")
        options = autocomplete_list.find_elements(By.TAG_NAME, "div")
        
        # Поиск и клик по элементу с нужным текстом
        for option in options:
            if option_text.lower() in option.text.lower():
                option.click()
                time.sleep(2)  # Увеличил паузу для обновления информации
                return True
        
        raise ValueError("Не найдено подходящих вариантов")
    
    except Exception as e:
        raise RuntimeError(f"Ошибка при выборе автозаполнения: {e}")

# Функция для обработки выбора пользователя
async def handle_user_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, input_type: str) -> int:
    query = update.callback_query
    selected_value = query.data
    await query.answer()  # Ожидание асинхронного ответа
    
    user_data = context.user_data
    if input_type == "city":
        user_data['city'] = selected_value
        await query.message.reply_text("Введите улицу:")
        return STREET
    elif input_type == "street":
        user_data['street'] = selected_value
        await query.message.reply_text("Введите номер дома:")
        return HOUSE_NUM
    elif input_type == "house_num":
        user_data['house_num'] = selected_value
        await query.message.reply_text(f"Номер дома выбран: {selected_value}. Процесс завершён.")
        return ConversationHandler.END
    else:
        await query.message.reply_text("Неизвестное состояние. Попробуйте начать процесс заново.")
        return ConversationHandler.END

# Функция для завершения сеанса
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global driver
    if driver:
        driver.quit()  # Закрытие WebDriver при отмене сеанса
        driver = None
    await update.message.reply_text("Сеанс завершён. Браузер закрыт.")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global driver
    if driver is None or driver.session_id is None:
        # Запуск WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Запуск Chrome в безголовом режиме
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        service = Service(chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get("https://www.dtek-oem.com.ua/ua/shutdowns")
    
    await update.message.reply_text("Введите город:")
    return CITY

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    user_data['city'] = update.message.text
    city = user_data['city']
    
    try:
        city_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "city"))
        )
        city_input.clear()
        city_input.send_keys(city)
        
        suggestions = get_suggestions(city_input, driver)
        
        if not suggestions:
            await update.message.reply_text("Не удалось найти предложения для города. Попробуйте ввести город ещё раз:")
            return CITY
        elif len(suggestions) == 1:
            user_data['city'] = suggestions[0]
            select_autocomplete_option(suggestions[0], city_input, driver)
            await update.message.reply_text(f"Выбран город: {suggestions[0]}. Введите улицу:")
            return STREET
        else:
            keyboard = create_buttons(suggestions)
            await update.message.reply_text("Выберите город из предложенных вариантов:", reply_markup=keyboard)
            return STREET
    except Exception as e:
        await update.message.reply_text(f"Ошибка при выборе города: {e}. Попробуйте ввести город еще раз.")
        return CITY

async def set_street(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    user_data['street'] = update.message.text
    street = user_data['street']
    
    try:
        street_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "street"))
        )
        street_input.clear()
        street_input.send_keys(street)
        
        suggestions = get_suggestions(street_input, driver)
        
        if not suggestions:
            await update.message.reply_text("Не удалось найти предложения для улицы. Попробуйте ввести улицу ещё раз:")
            return STREET
        elif len(suggestions) == 1:
            user_data['street'] = suggestions[0]
            select_autocomplete_option(suggestions[0], street_input, driver)
            await update.message.reply_text(f"Выбрана улица: {suggestions[0]}. Введите номер дома:")
            return HOUSE_NUM
        else:
            keyboard = create_buttons(suggestions)
            await update.message.reply_text("Выберите улицу из предложенных вариантов:", reply_markup=keyboard)
            return HOUSE_NUM
    except Exception as e:
        await update.message.reply_text(f"Ошибка при выборе улицы: {e}. Попробуйте ввести улицу еще раз.")
        return STREET

async def set_house_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    user_data['house_num'] = update.message.text
    house_num = user_data['house_num']
    
    try:
        house_num_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "house_num"))
        )
        house_num_input.clear()
        house_num_input.send_keys(house_num)
        
        suggestions = get_suggestions(house_num_input, driver)
        
        if not suggestions:
            await update.message.reply_text(f"Не удалось найти предложения для номера дома. Процесс завершён.")
            return ConversationHandler.END
        elif len(suggestions) == 1:
            user_data['house_num'] = suggestions[0]
            select_autocomplete_option(suggestions[0], house_num_input, driver)
            await update.message.reply_text(f"Выбран номер дома: {suggestions[0]}. Получение информации об отключениях...")
        else:
            keyboard = create_buttons(suggestions)
            await update.message.reply_text("Выберите номер дома из предложенных вариантов:", reply_markup=keyboard)
            return ConversationHandler.END

        # Проверка статуса отключений после выбора номера дома
        try:
            outage_info = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "showCurOutage"))
            ).text
            await update.message.reply_text(f"Информация по вашему адресу:\n{outage_info}")
        except Exception as e:
            await update.message.reply_text(f"Не удалось получить информацию об отключениях: {e}")
        
        return ConversationHandler.END
    
    except Exception as e:
        await update.message.reply_text(f"Ошибка при выборе номера дома: {e}. Попробуйте ввести номер дома еще раз.")
        return HOUSE_NUM

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    query_data = query.data
    user_data = context.user_data

    try:
        if 'city' in user_data:
            city_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "city"))
            )
            select_autocomplete_option(query_data, city_input, driver)
            await handle_user_choice(update, context, 'city')
        elif 'street' in user_data:
            street_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "street"))
            )
            select_autocomplete_option(query_data, street_input, driver)
            await handle_user_choice(update, context, 'street')
        elif 'house_num' in user_data:
            house_num_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "house_num"))
            )
            select_autocomplete_option(query_data, house_num_input, driver)
            await handle_user_choice(update, context, 'house_num')
        
        await query.answer()  # Ожидание асинхронного ответа
    
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке выбора: {e}")

# Функция для обработки команды /dtek
async def dtek(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data

    if 'city' in user_data and 'street' in user_data and 'house_num' in user_data:
        city = user_data['city']
        street = user_data['street']
        house_num = user_data['house_num']

        try:
            city_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "city"))
            )
            street_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "street"))
            )
            house_num_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "house_num"))
            )
            
            city_input.clear()
            city_input.send_keys(city)
            select_autocomplete_option(city, city_input, driver)

            street_input.clear()
            street_input.send_keys(street)
            select_autocomplete_option(street, street_input, driver)

            house_num_input.clear()
            house_num_input.send_keys(house_num)
            select_autocomplete_option(house_num, house_num_input, driver)

            # Проверка статуса отключений после выбора номера дома
            try:
                outage_info = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "showCurOutage"))
                ).text
                await update.message.reply_text(f"Информация по вашему адресу:\n{outage_info}")
            except Exception as e:
                await update.message.reply_text(f"Не удалось получить информацию об отключениях: {e}")

        except Exception as e:
            await update.message.reply_text(f"Ошибка при запросе информации о статусе отключений: {e}")
    else:
        await update.message.reply_text("Адрес не установлен. Введите свой адрес, используя команду /start.")

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    address_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_city)],
            STREET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_street)],
            HOUSE_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_house_num)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(address_conv)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler('dtek', dtek))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
