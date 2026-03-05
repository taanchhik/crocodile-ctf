from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import threading
import logging
import os
import time
import re
import sqlite3
from urllib.parse import urlparse, parse_qs

DB_PATH = '/app/data/crocodile_blog.db'

app = Flask(__name__)
FLAG = os.getenv('FLAG')

BOT_USERNAME = os.getenv('BOT_USERNAME')
BOT_PASSWORD = os.getenv('BOT_PASSWORD')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

caught_flag = None

@app.before_request
def log_request_info():
    logger.info(f"ВХОДЯЩИЙ ЗАПРОС: {request.method} {request.url}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Args: {dict(request.args)}")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response

def login_bot(page):
    try:
        logger.debug("Авторизация бота...")
        
        page.goto("http://web:5000/login", wait_until='networkidle')
        logger.debug("Страница для входа загружена")
        
        page.fill('input[name="username"]', BOT_USERNAME)
        page.fill('input[name="password"]', BOT_PASSWORD)
        logger.debug("Форма заполнена")
        
        with page.expect_navigation():
            page.click('button[type="submit"]')
            logger.debug("Клик по кнопке отправки")
        
        page.wait_for_load_state('networkidle')
        
        current_url = page.url
        
        if '/blog' in current_url:
            logger.info("Бот успешно авторизован!")
            return True
        else:
            error_text = page.text_content('.error')
            if error_text:
                logger.error(f"Ошибка на странице: {error_text}")
            logger.error(f"Неудачная авторизация. Текущий URL: {current_url}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при авторизации: {e}")
        return False

def visit_with_browser(comment_url):
    global caught_flag
    
    try:
        logger.debug(f"Исходный URL: {comment_url}")
        
        fixed_url = comment_url.replace('127.0.0.1', 'web').replace('localhost', 'web')
        base_url = fixed_url.split('#')[0]
        logger.debug(f"Базовый URL: {base_url}")
        
        logger.debug("Запуск Playwright...")
        with sync_playwright() as p:
            logger.debug("Playwright запущен")
            
            logger.debug("Запуск браузера...")
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.debug("Браузер запущен")
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            logger.debug("Страница создана")
            
            def log_request(request):
                logger.debug(f"ЗАПРОС: {request.method} {request.url}")
            
            def log_response(response):
                logger.debug(f"ОТВЕТ: {response.status} {response.url}")
            
            page.on('request', log_request)
            page.on('response', log_response)
            
            if not login_bot(page):
                logger.error("Не удалось авторизовать бота, прерываем выполнение")
                browser.close()
                return
            
            logger.debug(f"Переход на страницу с комментарием: {base_url}")
            page.goto(base_url, wait_until='networkidle')
            logger.debug("Страница с комментариями загружена")
            
            if '#' in fixed_url:
                comment_id = fixed_url.split('#')[1]
                logger.debug(f"Прокрутка к комментарию: {comment_id}")
                page.evaluate(f"""
                    var el = document.getElementById('{comment_id}');
                    if(el) {{
                        el.scrollIntoView();
                        el.style.backgroundColor = '#ffffcc';
                    }}
                """)
            
            logger.debug("Устанавливаем cookie...")
            page.evaluate(f"document.cookie = 'flag={FLAG}; path=/';")
            cookies = page.evaluate("document.cookie")
            
            logger.debug("Обновляем страницу...")
            page.reload(wait_until='networkidle')
            logger.debug("Страница обновлена")
            
            logger.debug("Ожидание 5 секунд...")
            time.sleep(5)
            
            browser.close()
            logger.debug("Браузер закрыт")
            
    except Exception as e:
        logger.error(f"Глобальная ошибка: {e}", exc_info=True)

@app.route('/check_comment', methods=['POST', 'OPTIONS'])
def check_comment():
    global caught_flag
    
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        comment_url = data.get('url')
        
        if not comment_url:
            return jsonify({'error': 'URL не указан'}), 400
        
        logger.info(f"ПОЛУЧЕН ЗАПРОС: {comment_url}")
        
        import re
        comment_id_match = re.search(r'comment-(\d+)', comment_url)
        
        caught_flag = None
        thread = threading.Thread(target=visit_with_browser, args=(comment_url,))
        thread.start()
        thread.join(timeout=30)
        
        if caught_flag:
            logger.info(f"ВОЗВРАЩАЕМ ФЛАГ ПОЛЬЗОВАТЕЛЮ: {caught_flag}")
            
            if comment_id_match:
                comment_id = comment_id_match.group(1)
                try:
                    conn = sqlite3.connect('/app/data/crocodile_blog.db')
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
                    conn.commit()
                    conn.close()
                    logger.info(f"Комментарий {comment_id} удален после получения флага")
                except Exception as e:
                    logger.error(f"Ошибка при удалении комментария: {e}")
            
            return jsonify({'message': f'FLAG: {caught_flag}'})
        
        return jsonify({'message': 'Комментарий в обработке, благодарим за обращение!'})
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return jsonify({'error': 'Ошибка сервера'}), 500

@app.route('/catch', methods=['GET', 'POST', 'OPTIONS'])
def catch_flag():
    global caught_flag
    
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        cookies = request.args.get('c', '') if request.method == 'GET' else request.json.get('cookies', '')
        logger.info(f"GET /catch с параметром c: {cookies}")
        
        if FLAG in cookies:
            logger.info(f"ФЛАГ ПЕРЕХВАЧЕН!")
            caught_flag = FLAG
            return jsonify({'status': 'ok', 'flag': FLAG})
        else:
            logger.info(f"Флаг не найден")
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Ошибка на /catch: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
