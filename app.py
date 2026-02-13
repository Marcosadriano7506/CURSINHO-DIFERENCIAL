import os
import psycopg2
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

import psycopg2
from flask import Flask, redirect, render_template, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "chave_super_secreta_123"
app.secret_key = os.getenv("SECRET_KEY", "chave_super_secreta_123")

DATABASE_URL = os.getenv("DATABASE_URL")
USE_SQLITE = not DATABASE_URL or DATABASE_URL.startswith("sqlite:///")
SQLITE_PATH = DATABASE_URL.replace("sqlite:///", "") if DATABASE_URL and DATABASE_URL.startswith("sqlite:///") else os.path.join(os.path.dirname(__file__), "app.db")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "zip", "rar", "jpg", "jpeg", "png"
}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
# CONEXÃO
# UTILITÁRIOS
# =========================
def get_db():
    if USE_SQLITE:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    if not DATABASE_URL:
        raise Exception("DATABASE_URL não configurada.")
    return psycopg2.connect(DATABASE_URL)


def run_query(cur, query, params=()):
    if USE_SQLITE:
        query = query.replace("%s", "?")
    cur.execute(query, params)


def fetch_all(cur):
    rows = cur.fetchall()
    return [tuple(r) for r in rows] if USE_SQLITE else rows


def fetch_one(cur):
    row = cur.fetchone()
    return tuple(row) if (row and USE_SQLITE) else row


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
    if USE_SQLITE:
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS turmas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                login TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                tipo TEXT NOT NULL,
                turma_id INTEGER,
                FOREIGN KEY(turma_id) REFERENCES turmas(id)
            );

            CREATE TABLE IF NOT EXISTS simulados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                turma_id INTEGER,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY(turma_id) REFERENCES turmas(id)
            );

            CREATE TABLE IF NOT EXISTS questoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulado_id INTEGER,
                enunciado TEXT NOT NULL,
                alt_a TEXT NOT NULL,
                alt_b TEXT NOT NULL,
                alt_c TEXT NOT NULL,
                alt_d TEXT NOT NULL,
                alt_e TEXT NOT NULL,
                correta TEXT NOT NULL,
                FOREIGN KEY(simulado_id) REFERENCES simulados(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS resultados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aluno_id INTEGER,
                simulado_id INTEGER,
                acertos INTEGER,
                total INTEGER,
                percentual REAL,
                data_realizacao DATE,
                FOREIGN KEY(aluno_id) REFERENCES usuarios(id),
                FOREIGN KEY(simulado_id) REFERENCES simulados(id)
            );

            CREATE TABLE IF NOT EXISTS materiais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                arquivo TEXT NOT NULL,
                turma_id INTEGER,
                data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(turma_id) REFERENCES turmas(id)
            );
            """
        )
    else:
        run_query(
            cur,
            """
            CREATE TABLE IF NOT EXISTS turmas (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL UNIQUE
            );
            """,
        )
        run_query(
            cur,
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                login TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                tipo TEXT NOT NULL,
                turma_id INTEGER REFERENCES turmas(id)
            );
            """,
        )
        run_query(
            cur,
            """
            CREATE TABLE IF NOT EXISTS simulados (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                turma_id INTEGER REFERENCES turmas(id),
                ativo BOOLEAN DEFAULT TRUE
            );
            """,
        )
        run_query(
            cur,
            """
            CREATE TABLE IF NOT EXISTS questoes (
                id SERIAL PRIMARY KEY,
                simulado_id INTEGER REFERENCES simulados(id) ON DELETE CASCADE,
                enunciado TEXT NOT NULL,
                alt_a TEXT NOT NULL,
                alt_b TEXT NOT NULL,
                alt_c TEXT NOT NULL,
                alt_d TEXT NOT NULL,
                alt_e TEXT NOT NULL,
                correta TEXT NOT NULL
            );
            """,
        )
        run_query(
            cur,
            """
            CREATE TABLE IF NOT EXISTS resultados (
                id SERIAL PRIMARY KEY,
                aluno_id INTEGER REFERENCES usuarios(id),
                simulado_id INTEGER REFERENCES simulados(id),
                acertos INTEGER,
                total INTEGER,
                percentual FLOAT,
                data_realizacao DATE
            );
            """,
        )
        run_query(
            cur,
            """
            CREATE TABLE IF NOT EXISTS materiais (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                arquivo TEXT NOT NULL,
                turma_id INTEGER REFERENCES turmas(id),
                data_envio TIMESTAMP DEFAULT NOW()
            );
            """,
        )

    conn.commit()
    cur.close()
    conn.close()


def criar_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE login='admin'")
    if not cur.fetchone():
        cur.execute("""
    run_query(cur, "SELECT id FROM usuarios WHERE login='admin'")
    if not fetch_one(cur):
        run_query(
            cur,
            """
            INSERT INTO usuarios (nome, login, senha, tipo)
            VALUES (%s,%s,%s,%s)
        """, ("Administrador", "admin",
              generate_password_hash("123456"), "admin"))
            """,
            ("Administrador", "admin", generate_password_hash("123456"), "admin"),
        )
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
        login_value = request.form.get("login", "").strip()
        senha = request.form.get("senha", "")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, senha, tipo FROM usuarios WHERE login=%s", (login,))
        user = cur.fetchone()
        run_query(cur, "SELECT id, senha, tipo FROM usuarios WHERE login=%s", (login_value,))
        user = fetch_one(cur)
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
        nome = request.form.get("nome", "").strip()
        if nome:
            cur.execute("INSERT INTO turmas (nome) VALUES (%s)", (nome,))
            run_query(cur, "INSERT OR IGNORE INTO turmas (nome) VALUES (%s)" if USE_SQLITE else "INSERT INTO turmas (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (nome,))
            conn.commit()

    cur.execute("SELECT id, nome FROM turmas ORDER BY id DESC")
    lista = cur.fetchall()
    run_query(cur, "SELECT id, nome FROM turmas ORDER BY id DESC")
    lista = fetch_all(cur)

    cur.close()
    conn.close()

    return render_template("turmas.html", turmas=lista)


# =========================
# SIMULADOS ADMIN
# =========================
@app.route("/matricular", methods=["GET", "POST"])
def matricular():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        login_value = request.form.get("login", "").strip()
        senha = request.form.get("senha", "").strip()
        turma_id = request.form.get("turma")

        if nome and login_value and senha and turma_id:
            run_query(
                cur,
                (
                    "INSERT OR IGNORE INTO usuarios (nome, login, senha, tipo, turma_id) VALUES (%s,%s,%s,'aluno',%s)"
                    if USE_SQLITE
                    else "INSERT INTO usuarios (nome, login, senha, tipo, turma_id) VALUES (%s,%s,%s,'aluno',%s) ON CONFLICT (login) DO NOTHING"
                ),
                (nome, login_value, generate_password_hash(senha), turma_id),
            )
            conn.commit()

    run_query(cur, "SELECT id, nome FROM turmas ORDER BY nome")
    turmas = fetch_all(cur)

    run_query(
        cur,
        """
        SELECT u.nome, u.login, t.nome
        FROM usuarios u
        LEFT JOIN turmas t ON t.id = u.turma_id
        WHERE u.tipo = 'aluno'
        ORDER BY u.id DESC
        """,
    )
    alunos = fetch_all(cur)

    cur.close()
    conn.close()

    return render_template("matricular.html", turmas=turmas, alunos=alunos)


@app.route("/materiais-admin", methods=["GET", "POST"])
def materiais_admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        turma = request.form.get("turma")
        arquivo = request.files.get("arquivo")

        if titulo and turma and arquivo and arquivo.filename:
            filename = secure_filename(arquivo.filename)
            if allowed_file(filename):
                nome_salvo = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                arquivo.save(os.path.join(UPLOAD_FOLDER, nome_salvo))
                run_query(cur, "INSERT INTO materiais (titulo, arquivo, turma_id) VALUES (%s,%s,%s)", (titulo, nome_salvo, turma))
                conn.commit()

    run_query(cur, "SELECT id, nome FROM turmas ORDER BY nome")
    turmas = fetch_all(cur)

    run_query(
        cur,
        """
        SELECT m.titulo, m.arquivo, t.nome
        FROM materiais m
        LEFT JOIN turmas t ON t.id = m.turma_id
        ORDER BY m.id DESC
        """,
    )
    lista = fetch_all(cur)

    cur.close()
    conn.close()

    return render_template("materiais_admin.html", turmas=turmas, lista=lista)


@app.route("/uploads/<path:filename>")
def download_upload(filename):
    if session.get("tipo") not in {"admin", "aluno"}:
        return redirect("/login")
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.route("/simulados-admin", methods=["GET", "POST"])
def simulados_admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        titulo = request.form.get("titulo")
        titulo = request.form.get("titulo", "").strip()
        turma = request.form.get("turma")
        if titulo and turma:
            cur.execute("INSERT INTO simulados (titulo, turma_id) VALUES (%s,%s)",
                        (titulo, turma))
            run_query(cur, "INSERT INTO simulados (titulo, turma_id) VALUES (%s,%s)", (titulo, turma))
            conn.commit()

    cur.execute("SELECT id, nome FROM turmas")
    turmas = cur.fetchall()
    run_query(cur, "SELECT id, nome FROM turmas ORDER BY nome")
    turmas = fetch_all(cur)

    cur.execute("SELECT id, titulo FROM simulados")
    lista = cur.fetchall()
    run_query(cur, "SELECT id, titulo FROM simulados ORDER BY id DESC")
    lista = fetch_all(cur)

    cur.close()
    conn.close()

    return render_template("simulados_admin.html",
                           turmas=turmas,
                           lista=lista)
    return render_template("simulados_admin.html", turmas=turmas, lista=lista)


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
        run_query(
            cur,
            """
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
            """,
            (
                simulado_id,
                request.form.get("enunciado"),
                request.form.get("a"),
                request.form.get("b"),
                request.form.get("c"),
                request.form.get("d"),
                request.form.get("e"),
                request.form.get("correta"),
            ),
        )
        conn.commit()

    cur.close()
    conn.close()

    return render_template("adicionar_questao.html",
                           simulado_id=simulado_id)
    return render_template("adicionar_questao.html", simulado_id=simulado_id)


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
    run_query(cur, "SELECT turma_id FROM usuarios WHERE id=%s", (usuario_id,))
    turma = fetch_one(cur)

    simulados = []
    historico = []
    materiais = []

    if turma:
    if turma and turma[0]:
        turma_id = turma[0]

        cur.execute("""
        run_query(
            cur,
            """
            SELECT id, titulo FROM simulados
            WHERE turma_id=%s AND ativo=TRUE
        """, (turma_id,))
        simulados = cur.fetchall()

        cur.execute("""
            WHERE turma_id=%s AND ativo=1
            ORDER BY id DESC
            """,
            (turma_id,),
        )
        simulados = fetch_all(cur)

        run_query(
            cur,
            """
            SELECT percentual, data_realizacao
            FROM resultados
            WHERE aluno_id=%s
            ORDER BY data_realizacao DESC
        """, (usuario_id,))
        historico = cur.fetchall()
            """,
            (usuario_id,),
        )
        historico = fetch_all(cur)

        run_query(
            cur,
            """
            SELECT titulo, arquivo
            FROM materiais
            WHERE turma_id=%s
            ORDER BY id DESC
            """,
            (turma_id,),
        )
        materiais = fetch_all(cur)

    cur.close()
    conn.close()

    return render_template("aluno_dashboard.html",
                           simulados=simulados,
                           historico=historico)
    return render_template("aluno_dashboard.html", simulados=simulados, historico=historico, materiais=materiais)


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
        run_query(cur, "SELECT id, correta FROM questoes WHERE simulado_id=%s", (simulado_id,))
        questoes = fetch_all(cur)

        total = len(questoes)
        acertos = 0

        for q in questoes:
            resposta = request.form.get(f"q{q[0]}")
            if resposta == q[1]:
                acertos += 1

        percentual = round((acertos / total) * 100, 2) if total else 0

        cur.execute("""
        run_query(
            cur,
            """
            INSERT INTO resultados
            (aluno_id, simulado_id, acertos, total, percentual, data_realizacao)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (usuario_id, simulado_id, acertos, total,
              percentual, datetime.now().date()))
            """,
            (usuario_id, simulado_id, acertos, total, percentual, datetime.now().date()),
        )
        conn.commit()

        cur.close()
        conn.close()

        return render_template("resultado.html",
                               acertos=acertos,
                               total=total,
                               percentual=percentual)
        return render_template("resultado.html", acertos=acertos, total=total, percentual=percentual)

    cur.execute("""
    run_query(
        cur,
        """
        SELECT id,enunciado,alt_a,alt_b,alt_c,alt_d,alt_e
        FROM questoes WHERE simulado_id=%s
    """, (simulado_id,))
    questoes = cur.fetchall()
        """,
        (simulado_id,),
    )
    questoes = fetch_all(cur)

    cur.close()
    conn.close()

    return render_template("fazer_simulado.html",
                           questoes=questoes)
    return render_template("fazer_simulado.html", questoes=questoes)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
