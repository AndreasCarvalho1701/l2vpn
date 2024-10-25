import sqlite3
import bcrypt

# Função para conectar ao banco de dados das cidades
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Função para conectar ao banco de dados dos usuários
def get_user_db_connection():
    conn = sqlite3.connect('usuarios.db')
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar o banco de dados das cidades
def initialize_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ip TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Inicializar o banco de dados dos usuários
def initialize_user_db():
    conn = get_user_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo_usuario TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Verificar credenciais do usuário pelo nome
def check_user_credentials(username, password):
    conn = get_user_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE nome = ?', (username,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user['senha'].encode('utf-8')):
        return user
    return None

# Criar um usuário admin para teste (apenas execute uma vez)
def create_admin_user():
    nome = "Andreas"
    senha = "teste"
    tipo_usuario = "admin"

    conn = get_user_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE nome = ?', (nome,)).fetchone()
    
    if not user:
        hashed_senha = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
        conn.execute('''
            INSERT INTO usuarios (nome, senha, tipo_usuario)
            VALUES (?, ?, ?)
        ''', (nome, hashed_senha.decode('utf-8'), tipo_usuario))
        conn.commit()
        print("Usuário admin criado com sucesso!")
    else:
        print("O usuário admin já existe.")
    
    conn.close()

# Função para conectar ao novo banco de dados dos usuários para logs
def get_user_log_db_connection():
    conn = sqlite3.connect('usuarios_log.db')
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar o banco de dados dos usuários para logs
def initialize_user_log_db():
    conn = get_user_log_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            tipo_usuario TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Função para sincronizar usuários entre bancos
def sync_users_to_log_db():
    # Obter os usuários do banco original
    conn_users = get_user_db_connection()
    users = conn_users.execute('SELECT id, nome, tipo_usuario FROM usuarios').fetchall()
    conn_users.close()

    # Inserir os usuários no banco de logs
    conn_log_users = get_user_log_db_connection()
    conn_log_users.execute('DELETE FROM usuarios')  # Limpa a tabela antes de sincronizar
    conn_log_users.executemany('''
        INSERT INTO usuarios (id, nome, tipo_usuario)
        VALUES (?, ?, ?)
    ''', [(user['id'], user['nome'], user['tipo_usuario']) for user in users])
    conn_log_users.commit()
    conn_log_users.close()

# Inicializar e sincronizar bancos ao iniciar
initialize_user_log_db()
sync_users_to_log_db()