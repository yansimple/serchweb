import time
import pandas as pd
import requests
import os
import logging
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

# Настройки
GOOGLE_SEARCH_API_KEY = "AIzaSyDog8YsSLLCIbTmX7o3gqDnCnXHmP6ui9I"  # Замените на ваш API ключ
GOOGLE_SEARCH_ENGINE_ID = "142dfc561543a4153"  # Замените на ваш ID поисковой системы
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
NUM_LINKS_TO_COLLECT = 400  # Количество ссылок для сбора
TIMEOUT = 30  # Таймаут загрузки сайта
CONTACT_PAGE_KEYWORDS = ['контакты', 'связаться', 'правообладатели', 'contact', 'copyright', 'contacts']  # Ключевые слова для поиска страниц с контактами
MAX_PAGES_TO_SEARCH = 5  # Максимальное количество страниц для поиска на одном сайте
DELAY_BETWEEN_REQUESTS = 2  # Задержка между запросами к Google API (в секундах)

# Настройка логгирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Функция для поиска email на странице
def find_emails_in_text(text):
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(email_regex, text)
    return emails

# Функция для поиска Telegram-ссылок на странице
def find_telegram_links_in_text(text):
    telegram_regex = r"https://t\.me/[a-zA-Z0-9_]+"
    telegram_links = re.findall(telegram_regex, text)
    return telegram_links

# Функция для поиска форм связи на странице
def find_contact_forms(soup):
    forms = []
    for form in soup.find_all('form'):
        action = form.get('action', '')
        method = form.get('method', '').lower()
        if action or method == 'post':
            forms.append(f"Форма: {action} (метод: {method})")
    return forms

# Функция для поиска контактной информации на сайте
def find_contact_info(url):
    try:
        visited_pages = set()  # Множество для отслеживания посещенных страниц
        pages_to_visit = [url]  # Очередь страниц для посещения
        contact_info = set()  # Множество для хранения найденной контактной информации

        while pages_to_visit and len(contact_info) == 0 and len(visited_pages) < MAX_PAGES_TO_SEARCH:
            current_url = pages_to_visit.pop(0)
            if current_url in visited_pages:
                continue

            logger.info(f"Поиск на странице: {current_url}")
            visited_pages.add(current_url)

            try:
                response = requests.get(current_url, timeout=TIMEOUT)
                soup = BeautifulSoup(response.text, 'html.parser')

                # Ищем email на текущей странице
                emails = find_emails_in_text(soup.get_text())
                if emails:
                    contact_info.update(emails)

                # Ищем Telegram-ссылки на текущей странице
                telegram_links = find_telegram_links_in_text(soup.get_text())
                if telegram_links:
                    contact_info.update(telegram_links)

                # Ищем формы связи на текущей странице
                forms = find_contact_forms(soup)
                if forms:
                    contact_info.update(forms)

                # Если контактная информация найдена, прекращаем поиск
                if contact_info:
                    break

                # Ищем ссылки в футере для дальнейшего поиска
                footer = soup.find('footer')
                if footer:
                    for link in footer.find_all('a', href=True):
                        internal_link = urljoin(current_url, link['href'])
                        if internal_link not in visited_pages and internal_link.startswith(url):
                            pages_to_visit.append(internal_link)

            except Exception as e:
                logger.error(f"Ошибка при обработке страницы {current_url}: {str(e)}")

        # Возвращаем найденную контактную информацию или пустую строку, если ничего не найдено
        return " ".join(contact_info) if contact_info else ""
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
        
        # Добавляем задержку между запросами, чтобы избежать превышения лимита
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    return links

# Основная функция
def main():
    query = input("Введите поисковый запрос: ")
    links = collect_links_from_google(query, NUM_LINKS_TO_COLLECT)
    
    # Собираем данные
    data = []
    for link in links:
        logger.info(f"Обработка ссылки: {link}")
        contact_info = find_contact_info(link)
        data.append({
            'Название сайта': link.split('//')[1].split('/')[0],
            'Ссылка': link,
            'Контактная информация': contact_info
        })
        logger.info(f"Контактная информация: {contact_info}")
    
    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Сортируем таблицу: сайты с найденными контактами сверху
    df['Есть контакты'] = df['Контактная информация'].apply(lambda x: 1 if x else 0)
    df = df.sort_values(by='Есть контакты', ascending=False).drop(columns=['Есть контакты'])
    
    # Сохраняем таблицу в Excel
    output_file = os.path.join(os.path.dirname(__file__), 'search_results.xlsx')
    df.to_excel(output_file, index=False, engine='openpyxl')
    logger.info(f"Результаты сохранены в файл: {output_file}")

if __name__ == "__main__":
    main()