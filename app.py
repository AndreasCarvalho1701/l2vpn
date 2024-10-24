import asyncio
import json
import time
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for

from db import get_db_connection, initialize_db
from ssh_pool import SSHConnectionPool
from utils import clean_output, configure_device

app = Flask(__name__)

# Initialize the database
initialize_db()

# Instantiate the global SSH connection pool
connection_pool = SSHConnectionPool()

@app.route('/')
def index():
    conn = get_db_connection()
    cidades = conn.execute('SELECT nome FROM cidades').fetchall()
    conn.close()
    return render_template('index.html', cidades=cidades)

# Adicione a importação
from concurrent.futures import ThreadPoolExecutor

@app.route('/configure-l2vpn', methods=['POST'])
def configure_l2vpn():
    # Início da medição de tempo
    start_time = time.time()
    
    cidade_pe1 = request.form.get('cidade_pe1')
    cidade_pe2 = request.form.get('cidade_pe2')

    # Ensure the cities are different
    if cidade_pe1 == cidade_pe2:
        return jsonify({"error": "As cidades PE1 e PE2 devem ser diferentes"}), 400

    conn = get_db_connection()
    ip_pe1_row = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_pe1,)).fetchone()
    ip_pe2_row = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_pe2,)).fetchone()
    conn.close()

    if not ip_pe1_row or not ip_pe2_row:
        return jsonify({"error": "Cidades não encontradas no banco de dados"}), 400

    ip_pe1 = ip_pe1_row['ip']
    ip_pe2 = ip_pe2_row['ip']

    # Retrieve form parameters for PE1
    vpws_group_name_pe1 = request.form.get('vpws_group_name_pe1')
    vpn_id_pe1 = request.form.get('vpn_id_pe1')
    neighbor_ip_pe1 = request.form.get('neighbor_ip_pe1')
    pw_vlan_pe1 = request.form.get('pw_vlan_pe1')
    pw_id_pe1 = request.form.get('pw_id_pe1')
    access_interface_pe1 = request.form.get('access_interface_pe1')
    dot1q_pe1 = request.form.get('dot1q_pe1')
    neighbor_targeted_ip_pe1 = request.form.get('neighbor_targeted_ip_pe1')

    # Retrieve form parameters for PE2
    vpws_group_name_pe2 = request.form.get('vpws_group_name_pe2')
    vpn_id_pe2 = request.form.get('vpn_id_pe2')
    neighbor_ip_pe2 = request.form.get('neighbor_ip_pe2')
    pw_vlan_pe2 = request.form.get('pw_vlan_pe2')
    pw_id_pe2 = request.form.get('pw_id_pe2')
    access_interface_pe2 = request.form.get('access_interface_pe2')
    dot1q_pe2 = request.form.get('dot1q_pe2')
    neighbor_targeted_ip_pe2 = request.form.get('neighbor_targeted_ip_pe2')

    # Get login credentials
    username = request.form.get('login')
    password = request.form.get('senha')

    # Build commands for PE1
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

    # Build commands for PE2
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

    # Defina uma função wrapper para coletar as respostas
    def configure_device_wrapper(*args):
        key = args[4]
        response = configure_device(*args)
        responses[key] = response

    # Crie um ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Envie as tarefas para o executor
        future1 = executor.submit(configure_device_wrapper, ip_pe1, pe1_commands, username, password, 'PE1_response', connection_pool)
        future2 = executor.submit(configure_device_wrapper, ip_pe2, pe2_commands, username, password, 'PE2_response', connection_pool)

        # Aguarde a conclusão das tarefas
        future1.result()
        future2.result()

    # Calcule o tempo de execução
    end_time = time.time()
    execution_time = end_time - start_time

    response_data = {
        'PE1_response': responses.get('PE1_response', {}),
        'PE2_response': responses.get('PE2_response', {}),
        'execution_time_seconds': round(execution_time, 1)
    }

    return Response(
        json.dumps(response_data, indent=2),
        mimetype='application/json'
    )


# Page to add new cities
@app.route('/manage-cities')
def manage_cities():
    return render_template('manage_cities.html')

# Route to add a new city to the database
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
    # Run the application using uvicorn for async support
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
