import os
import sqlite3
import json
import urllib.parse
import urllib.request
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

DB_PATH = os.path.join(app.root_path, "quiz.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nickname TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                corrette INTEGER NOT NULL,
                totale INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )


def ensure_schema():
    with get_db() as conn:
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "nickname" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN nickname TEXT")
            conn.execute(
                "UPDATE users SET nickname = username WHERE nickname IS NULL OR nickname = ''"
            )


init_db()
ensure_schema()

# domande del quiz
domande = [
{
    "domanda": "Qual è il linguaggio più usato per sviluppare applicazioni di Intelligenza Artificiale?",
    "opzioni": ["C++", "Python", "HTML", "CSS"],
    "risposta": "Python"
},
{
    "domanda": "Quale libreria Python è molto usata per il Machine Learning?",
    "opzioni": ["Flask", "scikit-learn", "Django", "Selenium"],
    "risposta": "scikit-learn"
},
{
    "domanda": "A cosa serve TensorFlow?",
    "opzioni": [
        "Sviluppare modelli di machine learning",
        "Creare pagine web",
        "Gestire database",
        "Compilare programmi"
    ],
    "risposta": "Sviluppare modelli di machine learning"
},
{
    "domanda": "Cos'è il Machine Learning?",
    "opzioni": [
        "Un metodo per compilare codice",
        "Un sistema che permette ai computer di imparare dai dati",
        "Un database avanzato",
        "Un linguaggio di programmazione"
    ],
    "risposta": "Un sistema che permette ai computer di imparare dai dati"
},
{
    "domanda": "Quale struttura è alla base del Deep Learning?",
    "opzioni": [
        "Reti neurali artificiali",
        "Liste collegate",
        "Stack",
        "Database relazionali"
    ],
    "risposta": "Reti neurali artificiali"
},
{
    "domanda": "Quale libreria Python serve per analizzare dati?",
    "opzioni": ["Pandas", "Flask", "Tkinter", "Pygame"],
    "risposta": "Pandas"
},
{
    "domanda": "A cosa serve un dataset di training?",
    "opzioni": [
        "Addestrare un modello",
        "Compilare codice",
        "Creare interfacce grafiche",
        "Installare librerie"
    ],
    "risposta": "Addestrare un modello"
},
{
    "domanda": "Quale tipo di apprendimento usa dati etichettati?",
    "opzioni": [
        "Supervised learning",
        "Unsupervised learning",
        "Reinforcement learning",
        "Random learning"
    ],
    "risposta": "Supervised learning"
},
{
    "domanda": "Quale libreria Python è molto usata per il Deep Learning?",
    "opzioni": ["PyTorch", "BeautifulSoup", "Requests", "Matplotlib"],
    "risposta": "PyTorch"
},
{
    "domanda": "Cos'è un modello di Machine Learning?",
    "opzioni": [
        "Un algoritmo addestrato sui dati",
        "Un database",
        "Un sistema operativo",
        "Un server web"
    ],
    "risposta": "Un algoritmo addestrato sui dati"
}
]


def _italian_day_name(dt: datetime) -> str:
    giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    return giorni[dt.weekday()]


def fetch_weather(city: str):
    """Fetch 3-day forecast using Open-Meteo (geocoding + forecast)."""

    if not city:
        return None, "Inserisci una città", None

    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": city, "count": 1, "language": "it", "format": "json"}
        )
        with urllib.request.urlopen(geo_url, timeout=10) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        results = geo_data.get("results") or []
        if not results:
            return None, "Città non trovata", None

        loc = results[0]
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        location_label = f"{loc.get('name')}, {loc.get('country_code')}"

        forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
            {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": 3,
                "timezone": "auto",
            }
        )
        with urllib.request.urlopen(forecast_url, timeout=10) as resp:
            forecast_data = json.loads(resp.read().decode("utf-8"))

        daily = forecast_data.get("daily", {})
        times = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])

        forecast = []
        for t, mx, mn in zip(times, t_max, t_min):
            try:
                dt = datetime.fromisoformat(t)
            except Exception:
                dt = None
            day_name = _italian_day_name(dt) if dt else ""
            date_fmt = dt.strftime("%Y-%m-%d") if dt else t
            forecast.append(
                {
                    "day": day_name,
                    "date": date_fmt,
                    "temp_day": round(mx, 1) if mx is not None else None,
                    "temp_night": round(mn, 1) if mn is not None else None,
                }
            )

        return forecast, None, location_label

    except Exception:
        return None, "Errore nel recupero meteo", None

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper

@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    weather_data = None
    weather_error = None
    location_label = None
    city_input = None

    if request.method == "POST":
        city_input = request.form.get("city", "").strip()
        weather_data, weather_error, location_label = fetch_weather(city_input)

    return render_template(
        "home.html",
        weather_data=weather_data,
        weather_error=weather_error,
        location_label=location_label,
        city_input=city_input,
    )

@app.route("/")
@login_required
def quiz():
    # Log all questions to the console for debugging/inspection
    for idx, domanda_corrente in enumerate(domande, start=1):
        print(f"Domanda {idx}: {domanda_corrente['domanda']}")

    # Pass the full list so the template can render all questions on one page
    return render_template("quiz.html", domande=domande)

@app.route("/risultato", methods=["POST"])
@login_required
def risultato():
    corrette = 0
    totale = len(domande)
    errate = []

    # Confronta ogni risposta dell'utente con la soluzione corretta
    for idx, domanda_corrente in enumerate(domande):
        chiave = f"risposta_{idx}"
        risposta_utente = request.form.get(chiave)
        if risposta_utente == domanda_corrente["risposta"]:
            corrette += 1
        else:
            errate.append(
                {
                    "domanda": domanda_corrente["domanda"],
                    "corretta": domanda_corrente["risposta"],
                    "utente": risposta_utente if risposta_utente else "Non risposta",
                }
            )

    messaggio = f"Risposte corrette: {corrette} su {totale}"
    user_id = session.get("user_id")
    if user_id:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO scores (user_id, corrette, totale, created_at) VALUES (?, ?, ?, ?)",
                (user_id, corrette, totale, datetime.utcnow().isoformat()),
            )

    with get_db() as conn:
        leaderboard_rows = conn.execute(
            """
            SELECT COALESCE(u.nickname, u.username) AS nickname, s.corrette, s.totale, s.created_at
            FROM scores s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.corrette DESC, s.totale DESC, s.created_at ASC
            LIMIT 10
            """
        ).fetchall()

    leaderboard = []
    for row in leaderboard_rows:
        created_at_raw = row["created_at"]
        try:
            created_at_fmt = datetime.fromisoformat(created_at_raw).strftime("%Y-%m-%d")
        except Exception:
            created_at_fmt = created_at_raw

        leaderboard.append(
            {
                "nickname": row["nickname"],
                "corrette": row["corrette"],
                "totale": row["totale"],
                "created_at": created_at_fmt,
            }
        )

    return render_template(
        "risultato.html",
        messaggio=messaggio,
        errate=errate,
        leaderboard=leaderboard,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as conn:
            row = conn.execute(
                "SELECT id, username, password, COALESCE(nickname, username) AS nickname FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if row and row["password"] == password:
            session["user"] = row["username"]
            session["user_id"] = row["id"]
            session["nickname"] = row["nickname"]
            return redirect(url_for("home"))
        else:
            error = "Credenziali non valide"

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        nickname = request.form.get("nickname", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not username or not password or not nickname:
            error = "Inserisci username, nickname e password"
        elif password != password_confirm:
            error = "Le password non coincidono"
        else:
            try:
                with get_db() as conn:
                    existing_nick = conn.execute(
                        "SELECT 1 FROM users WHERE nickname = ?",
                        (nickname,),
                    ).fetchone()
                    if existing_nick:
                        raise sqlite3.IntegrityError("nickname-not-unique")

                    cursor = conn.execute(
                        "INSERT INTO users (username, password, nickname) VALUES (?, ?, ?)",
                        (username, password, nickname),
                    )
                    user_id = cursor.lastrowid
                session["user"] = username
                session["user_id"] = user_id
                session["nickname"] = nickname
                return redirect(url_for("home"))
            except sqlite3.IntegrityError as exc:
                if "nickname" in str(exc) or "nickname-not-unique" in str(exc):
                    error = "Nickname già in uso"
                else:
                    error = "Utente già registrato"

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("user_id", None)
    session.pop("nickname", None)
    return redirect(url_for("login"))

app.run(debug=True)