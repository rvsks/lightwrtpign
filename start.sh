#!/bin/bash

# Установка chromedriver
wget -N https://chromedriver.storage.googleapis.com/109.0.5414.74/chromedriver_linux64.zip
unzip chromedriver_linux64.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver

# Запуск бота
python bot.py
