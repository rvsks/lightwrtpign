#!/bin/bash

# Установка chromedriver в /tmp
wget -N https://chromedriver.storage.googleapis.com/109.0.5414.74/chromedriver_linux64.zip -P /tmp/
unzip /tmp/chromedriver_linux64.zip -d /tmp/
chmod +x /tmp/chromedriver

# Убедитесь, что путь к chromedriver правильный в bot.py
sed -i 's|/app/chromedriver/chromedriver|/tmp/chromedriver|' bot.py

# Запуск бота
python bot.py
