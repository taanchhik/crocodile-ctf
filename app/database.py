import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'crocodile_blog.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        count = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
        
        if count == 0:
            articles_dir = os.path.join(os.path.dirname(__file__), 'articles')
            
            article_titles = [
                "Нильский крокодил - король Африки",
                "Африканский узкорылый крокодил",
                "Карликовый крокодил - скрытный житель джунглей",
                "Охота нильского крокодила",
                "Размножение и забота о потомстве"
            ]
            
            for i, title in enumerate(article_titles, 1):
                file_path = os.path.join(articles_dir, f'article_{i}.txt')
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                except FileNotFoundError:
                    content = f"Здесь должна быть статья про {title.lower()}... Но файл с текстом не найден."
                
                conn.execute('INSERT INTO articles (title, content) VALUES (?, ?)', 
                           (title, content))
