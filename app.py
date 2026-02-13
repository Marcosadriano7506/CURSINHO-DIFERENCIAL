import os
import psycopg2
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave_super_secreta_123"

DATABASE_URL = os.getenv("DATABASE_URL")


# =========================
# CONEXÃO
# =========================
def get_db():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL não configurada.")
    return psycopg2.connect(DATABASE_URL)


# =========================
# CRIAÇÃO DE TABELAS
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
    return "Banco inicializado com sucesso!"


# =========================
# LOGIN
# =========================
@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form.get("login")
        senha = request.form.get("senha")

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

        return render_template("login.html", erro="Login inválido")

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
# TURMAS
# =========================
@app.route("/turmas", methods=["GET", "POST"])
def turmas():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form.get("nome")
        if nome:
            cur.execute("INSERT INTO turmas (nome) VALUES (%s)", (nome,))
            conn.commit()

    cur.execute("SELECT id, nome FROM turmas ORDER BY id DESC")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("turmas.html", turmas=lista)


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
        titulo = request.form.get("titulo")
        turma = request.form.get("turma")
        if titulo and turma:
            cur.execute("INSERT INTO simulados (titulo, turma_id) VALUES (%s,%s)",
                        (titulo, turma))
            conn.commit()

    cur.execute("SELECT id, nome FROM turmas")
    turmas = cur.fetchall()

    cur.execute("SELECT id, titulo FROM simulados")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("simulados_admin.html",
                           turmas=turmas,
                           lista=lista)


# =========================
# ADICIONAR QUESTÃO
# =========================
@app.route("/adicionar-questao/<int:simulado_id>", methods=["GET", "POST"])
def adicionar_questao(simulado_id):
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            INSERT INTO questoes
            (simulado_id,enunciado,alt_a,alt_b,alt_c,alt_d,alt_e,correta)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            simulado_id,
            request.form.get("enunciado"),
            request.form.get("a"),
            request.form.get("b"),
            request.form.get("c"),
            request.form.get("d"),
            request.form.get("e"),
            request.form.get("correta")
        ))
        conn.commit()

    cur.close()
    conn.close()

    return render_template("adicionar_questao.html",
                           simulado_id=simulado_id)


# =========================
# ALUNO DASHBOARD
# =========================
@app.route("/aluno")
def aluno():
    if session.get("tipo") != "aluno":
        return redirect("/login")

    usuario_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT turma_id FROM usuarios WHERE id=%s", (usuario_id,))
    turma = cur.fetchone()

    simulados = []
    historico = []

    if turma:
        turma_id = turma[0]

        cur.execute("""
            SELECT id, titulo FROM simulados
            WHERE turma_id=%s AND ativo=TRUE
        """, (turma_id,))
        simulados = cur.fetchall()

        cur.execute("""
            SELECT percentual, data_realizacao
            FROM resultados
            WHERE aluno_id=%s
            ORDER BY data_realizacao DESC
        """, (usuario_id,))
        historico = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("aluno_dashboard.html",
                           simulados=simulados,
                           historico=historico)


# =========================
# FAZER SIMULADO
# =========================
@app.route("/fazer-simulado/<int:simulado_id>", methods=["GET", "POST"])
def fazer_simulado(simulado_id):
    if session.get("tipo") != "aluno":
        return redirect("/login")

    usuario_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("SELECT id, correta FROM questoes WHERE simulado_id=%s",
                    (simulado_id,))
        questoes = cur.fetchall()

        total = len(questoes)
        acertos = 0

        for q in questoes:
            resposta = request.form.get(f"q{q[0]}")
            if resposta == q[1]:
                acertos += 1

        percentual = round((acertos / total) * 100, 2) if total else 0

        cur.execute("""
            INSERT INTO resultados
            (aluno_id, simulado_id, acertos, total, percentual, data_realizacao)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (usuario_id, simulado_id, acertos, total,
              percentual, datetime.now().date()))
        conn.commit()

        cur.close()
        conn.close()

        return render_template("resultado.html",
                               acertos=acertos,
                               total=total,
                               percentual=percentual)

    cur.execute("""
        SELECT id,enunciado,alt_a,alt_b,alt_c,alt_d,alt_e
        FROM questoes WHERE simulado_id=%s
    """, (simulado_id,))
    questoes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("fazer_simulado.html",
                           questoes=questoes)
