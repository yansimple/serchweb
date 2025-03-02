import time
import pandas as pd
import requests
import os
import logging
from bs4 import BeautifulSoup
import re

# Настройки
GOOGLE_SEARCH_API_KEY = "AIzaSyDog8YsSLLCIbTmX7o3gqDnCnXHmP6ui9I"  # Замените на ваш API ключ
GOOGLE_SEARCH_ENGINE_ID = "142dfc561543a4153"  # Замените на ваш ID поисковой системы
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
NUM_LINKS_TO_COLLECT = 300  # Количество ссылок для сбора
TIMEOUT = 30  # Таймаут загрузки сайта

# Настройка логгирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Функция для поиска контактной почты на странице
def find_contact_email(url):
    try:
        response = requests.get(url, timeout=TIMEOUT)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Регулярное выражение для поиска email
        email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        emails = re.findall(email_regex, soup.get_text())

        # Возвращаем первый найденный email или сообщение, если email не найден
        return emails[0] if emails else "Почта не найдена"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# Функция для сбора ссылок с выдачи Google
def collect_links_from_google(query, num_links):
    links = []
    start = 1  # Начальный индекс для пагинации
    
    while len(links) < num_links:
        params = {
            'key': GOOGLE_SEARCH_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'start': start,
            'num': 10  # Максимальное количество результатов за один запрос
        }
        
        response = requests.get(GOOGLE_SEARCH_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            for item in data.get('items', []):
                link = item.get('link')
                if link and link not in links:
                    links.append(link)
                    if len(links) >= num_links:
                        break
            start += 10  # Переход к следующей странице результатов
        else:
            logger.error(f"Ошибка при запросе к Google API: {response.status_code}")
            break
    
    return links

# Основная функция
def main():
    query = input("Введите поисковый запрос: ")
    links = collect_links_from_google(query, NUM_LINKS_TO_COLLECT)
    
    # Собираем данные
    data = []
    for link in links:
        logger.info(f"Обработка ссылки: {link}")
        contact_email = find_contact_email(link)
        data.append({
            'Название сайта': link.split('//')[1].split('/')[0],
            'Ссылка': link,
            'Контактная почта': contact_email
        })
        logger.info(f"Контактная почта: {contact_email}")
    
    # Создаем таблицу
    df = pd.DataFrame(data)
    
    # Сохраняем таблицу в текущей директории
    output_file = os.path.join(os.path.dirname(__file__), 'search_results.csv')
    df.to_csv(output_file, index=False, encoding='utf-8')
    logger.info(f"Результаты сохранены в файл: {output_file}")

if __name__ == "__main__":
    main()