from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import sqlite3
import hashlib


app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="supersecretkey123")
app.mount("/static", StaticFiles(directory="static"), name="static")

conn = sqlite3.connect('blog.db')
cur = conn.cursor()
cur.executescript('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    );
''')
conn.commit()
conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_template(filename):
    with open(f"templates/{filename}", "r", encoding="utf-8") as f:
        return f.read()

def remove_log_reg_btn(template: str, current_user: str | None):
    if current_user:
        return template.replace("{{auth_buttons}}", f"""
            <span class='user-info'>Inloggad som: <b>{current_user}</b></span>
            <a class='btn' href='/logout'>Logout</a>
        """)
    else:
        return template.replace("{{auth_buttons}}", """
            <a class='btn' href='/register'>Register</a>
            <a class='btn' href='/login'>Login</a>
        """)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT id, title, content FROM posts ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()

    template = load_template("index.html") 
    current_user = request.session.get("user")

    template = remove_log_reg_btn(template, current_user)

    posts_html = ""
    for pid, title, content in posts:
        posts_html += f"""
        <div class='post'>
            <h2>{title}</h2>
            <p>{content}</p>
        </div>"""
    
    current_user = request.session.get("user")
 

    return template.replace("{{posts}}", posts_html)


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request):
    current_user = request.session.get("user")
    
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    if current_user != "admin1":
        return RedirectResponse("/", status_code=303)
   

    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT id, title, content FROM posts ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()

    template = load_template("admin.html") 
    current_user = request.session.get("user")

    template = remove_log_reg_btn(template, current_user)
    
    posts_html = ""
    for pid, title, content in posts:
        posts_html += f"""
        <div class='post'>
            <h2>{title}</h2>
            <p>{content}</p>
            <a href="/edit/{pid}">✏️ Redigera</a>
            <a href="/delete/{pid}">🗑️ Ta bort</a>
        </div>"""

    return template.replace("{{posts}}", posts_html)


@app.get("/new", response_class=HTMLResponse)
def new_post_form():
    return load_template("new.html")

@app.post("/new")
def save_post(title: str = Form(...), content: str = Form(...)):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
                                                #(?, ?) Att skydda mot SQL-injection (hackare kan inte smyga in egen SQL i dina formulärfält).
    cur.execute("INSERT INTO posts (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin", status_code=303)

@app.get("/delete/{post_id}")
def delete_post(post_id: int):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin", status_code=303)

@app.get("/edit/{post_id}", response_class=HTMLResponse)
def edit_post_form(post_id: int):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT title, content FROM posts WHERE id = ?", (post_id,))
    post = cur.fetchone()
    conn.close()

    if not post:
        return RedirectResponse("/admin", status_code=303)

    title, content = post
    html = load_template("update.html")
    html = html.replace("{post_id}", str(post_id))
    html = html.replace("{title}", title)
    html = html.replace("{content}", content)
    
    return HTMLResponse(html)
@app.post("/edit/{post_id}")
def update_post(post_id: int, title: str = Form(...), content: str = Form(...)):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("UPDATE posts SET title = ?, content = ? WHERE id = ?", (title, content, post_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_form():
    return load_template("register.html")

@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
    conn.commit()
    conn.close()
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_form():
    return load_template("login.html")

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND password = ?",  (username, hash_password(password)))
    user = cur.fetchone()
    conn.close()
    hashed_input = hash_password(password)
    if not user:
        return HTMLResponse("Fel användarnamn eller lösenord <a href='/login'>Försök igen</a>")
    request.session["user"] = user[1]
    print("Inloggad som:", request.session["user"])
    
    if user:
        if (user[1] == "admin1") and (user[2] == hashed_input):
         return RedirectResponse("/admin", status_code=303) 
        else:
            return RedirectResponse("/", status_code=303) 
   

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)