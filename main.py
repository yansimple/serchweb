import time
import pandas as pd
import requests
import os
import logging
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

GOOGLE_SEARCH_API_KEY = "AIzaSyDog8YsSLLCIbTmX7o3gqDnCnXHmP6ui9I"
GOOGLE_SEARCH_ENGINE_ID = "142dfc561543a4153"
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
NUM_LINKS_TO_COLLECT = 400
TIMEOUT = 30
CONTACT_PAGE_KEYWORDS = ['контакты', 'связаться', 'правообладатели', 'contact', 'copyright', 'contacts']
MAX_PAGES_TO_SEARCH = 5
DELAY_BETWEEN_REQUESTS = 2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_emails_in_text(text):
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(email_regex, text)
    return emails

def find_telegram_links_in_text(text):
    telegram_regex = r"https://t\.me/[a-zA-Z0-9_]+"
    telegram_links = re.findall(telegram_regex, text)
    return telegram_links

def find_contact_forms(soup):
    forms = []
    for form in soup.find_all('form'):
        action = form.get('action', '')
        method = form.get('method', '').lower()
        if action or method == 'post':
            forms.append(f"Форма: {action} (метод: {method})")
    return forms

def find_contact_info(url):
    try:
        visited_pages = set()
        pages_to_visit = [url]
        contact_info = set()

        while pages_to_visit and len(contact_info) == 0 and len(visited_pages) < MAX_PAGES_TO_SEARCH:
            current_url = pages_to_visit.pop(0)
            if current_url in visited_pages:
                continue

            logger.info(f"Поиск на странице: {current_url}")
            visited_pages.add(current_url)

            try:
                response = requests.get(current_url, timeout=TIMEOUT)
                soup = BeautifulSoup(response.text, 'html.parser')

                emails = find_emails_in_text(soup.get_text())
                if emails:
                    contact_info.update(emails)

                telegram_links = find_telegram_links_in_text(soup.get_text())
                if telegram_links:
                    contact_info.update(telegram_links)

                forms = find_contact_forms(soup)
                if forms:
                    contact_info.update(forms)

                if contact_info:
                    break

                footer = soup.find('footer')
                if footer:
                    for link in footer.find_all('a', href=True):
                        internal_link = urljoin(current_url, link['href'])
                        if internal_link not in visited_pages and internal_link.startswith(url):
                            pages_to_visit.append(internal_link)

            except Exception as e:
                logger.error(f"Ошибка при обработке страницы {current_url}: {str(e)}")

        return " ".join(contact_info) if contact_info else ""
    except Exception as e:
        return f"Ошибка: {str(e)}"

def collect_links_from_google(query, num_links):
    links = []
    start = 1
    
    while len(links) < num_links:
        params = {
            'key': GOOGLE_SEARCH_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'start': start,
            'num': 10
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
            start += 10
        else:
            logger.error(f"Ошибка при запросе к Google API: {response.status_code}")
            break
        
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    return links

def main():
    query = input("Введите поисковый запрос: ")
    links = collect_links_from_google(query, NUM_LINKS_TO_COLLECT)
    
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
    
    df = pd.DataFrame(data)
    
    df['Есть контакты'] = df['Контактная информация'].apply(lambda x: 1 if x else 0)
    df = df.sort_values(by='Есть контакты', ascending=False).drop(columns=['Есть контакты'])
    
    output_file = os.path.join(os.path.dirname(__file__), 'search_results.xlsx')
    df.to_excel(output_file, index=False, engine='openpyxl')
    logger.info(f"Результаты сохранены в файл: {output_file}")

if __name__ == "__main__":
    main()