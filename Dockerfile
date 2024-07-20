# Используйте официальный образ Python как базовый образ
FROM python:3.11

# Установите рабочий каталог
WORKDIR /app

# Скопируйте файл с зависимостями
COPY requirements.txt requirements.txt

# Установите зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Установите Playwright и его браузеры
RUN pip install playwright
RUN playwright install

# Скопируйте все файлы проекта в контейнер
COPY . .

# Команда для запуска вашего приложения
CMD ["python", "main.py"]
