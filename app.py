import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date

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


def criar_admin():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM usuarios WHERE login = %s", ("admin",))
    if not cur.fetchone():
        senha_hash = generate_password_hash("123456")
        cur.execute("""
            INSERT INTO usuarios (nome, login, senha, tipo)
            VALUES (%s, %s, %s, %s)
        """, ("Administrador", "admin", senha_hash, "admin"))
        conn.commit()

    cur.close()
    conn.close()


# =========================
# INICIALIZAR BANCO
# =========================
@app.route("/init")
def init():
    criar_tabelas()
    criar_admin()
    return "Banco inicializado com sucesso!"


# =========================
# FUNÇÃO DE VERIFICAÇÃO DE BLOQUEIO
# =========================
def verificar_status_aluno(usuario_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT vencimento, status
        FROM pagamentos
        WHERE usuario_id=%s
        AND status='pendente'
        ORDER BY vencimento ASC
        LIMIT 1
    """, (usuario_id,))

    registro = cur.fetchone()
    cur.close()
    conn.close()

    if not registro:
        return "ativo", None

    vencimento = registro[0]
    hoje = date.today()

    if hoje < vencimento:
        return "ativo", vencimento

    if hoje == vencimento:
        return "vence_hoje", vencimento

    if hoje <= vencimento + timedelta(days=7):
        return "atrasado", vencimento

    return "bloqueado", vencimento


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
# ADMIN
# =========================
@app.route("/admin")
def admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    return """
    <h2>Painel Admin</h2>
    <a href="/turmas">Turmas</a><br><br>
    <a href="/matricular">Matricular Aluno</a><br><br>
    <a href="/logout">Sair</a>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# TURMAS
# =========================
@app.route("/turmas")
def turmas():
    if session.get("tipo") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM turmas")
    lista = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h2>Turmas</h2><a href='/admin'>Voltar</a><br><br>"
    html += "<a href='/nova-turma'>Nova Turma</a><br><br>"

    for turma in lista:
        html += f"{turma[1]} - <a href='/excluir-turma/{turma[0]}'>Excluir</a><br>"

    return html


@app.route("/nova-turma", methods=["GET", "POST"])
def nova_turma():
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
    <h2>Nova Turma</h2>
    <form method="POST">
        Nome: <input name="nome"><br><br>
        <button type="submit">Salvar</button>
    </form>
    """


@app.route("/excluir-turma/<int:id>")
def excluir_turma(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM turmas WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/turmas")


# =========================
# MATRICULAR
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
        senha = generate_password_hash(request.form["senha"])
        turma_id = request.form["turma"]
        data_matricula = request.form["data_matricula"]

        cur.execute("""
            INSERT INTO usuarios (nome, login, senha, tipo, turma_id, data_matricula)
            VALUES (%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (nome, login, senha, "aluno", turma_id, data_matricula))

        usuario_id = cur.fetchone()[0]

        base = datetime.strptime(data_matricula, "%Y-%m-%d")

        for i in range(12):
            venc = base + timedelta(days=30*i)
            cur.execute("""
                INSERT INTO pagamentos (usuario_id, mes, ano, vencimento)
                VALUES (%s,%s,%s,%s)
            """, (usuario_id, venc.month, venc.year, venc.date()))

        conn.commit()
        cur.close()
        conn.close()
        return redirect("/admin")

    html = "<h2>Matricular</h2><a href='/admin'>Voltar</a><br><br>"
    html += "<form method='POST'>"
    html += "Nome: <input name='nome'><br><br>"
    html += "Login: <input name='login'><br><br>"
    html += "Senha: <input name='senha'><br><br>"
    html += "Data: <input type='date' name='data_matricula'><br><br>"
    html += "Turma: <select name='turma'>"
    for t in turmas:
        html += f"<option value='{t[0]}'>{t[1]}</option>"
    html += "</select><br><br>"
    html += "<button type='submit'>Salvar</button></form>"

    return html


# =========================
# VER PAGAMENTOS (ADMIN)
# =========================
@app.route("/pagamentos/<int:usuario_id>")
def ver_pagamentos(usuario_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, mes, ano, vencimento, status
        FROM pagamentos
        WHERE usuario_id=%s
        ORDER BY vencimento
    """, (usuario_id,))
    lista = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h2>Pagamentos</h2><a href='/admin'>Voltar</a><br><br>"

    for p in lista:
        html += f"{p[1]}/{p[2]} - {p[3]} - {p[4]}"
        if p[4] == "pendente":
            html += f" - <a href='/marcar-pago/{p[0]}'>Marcar como pago</a>"
        html += "<br>"

    return html


@app.route("/marcar-pago/<int:id>")
def marcar_pago(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE pagamentos
        SET status='pago', data_pagamento=%s
        WHERE id=%s
    """, (date.today(), id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(request.referrer)


# =========================
# PAINEL ALUNO
# =========================
@app.route("/aluno")
def aluno():
    if session.get("tipo") != "aluno":
        return redirect("/login")

    usuario_id = session["user_id"]
    status, vencimento = verificar_status_aluno(usuario_id)

    if status == "bloqueado":
        return "<h2>Seu acesso foi bloqueado por inadimplência.</h2>"

    aviso = ""
    if status == "vence_hoje":
        aviso = "<p>⚠️ Sua mensalidade vence hoje.</p>"
    elif status == "atrasado":
        dias = (date.today() - vencimento).days
        aviso = f"<p>❗ Mensalidade vencida há {dias} dias.</p>"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT mes, ano, vencimento, status
        FROM pagamentos
        WHERE usuario_id=%s
        ORDER BY vencimento
    """, (usuario_id,))
    lista = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h2>Painel do Aluno</h2>"
    html += aviso
    html += "<h3>Histórico</h3>"

    for p in lista:
        html += f"{p[0]}/{p[1]} - {p[2]} - {p[3]}<br>"

    html += "<br><a href='/logout'>Sair</a>"

    return html
