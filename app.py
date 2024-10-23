from flask import Flask, render_template, request, jsonify, Response
import paramiko
import time
import json
import re

def execute_ssh(ip_address, commands):
    try:
        # Captura o login e a senha diretamente do formulário
        username = request.form.get('login')
        password = request.form.get('senha')

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Conecta ao dispositivo usando o login e a senha capturados
        ssh.connect(ip_address, username=username, password=password)
        
        remote_conn = ssh.invoke_shell()
        output = ""
        
        # Envia os comandos de configuração
        for command in commands.strip().split('\n'):
            remote_conn.send(command.strip() + '\n')
            time.sleep(1)
            while remote_conn.recv_ready():
                output += remote_conn.recv(4096).decode('utf-8')

        # Envia o comando adicional para verificar as alterações
        verification_command = "show configuration commit changes\n"
        remote_conn.send(verification_command)
        time.sleep(2)
        
        verification_output = ""
        while remote_conn.recv_ready():
            verification_output += remote_conn.recv(4096).decode('utf-8')

        ssh.close()

        # Limpa e organiza as saídas
        output = clean_output(output)
        verification_output = clean_output(verification_output)

        # Quebra as saídas em listas de linhas
        output_lines = output.split('\n')
        verification_output_lines = verification_output.split('\n')

        return {
            "config_output": output_lines,
            "verification_output": verification_output_lines
        }
        
    except Exception as e:
        return {"error": str(e)}

# Função para limpar a saída
def clean_output(output):
    # Remove sequências de escape ANSI
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)
    
    # Substitui \r\n e \r por \n
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove múltiplas quebras de linha consecutivas
    output = re.sub(r'\n+', '\n', output)
    
    # Remove espaços em branco extras
    output = output.strip()
    
    return output

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configure-l2vpn', methods=['POST'])
def configure_l2vpn():

    # Capturando os valores dos campos HOSTA e HOSTB do formulário
    host_a = request.form.get('HOSTA')
    host_b = request.form.get('HOSTB')

    vpws_group_name_pe1 = request.form.get('vpws_group_name_pe1')
    vpn_id_pe1 = request.form.get('vpn_id_pe1')
    neighbor_ip_pe1 = request.form.get('neighbor_ip_pe1')
    pw_vlan_pe1 = request.form.get('pw_vlan_pe1')
    pw_id_pe1 = request.form.get('pw_id_pe1')
    access_interface_pe1 = request.form.get('access_interface_pe1')
    dot1q_pe1 = request.form.get('dot1q_pe1')
    neighbor_targeted_ip_pe1 = request.form.get('neighbor_targeted_ip_pe1')

    # Variáveis PE2

    vpws_group_name_pe2 = request.form.get('vpws_group_name_pe2')
    vpn_id_pe2 = request.form.get('vpn_id_pe2')
    neighbor_ip_pe2 = request.form.get('neighbor_ip_pe2')
    pw_vlan_pe2 = request.form.get('pw_vlan_pe2')
    pw_id_pe2 = request.form.get('pw_id_pe2')
    access_interface_pe2 = request.form.get('access_interface_pe2')
    dot1q_pe2 = request.form.get('dot1q_pe2')
    neighbor_targeted_ip_pe2 = request.form.get('neighbor_targeted_ip_pe2')

    # Comandos para PE1
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

    # Comandos para PE2
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

    # Executar os comandos via SSH nos hosts fornecidos
    response_pe1 = execute_ssh(host_a, pe1_commands)
    response_pe2 = execute_ssh(host_b, pe2_commands)

    # Preparar a resposta JSON
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

    # Retornar o JSON formatado com indentação
    return Response(
        json.dumps(response_data, indent=2),
        mimetype='application/json'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
