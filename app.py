import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chave_super_secreta_123"

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

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

    conn.commit()
    cur.close()
    conn.close()

def criar_admin():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM usuarios WHERE login = 'admin'")
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
        <h2>Login</h2>
        <form method="POST">
            Login: <input name="login"><br><br>
            Senha: <input type="password" name="senha"><br><br>
            <button type="submit">Entrar</button>
        </form>
    """)

@app.route("/admin")
def admin():
    if session.get("tipo") != "admin":
        return redirect("/login")

    return """
    <h2>Painel Admin</h2>
    <p>Sistema iniciado com sucesso 🚀</p>
    """

@app.route("/aluno")
def aluno():
    if session.get("tipo") != "aluno":
        return redirect("/login")

    return "<h2>Painel do Aluno</h2>"

if __name__ == "__main__":
    criar_tabelas()
    criar_admin()
    app.run(debug=True)
