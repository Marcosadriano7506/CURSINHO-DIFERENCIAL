import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
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
    CREATE TABLE IF NOT EXISTS pagamentos (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
        mes INTEGER,
        ano INTEGER,
        vencimento DATE,
        status TEXT DEFAULT 'pendente',
        data_pagamento DATE
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questoes (
        id SERIAL PRIMARY KEY,
        simulado_id INTEGER REFERENCES simulados(id) ON DELETE CASCADE,
        enunciado TEXT,
        alt_a TEXT,
        alt_b TEXT,
        alt_c TEXT,
        alt_d TEXT,
        alt_e TEXT,
        correta TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS resultados (
        id SERIAL PRIMARY KEY,
        aluno_id INTEGER REFERENCES usuarios(id),
        simulado_id INTEGER REFERENCES simulados(id),
        acertos INTEGER,
        total INTEGER,
        percentual FLOAT,
        data_realizacao DATE
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

    return """
    <h2>Cursinho Diferencial</h2>
    <form method="POST">
        Login: <input name="login"><br><br>
        Senha: <input type="password" name="senha"><br><br>
        <button>Entrar</button>
    </form>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# ADMIN
# =========================
@app.route("/admin")
def admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    return """
    <h2>Painel Admin</h2>
    <a href="/turmas">Turmas</a><br>
    <a href="/materiais-admin">Materiais</a><br>
    <a href="/simulados-admin">Simulados</a><br>
    <a href="/logout">Sair</a>
    """


# =========================
# MATERIAIS
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

    html = "<h2>Materiais</h2><form method='POST' enctype='multipart/form-data'>"
    html += "Título: <input name='titulo'><br>"
    html += "Turma: <select name='turma'>"
    for t in turmas:
        html += f"<option value='{t[0]}'>{t[1]}</option>"
    html += "</select><br>"
    html += "Arquivo: <input type='file' name='arquivo'><br><br>"
    html += "<button>Enviar</button></form><hr>"

    for m in lista:
        html += m[0] + "<br>"

    cur.close()
    conn.close()
    return html


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

    html = "<h2>Simulados</h2>"
    html += "<form method='POST'>Título: <input name='titulo'>"
    html += "Turma: <select name='turma'>"
    for t in turmas:
        html += f"<option value='{t[0]}'>{t[1]}</option>"
    html += "</select><button>Criar</button></form>"

    cur.close()
    conn.close()
    return html


# =========================
# ALUNO
# =========================
@app.route("/aluno")
def aluno():
    if session.get("tipo") != "aluno":
        return redirect("/login")

    return """
    <h2>Painel do Aluno</h2>
    <a href="/logout">Sair</a>
    """
