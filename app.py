import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "chave_super_secreta_123"

DATABASE_URL = os.getenv("DATABASE_URL")


# =========================
# CONEXÃO COM BANCO
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
        nome TEXT NOT NULL,
        login TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        tipo TEXT NOT NULL,
        turma_id INTEGER REFERENCES turmas(id),
        data_matricula DATE,
        ativo BOOLEAN DEFAULT TRUE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pagamentos (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
        mes INTEGER NOT NULL,
        ano INTEGER NOT NULL,
        vencimento DATE NOT NULL,
        status TEXT DEFAULT 'pendente',
        data_pagamento DATE
    );
    """)

    conn.commit()
    cur.close()
    conn.close()


# =========================
# CRIAR ADMIN PADRÃO
# =========================
def criar_admin():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM usuarios WHERE login = %s", ("admin",))
    admin = cur.fetchone()

    if not admin:
        senha_hash = generate_password_hash("123456")
        cur.execute("""
            INSERT INTO usuarios (nome, login, senha, tipo)
            VALUES (%s, %s, %s, %s)
        """, ("Administrador", "admin", senha_hash, "admin"))
        conn.commit()

    cur.close()
    conn.close()


# =========================
# ROTA DE INICIALIZAÇÃO
# =========================
@app.route("/init")
def init():
    try:
        criar_tabelas()
        criar_admin()
        return "Banco inicializado com sucesso!"
    except Exception as e:
        return f"Erro ao inicializar: {str(e)}"


# =========================
# ROTAS PRINCIPAIS
# =========================
@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        senha = request.form["senha"]

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, senha, tipo FROM usuarios WHERE login=%s",
                (login,)
            )
            user = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            return f"Erro de conexão: {str(e)}"

        if user and check_password_hash(user[1], senha):
            session["user_id"] = user[0]
            session["tipo"] = user[2]

            if user[2] == "admin":
                return redirect("/admin")
            else:
                return redirect("/aluno")

        return "Login inválido"

    return render_template_string("""
        <h2>Cursinho Diferencial</h2>
        <form method="POST">
            Login: <input name="login"><br><br>
            Senha: <input type="password" name="senha"><br><br>
            <button type="submit">Entrar</button>
        </form>
    """)


# =========================
# PAINEL ADMIN
# =========================
@app.route("/admin")
def admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    return """
    <h2>Painel Admin - Cursinho Diferencial</h2>
    <br>
    <a href="/turmas">🎓 Gerenciar Turmas</a><br><br>
    <a href="/matricular">👥 Matricular Aluno</a><br><br>
    <a href="/logout">🚪 Sair</a>
    """


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# LISTAR TURMAS
# =========================
@app.route("/turmas")
def turmas():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM turmas ORDER BY id DESC")
    lista = cur.fetchall()
    cur.close()
    conn.close()

    html = """
    <h2>Gerenciar Turmas</h2>
    <a href="/admin">⬅ Voltar</a><br><br>
    <a href="/nova-turma">➕ Criar Nova Turma</a><br><br>
    <ul>
    """

    for turma in lista:
        html += f"<li>{turma[1]} - <a href='/excluir-turma/{turma[0]}'>Excluir</a></li>"

    html += "</ul>"

    return html


# =========================
# CRIAR NOVA TURMA
# =========================
@app.route("/nova-turma", methods=["GET", "POST"])
def nova_turma():
    if session.get("tipo") != "admin":
        return redirect("/login")

    if request.method == "POST":
        nome = request.form["nome"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO turmas (nome) VALUES (%s)", (nome,))
        conn.commit()
        cur.close()
        conn.close()

        return redirect("/turmas")

    return """
    <h2>Criar Nova Turma</h2>
    <a href="/turmas">⬅ Voltar</a><br><br>
    <form method="POST">
        Nome da turma: <input name="nome" required><br><br>
        <button type="submit">Salvar</button>
    </form>
    """


# =========================
# EXCLUIR TURMA
# =========================
@app.route("/excluir-turma/<int:id>")
def excluir_turma(id):
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM turmas WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/turmas")


# =========================
# MATRICULAR ALUNO
# =========================
@app.route("/matricular", methods=["GET", "POST"])
def matricular():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM turmas")
    turmas = cur.fetchall()

    if request.method == "POST":
        nome = request.form["nome"]
        login = request.form["login"]
        senha = request.form["senha"]
        turma_id = request.form["turma"]
        data_matricula = request.form["data_matricula"]

        senha_hash = generate_password_hash(senha)

        cur.execute("""
            INSERT INTO usuarios (nome, login, senha, tipo, turma_id, data_matricula)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (nome, login, senha_hash, "aluno", turma_id, data_matricula))

        usuario_id = cur.fetchone()[0]

        data_base = datetime.strptime(data_matricula, "%Y-%m-%d")

        for i in range(12):
            vencimento = data_base + timedelta(days=30*i)
            cur.execute("""
                INSERT INTO pagamentos (usuario_id, mes, ano, vencimento)
                VALUES (%s, %s, %s, %s)
            """, (
                usuario_id,
                vencimento.month,
                vencimento.year,
                vencimento.date()
            ))

        conn.commit()
        cur.close()
        conn.close()

        return redirect("/admin")

    html = """
    <h2>Matricular Novo Aluno</h2>
    <a href="/admin">⬅ Voltar</a><br><br>
    <form method="POST">
        Nome: <input name="nome" required><br><br>
        Login: <input name="login" required><br><br>
        Senha: <input name="senha" required><br><br>
        Data da matrícula: <input type="date" name="data_matricula" required><br><br>
        Turma:
        <select name="turma" required>
    """

    for turma in turmas:
        html += f"<option value='{turma[0]}'>{turma[1]}</option>"

    html += """
        </select><br><br>
        <button type="submit">Matricular</button>
    </form>
    """

    cur.close()
    conn.close()

    return html


# =========================
# PAINEL ALUNO
# =========================
@app.route("/aluno")
def aluno():
    if session.get("tipo") != "aluno":
        return redirect("/login")

    return "<h2>Painel do Aluno</h2>"
