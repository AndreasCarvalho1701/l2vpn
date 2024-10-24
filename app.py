import asyncio
import json
import time
import subprocess
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for
from concurrent.futures import ThreadPoolExecutor

from db import get_db_connection, initialize_db
from ssh_pool import SSHConnectionPool
from utils import clean_output, configure_device

app = Flask(__name__)

# Initialize the database
initialize_db()

# Instantiate the global SSH connection pool
connection_pool = SSHConnectionPool()

# Função para pegar o IP da cidade do banco de dados
def get_city_ip(cidade_nome):
    conn = get_db_connection()
    ip_row = conn.execute('SELECT ip FROM cidades WHERE nome = ?', (cidade_nome,)).fetchone()
    conn.close()
    if ip_row:
        return ip_row['ip']
    return None

# Função para realizar o ping e medir latência
def ping_device(ip_address):
    try:
        # Executa o ping com 4 pacotes para calcular média
        result = subprocess.run(['ping', '-c', '4', ip_address], capture_output=True, text=True)
        if result.returncode == 0:
            # Filtra a linha de estatísticas do ping
            output_lines = result.stdout.split('\n')
            stats_line = next(line for line in output_lines if 'min/avg/max' in line)
            # Extrai a média de latência
            avg_latency = stats_line.split('=')[-1].split('/')[1].strip()
            return {"ip": ip_address, "avg_latency_ms": avg_latency}
        else:
            return {"ip": ip_address, "error": "Ping failed"}
    except Exception as e:
        return {"ip": ip_address, "error": str(e)}

@app.route('/configure-l2vpn', methods=['POST'])
def configure_l2vpn():
    # Início da medição de tempo
    start_time = time.time()

    cidade_pe1 = request.form.get('cidade_pe1')
    cidade_pe2 = request.form.get('cidade_pe2')

    # Garantir que as cidades são diferentes
    if cidade_pe1 == cidade_pe2:
        return jsonify({"error": "As cidades PE1 e PE2 devem ser diferentes"}), 400

    # Pega os IPs das cidades do banco de dados
    ip_pe1 = get_city_ip(cidade_pe1)
    ip_pe2 = get_city_ip(cidade_pe2)

    if not ip_pe1 or not ip_pe2:
        return jsonify({"error": "Uma ou ambas as cidades não foram encontradas no banco de dados"}), 400

    # Realiza o ping em ambos os dispositivos antes de configurar
    pe1_ping_result = ping_device(ip_pe1)
    pe2_ping_result = ping_device(ip_pe2)

    # Recupera os parâmetros do formulário para PE1 e PE2 (mesmo código que você já tinha)
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

    # Credenciais de login
    username = request.form.get('login')
    password = request.form.get('senha')

    # Comandos de configuração para PE1
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

    # Comandos de configuração para PE2
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

    def configure_device_wrapper(ip, commands, username, password, key):
        response = configure_device(ip, commands, username, password, key, connection_pool)
        responses[key] = response

    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(configure_device_wrapper, ip_pe1, pe1_commands, username, password, 'PE1_response')
        future2 = executor.submit(configure_device_wrapper, ip_pe2, pe2_commands, username, password, 'PE2_response')
        future1.result()
        future2.result()

    # Calcule o tempo de execução
    end_time = time.time()
    execution_time = end_time - start_time

    # Monta o JSON final com os resultados do ping e das configurações
    response_data = {
        'PE1_response': responses.get('PE1_response', {}),
        'PE2_response': responses.get('PE2_response', {}),
        'PE1_ping': pe1_ping_result,
        'PE2_ping': pe2_ping_result,
        'execution_time_seconds': round(execution_time, 1)
    }

    return Response(
        json.dumps(response_data, indent=2),
        mimetype='application/json'
    )

if __name__ == '__main__':
    # Execute a aplicação Flask
    app.run(host='0.0.0.0', port=5000)
