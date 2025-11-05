from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
import sqlite3
import hashlib
import os
import shutil

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="supersecretkey123")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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

try:
    cur.execute("ALTER TABLE posts ADD COLUMN image TEXT;")
except sqlite3.OperationalError:
    pass

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
    cur.execute("SELECT id, title, content, image FROM posts ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()

    
    current_user = request.session.get("user")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "posts": posts,
        "current_user": current_user
    })


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request):
    current_user = request.session.get("user")
    
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    if current_user != "admin1":
        return RedirectResponse("/", status_code=303)
   

    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, image FROM posts ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()

    current_user = request.session.get("user")

    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "posts": posts,
        "current_user": current_user
    })



@app.get("/new", response_class=HTMLResponse)
def new_post_form():
    return load_template("new.html")

@app.post("/new")
def save_post(title: str = Form(...), content: str = Form(...), image: UploadFile = File(None)):
    image_path = None
    if image and image.filename != "":
        image_path = f"static/uploads/{image.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO posts (title, content, image) VALUES (?, ?, ?)", (title, content, image_path))
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
def edit_post_form(request: Request, post_id: int):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT title, content, image FROM posts WHERE id = ?", (post_id,))
    post = cur.fetchone()
    conn.close()

    if not post:
        return RedirectResponse("/admin", status_code=303)

    title, content, image = post
    return templates.TemplateResponse("update.html", {
        "request": request,
        "post_id": post_id,
        "title": title,
        "content": content,
        "image": image
    })
    
   
@app.post("/edit/{post_id}")
def update_post(post_id: int, title: str = Form(...), content: str = Form(...), image: UploadFile = File(None)):
    conn = sqlite3.connect("blog.db")
    cur = conn.cursor()
    cur.execute("SELECT image FROM posts WHERE id = ?", (post_id,))
    old_image = cur.fetchone()[0]
    filename = os.path.basename(image.filename)
    image_path = f"static/uploads/{filename}".lstrip("/")

    if image and image.filename != "":
        image_path = f"static/uploads/{image.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    
    cur.execute(
        "UPDATE posts SET title = ?, content = ?, image = ? WHERE id = ?",
        (title, content, image_path, post_id)
    )

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

    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    existing_user = cur.fetchone()

    if existing_user:
        conn.close()
       
        return HTMLResponse("""
            <h2>❌ Användarnamnet finns redan!</h2>
            <p>Välj ett annat användarnamn.</p>
            <a href='/register'>⬅ Försök igen</a>
        """)

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