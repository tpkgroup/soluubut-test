import os
import time

import pg8000.dbapi
from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)

DB = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "app"),
    password=os.environ.get("DB_PASSWORD", "app"),
    database=os.environ.get("DB_NAME", "guestbook"),
)

PAGE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sổ lưu bút</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #1e293b; }
  form { display: grid; gap: .5rem; margin-bottom: 2rem; }
  input, textarea, button { font: inherit; padding: .6rem; border: 1px solid #94a3b8; border-radius: 8px; }
  button { background: #0f766e; color: #fff; border: 0; cursor: pointer; }
  article { padding: .8rem 0; border-top: 1px solid #cbd5e1; }
  small { color: #64748b; }
</style></head><body>
<h1>Sổ lưu bút</h1>
<form method="post">
  <input name="name" placeholder="Tên của bạn" maxlength="50" required>
  <textarea name="body" placeholder="Lời nhắn" maxlength="500" rows="3" required></textarea>
  <button>Gửi lời nhắn</button>
</form>
{% for name, body, created in rows %}
<article><strong>{{ name }}</strong> <small>{{ created.strftime('%d/%m/%Y %H:%M') }}</small><p>{{ body }}</p></article>
{% else %}
<p>Chưa có lời nhắn nào. Hãy là người đầu tiên.</p>
{% endfor %}
<p><small>Database: {{ host }}</small></p>
</body></html>"""


def connect():
    return pg8000.dbapi.connect(timeout=5, **DB)


def init_db(retries=30):
    for _ in range(retries):
        try:
            conn = connect()
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id SERIAL PRIMARY KEY, name TEXT NOT NULL, body TEXT NOT NULL, "
                "created_at TIMESTAMP DEFAULT now())"
            )
            conn.commit()
            conn.close()
            return
        except Exception as e:
            print("Đang chờ database...", e, flush=True)
            time.sleep(2)
    raise SystemExit("Không kết nối được database")


init_db()


@app.route("/", methods=["GET", "POST"])
def index():
    conn = connect()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:50]
        body = request.form.get("body", "").strip()[:500]
        if name and body:
            cur.execute("INSERT INTO messages (name, body) VALUES (%s, %s)", (name, body))
            conn.commit()
        conn.close()
        return redirect("/")
    cur.execute("SELECT name, body, created_at FROM messages ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    conn.close()
    return render_template_string(PAGE, rows=rows, host=DB["host"])


@app.route("/health")
def health():
    try:
        conn = connect()
        conn.cursor().execute("SELECT 1")
        conn.close()
        return {"web": "ok", "db": "ok"}
    except Exception as e:
        return {"web": "ok", "db": "error", "detail": str(e)}, 503
