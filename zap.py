import requests
import time

url = 'https://wrtping.glitch.me/ping?chat_id=558625598'

while True:
    response = requests.get(url)
    print(response.text)
    time.sleep(180)  # Ожидание 3 минуты (180 секунд)
