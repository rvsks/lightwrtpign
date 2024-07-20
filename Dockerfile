# Используйте официальный образ Python как базовый образ
FROM python:3.11-slim

# Установите необходимые библиотеки
RUN apt-get update && apt-get install -y \
    libicu-dev \
    libevent-dev \
    libjpeg-dev \
    libenchant-dev \
    libsecret-1-dev \
    libffi-dev \
    libgles2-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

# Установите зависимости Python
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Установите Playwright и его браузеры
RUN pip install playwright
RUN playwright install

# Скопируйте все файлы проекта в контейнер
COPY . .

# Команда для запуска вашего приложения
CMD ["python", "main.py"]
