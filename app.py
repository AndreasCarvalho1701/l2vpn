import sqlite3
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for
import asyncio
import asyncssh
import json
import re

app = Flask(__name__)

# Função para conectar ao banco de dados
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Função para criar a tabela de cidades se não existir
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

# Inicializar banco de dados
initialize_db()

# Função para limpar a saída de dados SSH
def clean_output(output):
    """
    Remove caracteres de escape ANSI e formata a saída.

    Args:
        output (str): Saída bruta dos comandos SSH.

    Retorna:
        str: Saída limpa e formatada.
    """
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    output = re.sub(r'\n+', '\n', output)
    return output.strip()

# Classe para gerenciar conexões SSH persistentes de forma assíncrona
class SSHConnectionPool:
    def __init__(self):
        self.connections = {}
        self.lock = asyncio.Lock()

    async def get_connection(self, ip_address, username, password):
        async with self.lock:
            if ip_address in self.connections:
                return self.connections[ip_address]
            else:
                conn = await asyncssh.connect(ip_address, username=username, password=password, known_hosts=None)
                self.connections[ip_address] = conn
                return conn

    async def close_all(self):
        async with self.lock:
            for conn in self.connections.values():
                conn.close()
            self.connections.clear()

# Remover a instância global do pool de conexões
# connection_pool = SSHConnectionPool()

# Função assíncrona para executar comandos SSH
async def execute_ssh(ip_address, commands, username, password, connection_pool):
    try:
        conn = await connection_pool.get_connection(ip_address, username, password)
        # Processar os comandos
        commands_list = [cmd.strip() for cmd in commands.strip().split('\n') if cmd.strip()]
        commands_combined = '\n'.join(commands_list)
        result = await conn.run(commands_combined, check=False)
        # Capturar stdout e stderr
        output = result.stdout + result.stderr
        output = clean_output(output)
        output_lines = output.split('\n')
        return {
            "commands_sent": commands_list,
            "config_output": output_lines
        }
    except Exception as e:
        return {"error": str(e)}

# Função assíncrona para configurar um dispositivo
async def configure_device(ip, commands, username, password, responses, key, connection_pool):
    response = await execute_ssh(ip, commands, username, password, connection_pool)
    responses[key] = response

@app.route('/')
def index():
    conn = get_db_connection()
    cidades = conn.execute('SELECT nome FROM cidades').fetchall()
    conn.close()
    return render_template('index.html', cidades=cidades)

@app.route('/configure-l2vpn', methods=['POST'])
def configure_l2vpn():
    # Obter o loop de eventos atual
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Instanciar o pool de conexões dentro do loop de eventos
    connection_pool = SSHConnectionPool()

    cidade_pe1 = request.form.get('cidade_pe1')
    cidade_pe2 = request.form.get('cidade_pe2')

    # Verificar se as cidades são diferentes
    if cidade_pe1 == cidade_pe2:
        return jsonify({"error": "As cidades PE1 e PE2 devem ser diferentes"}), 400

    conn = get_db_connection()
    ip_pe1_row = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_pe1,)).fetchone()
    ip_pe2_row = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_pe2,)).fetchone()
    conn.close()

    if not ip_pe1_row or not ip_pe2_row:
        return jsonify({"error": "Cidades não encontradas no banco de dados"}), 400

    # Atribuir corretamente os endereços IP
    ip_pe1 = ip_pe1_row['ip']
    ip_pe2 = ip_pe2_row['ip']

    # Debug: Verificar os endereços IP
    print(f"ip_pe1: {ip_pe1}")
    print(f"ip_pe2: {ip_pe2}")

    # Obter os parâmetros do formulário
    vpws_group_name_pe1 = request.form.get('vpws_group_name_pe1')
    vpn_id_pe1 = request.form.get('vpn_id_pe1')
    neighbor_ip_pe1 = request.form.get('neighbor_ip_pe1')
    pw_vlan_pe1 = request.form.get('pw_vlan_pe1')
    pw_id_pe1 = request.form.get('pw_id_pe1')
    access_interface_pe1 = request.form.get('access_interface_pe1')
    dot1q_pe1 = request.form.get('dot1q_pe1')
    neighbor_targeted_ip_pe1 = request.form.get('neighbor_targeted_ip_pe1')

    vpws_group_name_pe2 = request.form.get('vpws_group_name_pe2')
    vpn_id_pe2 = request.form.get('vpn_id_pe2')
    neighbor_ip_pe2 = request.form.get('neighbor_ip_pe2')
    pw_vlan_pe2 = request.form.get('pw_vlan_pe2')
    pw_id_pe2 = request.form.get('pw_id_pe2')
    access_interface_pe2 = request.form.get('access_interface_pe2')
    dot1q_pe2 = request.form.get('dot1q_pe2')
    neighbor_targeted_ip_pe2 = request.form.get('neighbor_targeted_ip_pe2')

    # Obter credenciais de login
    username = request.form.get('login')
    password = request.form.get('senha')

    # Construir os comandos para cada PE
    pe1_commands = f"""
config
mpls l2vpn vpws-group {vpws_group_name_pe1} vpn {vpn_id_pe1} neighbor {neighbor_ip_pe1}
pw-type vlan {pw_vlan_pe1}
pw-load-balance flow-label both
pw-id {pw_id_pe1}
exit
access-interface {access_interface_pe1}
dot1q {dot1q_pe1}
top
mpls ldp lsr-id loopback-0 neighbor targeted {neighbor_targeted_ip_pe1}
top
commit
"""

    pe2_commands = f"""
config
mpls l2vpn vpws-group {vpws_group_name_pe2} vpn {vpn_id_pe2} neighbor {neighbor_ip_pe2}
pw-type vlan {pw_vlan_pe2}
pw-load-balance flow-label both
pw-id {pw_id_pe2}
exit
access-interface {access_interface_pe2}
dot1q {dot1q_pe2}
top
mpls ldp lsr-id loopback-0 neighbor targeted {neighbor_targeted_ip_pe2}
top
commit
"""

    responses = {}

    # Criar tarefas assíncronas para configurar os dispositivos
    tasks = [
        configure_device(ip_pe1, pe1_commands, username, password, responses, 'PE1_response', connection_pool),
        configure_device(ip_pe2, pe2_commands, username, password, responses, 'PE2_response', connection_pool),
    ]

    # Executar as tarefas assíncronas
    loop.run_until_complete(asyncio.gather(*tasks))
    loop.run_until_complete(connection_pool.close_all())

    response_data = {
        'PE1_response': responses.get('PE1_response', {}),
        'PE2_response': responses.get('PE2_response', {})
    }

    return Response(
        json.dumps(response_data, indent=2),
        mimetype='application/json'
    )

# Página para adicionar novas cidades
@app.route('/manage-cities')
def manage_cities():
    return '''
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Gerenciar Cidades</title>
        </head>
        <body style="background-color: black; color: green;">
            <h1>Gerenciar Cidades</h1>
            <form action="/add-city" method="post">
                <label for="cidade_nome">Nome da Cidade:</label>
                <input type="text" id="cidade_nome" name="cidade_nome" required><br><br>
                <label for="cidade_ip">IP da Cidade:</label>
                <input type="text" id="cidade_ip" name="cidade_ip" required><br><br>
                <button type="submit">Adicionar Cidade</button>
            </form>
            <br>
            <a href="/">Voltar para Configuração de L2VPN</a>
        </body>
        </html>
    '''

# Rota para adicionar nova cidade ao banco
@app.route('/add-city', methods=['POST'])
def add_city():
    cidade_nome = request.form.get('cidade_nome')
    cidade_ip = request.form.get('cidade_ip')

    if cidade_nome and cidade_ip:
        conn = get_db_connection()
        conn.execute('INSERT INTO cidades (nome, ip) VALUES (?, ?)', (cidade_nome, cidade_ip))
        conn.commit()
        conn.close()

    return redirect(url_for('manage_cities'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
