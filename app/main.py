from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
from database import get_db, init_db
import hashlib
import secrets
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))
app.permanent_session_lifetime = timedelta(days=7)

FLAG = os.getenv('FLAG', 'practice{StoredXSS_miem_ctf_2026}')

def ensure_bot_exists():
    """Создает пользователя bot, если его нет (вызывается при запуске)"""
    with get_db() as conn:
        bot_username = os.getenv('BOT_USERNAME')
        bot_password_plain = os.getenv('BOT_PASSWORD')
        bot_password = hashlib.sha256(bot_password_plain.encode()).hexdigest()
        
        conn.execute('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)',
                    (bot_username, bot_password))
        conn.commit()
        print(f"Пользователь {bot_username} проверен/создан")

init_db()
ensure_bot_exists()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('blog'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                              (username, password)).fetchone()
            
            if user:
                session['username'] = username
                session.permanent = True
                return redirect(url_for('blog'))
            else:
                return render_template('login.html', error='Неверное имя пользователя или пароль')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('register.html', error='Пароли не совпадают')
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            with get_db() as conn:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                           (username, hashed_password))
                
                user = conn.execute('SELECT id FROM users WHERE username = ?',
                                  (username,)).fetchone()
                user_id = user['id']
                
                sample_comments = [
                    (1, user_id, 'Аноним', 'Крокодилы такие милые создания!'),
                    (1, user_id, 'Любитель_природы', 'Интересно, а сколько они живут?'),
                    (2, user_id, 'Исследователь', 'Узкорылый крокодил - мой любимчик! Очень редкий вид'),
                    (3, user_id, 'Турист', 'Видел такого в зоопарке, реально маленький ахаха, почти как игрушечный'),
                    (4, user_id, 'Охотник', 'Страшные хищники, лучше держаться подальше от водоемов в Африке'),
                    (5, user_id, 'Биолог', 'Забота о потомстве у них удивительная! Прямо как у птиц))'),
                ]
                
                for article_id, uid, uname, content in sample_comments:
                    conn.execute('''
                        INSERT INTO comments (article_id, user_id, username, content, timestamp)
                        VALUES (?, ?, ?, ?, datetime('now', '-1 day'))
                    ''', (article_id, uid, uname, content))
                
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Пользователь с таким именем уже существует')
    
    return render_template('register.html')

@app.route('/blog')
def blog():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    article_id = request.args.get('article', 1)
    
    with get_db() as conn:
        user = conn.execute('SELECT id FROM users WHERE username = ?', 
                          (session['username'],)).fetchone()
        
        if user is None:
            session.clear()
            return redirect(url_for('login'))
            
        user_id = user['id']
        
        articles = conn.execute('SELECT id, title FROM articles').fetchall()
        current_article = conn.execute('SELECT * FROM articles WHERE id = ?', 
                                      (article_id,)).fetchone()
        
        if session['username'] == 'bot':
            comments = conn.execute('''
                SELECT id, username, content, timestamp 
                FROM comments 
                WHERE article_id = ?
                ORDER BY timestamp DESC
            ''', (article_id,)).fetchall()
        else:
            comments = conn.execute('''
                SELECT id, username, content, timestamp 
                FROM comments 
                WHERE article_id = ? AND user_id = ?
                ORDER BY timestamp DESC
            ''', (article_id, user_id)).fetchall()
    
    return render_template('blog.html', 
                         articles=articles, 
                         article=current_article, 
                         comments=comments,
                         username=session['username'],
                         flag=FLAG)

@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    article_id = request.form['article_id']
    content = request.form['content']
    
    with get_db() as conn:
        user = conn.execute('SELECT id FROM users WHERE username = ?', 
                          (session['username'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('login'))
            
        user_id = user['id']
        
        conn.execute('''
            INSERT INTO comments (article_id, user_id, username, content)
            VALUES (?, ?, ?, ?)
        ''', (article_id, user_id, session['username'], content))
    
    return redirect(url_for('blog', article=article_id))

@app.route('/get_comment/<int:comment_id>')
def get_comment(comment_id):
    with get_db() as conn:
        comment = conn.execute('SELECT * FROM comments WHERE id = ?', 
                             (comment_id,)).fetchone()
        if comment:
            return jsonify({
                'id': comment['id'],
                'username': comment['username'],
                'content': comment['content'],
                'timestamp': comment['timestamp']
            })
    return jsonify({'error': 'Комментарий не найден'}), 404

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
