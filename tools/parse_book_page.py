
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

import xml.etree.ElementTree as ET
from html import unescape
import re

from src.constants import FLIBUSTA_BASE_URL


def get_fb2_info_with_selenium(book_id: str):
    """
    Использует Selenium для получения FB2 метаданных
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        url = f"{FLIBUSTA_BASE_URL}/b/{book_id}"
        driver.get(url)

        # Ждем загрузки
        time.sleep(2)

        # Ищем и кликаем кнопку
        fb2_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "fb2info.icon-open"))
        )
        fb2_button.click()

        # Ждем загрузки контента
        time.sleep(1)

        # Получаем содержимое
        content_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fb2info-content"))
        )

        return content_div.get_attribute("innerHTML")

    except Exception as e:
        print(f"Ошибка Selenium: {e}")
        return None
    finally:
        driver.quit()


import xml.etree.ElementTree as ET
from html import unescape
import re


def parse_fb2_metadata_from_html(html_content: str):
    """
    Парсит FB2 метаданные из HTML содержимого
    """
    try:
        # Извлекаем XML из HTML
        xml_match = re.search(r'&lt;(description&gt;.*?&lt;/description&gt;)', html_content, re.DOTALL)
        if not xml_match:
            print("XML не найден в HTML")
            return None

        # Декодируем HTML entities
        xml_content = unescape(xml_match.group(1))

        # Заменяем &lt; и &gt; на настоящие теги
        xml_content = xml_content.replace('&lt;', '<').replace('&gt;', '>')

        # Добавляем недостающий открывающий тег <description>
        if not xml_content.startswith('<description>'):
            xml_content = '<description>' + xml_content

        print("Исправленный XML:")
        print(xml_content[:500] + "..." if len(xml_content) > 500 else xml_content)

        # Парсим XML
        root = ET.fromstring(xml_content)

        # Извлекаем данные из publish-info
        publish_info = root.find('.//publish-info')
        metadata = {}

        if publish_info is not None:
            metadata['year'] = publish_info.findtext('year')
            metadata['isbn'] = publish_info.findtext('isbn')
            metadata['city'] = publish_info.findtext('city')
            metadata['publisher'] = publish_info.findtext('publisher')
            metadata['book_name'] = publish_info.findtext('book-name')

        # Извлекаем данные из title-info
        title_info = root.find('.//title-info')
        if title_info is not None:
            metadata['title'] = title_info.findtext('book-title')
            metadata['lang'] = title_info.findtext('lang')

            # Автор
            author = title_info.find('.//author')
            if author is not None:
                metadata['author'] = {
                    'first_name': author.findtext('first-name'),
                    'last_name': author.findtext('last-name')
                }

            # Жанры
            genres = [genre.text for genre in title_info.findall('genre')]
            if genres:
                metadata['genres'] = genres

        # Извлекаем данные из document-info
        doc_info = root.find('.//document-info')
        if doc_info is not None:
            metadata['date'] = doc_info.findtext('date')
            metadata['version'] = doc_info.findtext('version')

        return {k: v for k, v in metadata.items() if v is not None}

    except ET.ParseError as e:
        print(f"Ошибка парсинга XML: {e}")
        if 'xml_content' in locals():
            print(f"Проблемный XML (первые 200 символов):")
            print(xml_content[:200])
        return None
    except Exception as e:
        print(f"Ошибка обработки данных: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_metadata_with_regex(html_content: str):
    """
    Извлекает метаданные с помощью регулярных выражений
    """
    # Декодируем HTML entities
    text = unescape(html_content)
    text = text.replace('&lt;', '<').replace('&gt;', '>')

    metadata = {}

    # Шаблоны для поиска
    patterns = {
        'year': r'<year>([^<]+)</year>',
        'isbn': r'<isbn>([^<]+)</isbn>',
        'city': r'<city>([^<]+)</city>',
        'publisher': r'<publisher>([^<]+)</publisher>',
        'title': r'<book-title>([^<]+)</book-title>',
        'author_first_name': r'<first-name>([^<]+)</first-name>',
        'author_last_name': r'<last-name>([^<]+)</last-name>'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            metadata[key] = match.group(1)

    # Собираем автора
    if 'author_first_name' in metadata or 'author_last_name' in metadata:
        metadata['author'] = {
            'first_name': metadata.pop('author_first_name', None),
            'last_name': metadata.pop('author_last_name', None)
        }

    return metadata


def get_book_metadata(book_id: str):
    """
    Получает полные метаданные книги через Selenium
    """
    html_content = get_fb2_info_with_selenium(book_id)
    if not html_content:
        print("Не удалось получить HTML содержимое")
        return None

    print("Полученное содержимое:")
    print("-" * 50)
    print(html_content)
    print("-" * 50)

    # Пробуем XML парсер
    print("Пробуем XML парсер...")
    #metadata = parse_fb2_metadata_from_html(html_content)
    metadata = {}

    # Если XML не сработал, пробуем регулярки
    if not metadata:
        print("XML парсер не сработал, пробуем регулярные выражения...")
        metadata = parse_metadata_with_regex(html_content)

    return metadata


if __name__ == "__main__":
    print("=== ТЕСТИРОВАНИЕ ПАРСЕРА ===")

    metadata = get_book_metadata("747802")

    if metadata:
        print("\n✅ УСПЕХ! Метаданные книги:")
        for key, value in metadata.items():
            print(f"{key}: {value}")
    else:
        print("\n❌ Не удалось распарсить метаданные")

