from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class WebDriverManager:
    def __init__(self):
        self.driver = None
        self.chrome_driver_path = "C:/Users/Admin/Desktop/chromedriver-win64/chromedriver.exe"
    
    def start_driver(self):
        if self.driver is None:
            chrome_options = Options()
            # Удалите следующую строку, чтобы браузер был видим
            # chrome_options.add_argument("--headless")
            service = Service(self.chrome_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.get("https://www.dtek-oem.com.ua/ua/shutdowns")
        return self.driver
    
    def get_driver(self):
        return self.driver
    
    def quit_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
