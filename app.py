import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "chave_super_secreta_123"

DATABASE_URL = os.getenv("DATABASE_URL")

UPLOAD_FOLDER = "materiais_privados"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
# CONEXÃO
# =========================
def get_db():
    return psycopg2.connect(DATABASE_URL)


# =========================
# CRIAR TABELAS
# =========================
def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS turmas (
        id SERIAL PRIMARY KEY,
        nome TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        login TEXT UNIQUE,
        senha TEXT,
        tipo TEXT,
        turma_id INTEGER REFERENCES turmas(id),
        data_matricula DATE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS materiais (
        id SERIAL PRIMARY KEY,
        titulo TEXT,
        nome_arquivo TEXT,
        turma_id INTEGER REFERENCES turmas(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS simulados (
        id SERIAL PRIMARY KEY,
        titulo TEXT,
        turma_id INTEGER REFERENCES turmas(id),
        ativo BOOLEAN DEFAULT TRUE
    );
    """)

    conn.commit()
    cur.close()
    conn.close()


def criar_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE login='admin'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO usuarios (nome, login, senha, tipo)
            VALUES (%s,%s,%s,%s)
        """, ("Administrador", "admin",
              generate_password_hash("123456"), "admin"))
        conn.commit()
    cur.close()
    conn.close()


@app.route("/init")
def init():
    criar_tabelas()
    criar_admin()
    return "Banco inicializado!"


# =========================
# LOGIN
# =========================
@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        senha = request.form["senha"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, senha, tipo FROM usuarios WHERE login=%s", (login,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[1], senha):
            session["user_id"] = user[0]
            session["tipo"] = user[2]
            return redirect("/admin" if user[2] == "admin" else "/aluno")

        return "Login inválido"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin")
def admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    return render_template("admin_dashboard.html")


# =========================
# MATERIAIS ADMIN
# =========================
@app.route("/materiais-admin", methods=["GET", "POST"])
def materiais_admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM turmas")
    turmas = cur.fetchall()

    if request.method == "POST":
        titulo = request.form["titulo"]
        turma_id = request.form["turma"]
        arquivo = request.files["arquivo"]

        nome_arquivo = secure_filename(arquivo.filename)
        caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        arquivo.save(caminho)

        cur.execute("""
            INSERT INTO materiais (titulo, nome_arquivo, turma_id)
            VALUES (%s,%s,%s)
        """, (titulo, nome_arquivo, turma_id))
        conn.commit()

    cur.execute("SELECT titulo FROM materiais")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("materiais_admin.html",
                           turmas=turmas,
                           lista=lista)


@app.route("/material/<nome>")
def abrir_material(nome):
    if session.get("tipo") != "aluno":
        return redirect("/login")
    return send_file(os.path.join(UPLOAD_FOLDER, nome))


# =========================
# SIMULADOS ADMIN
# =========================
@app.route("/simulados-admin", methods=["GET", "POST"])
def simulados_admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        titulo = request.form["titulo"]
        turma = request.form["turma"]
        cur.execute("INSERT INTO simulados (titulo, turma_id) VALUES (%s,%s)",
                    (titulo, turma))
        conn.commit()

    cur.execute("SELECT id, nome FROM turmas")
    turmas = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("simulados_admin.html", turmas=turmas)


# =========================
# ALUNO DASHBOARD
# =========================
@app.route("/aluno")
def aluno():
    if session.get("tipo") != "aluno":
        return redirect("/login")

    return render_template("aluno_dashboard.html")
