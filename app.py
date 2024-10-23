import sqlite3
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for

import paramiko
import time
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
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    output = re.sub(r'\n+', '\n', output)
    return output.strip()

# Função para executar comandos SSH
def execute_ssh(ip_address, commands):
    try:
        username = request.form.get('login')
        password = request.form.get('senha')

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip_address, username=username, password=password)

        remote_conn = ssh.invoke_shell()
        output = ""

        for command in commands.strip().split('\n'):
            remote_conn.send(command.strip() + '\n')
            time.sleep(0.125)
            while remote_conn.recv_ready():
                output += remote_conn.recv(4096).decode('utf-8')

        verification_command = "show configuration commit changes\n"
        remote_conn.send(verification_command)
        time.sleep(0.25)

        verification_output = ""
        while remote_conn.recv_ready():
            verification_output += remote_conn.recv(4096).decode('utf-8')

        ssh.close()

        output = clean_output(output)
        verification_output = clean_output(verification_output)

        output_lines = output.split('\n')
        verification_output_lines = verification_output.split('\n')

        return {
            "config_output": output_lines,
            "verification_output": verification_output_lines
        }

    except Exception as e:
        return {"error": str(e)}

@app.route('/')
def index():
    conn = get_db_connection()
    cidades = conn.execute('SELECT nome FROM cidades').fetchall()
    conn.close()
    return render_template('index.html', cidades=cidades)

@app.route('/configure-l2vpn', methods=['POST'])
def configure_l2vpn():
    cidade_pe1 = request.form.get('cidade_pe1')
    cidade_pe2 = request.form.get('cidade_pe2')

    conn = get_db_connection()
    ip_pe1 = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_pe1,)).fetchone()['ip']
    ip_pe2 = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_pe2,)).fetchone()['ip']
    conn.close()

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

    response_pe1 = execute_ssh(ip_pe1, pe1_commands)
    response_pe2 = execute_ssh(ip_pe2, pe2_commands)

    response_data = {
        "PE1_response": {
            "config_output": response_pe1.get("config_output", []),
            "verification_output": response_pe1.get("verification_output", [])
        },
        "PE2_response": {
            "config_output": response_pe2.get("config_output", []),
            "verification_output": response_pe2.get("verification_output", [])
        }
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
    app.run(host='0.0.0.0', port=5000, debug=True)
