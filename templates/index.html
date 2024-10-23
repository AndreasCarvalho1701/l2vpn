from flask import Flask, render_template, request, jsonify
import paramiko
import time

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
        
        # Envia os comandos linha por linha
        for command in commands.strip().split('\n'):
            remote_conn.send(command.strip() + '\n')
            time.sleep(1)
            while remote_conn.recv_ready():
                output += remote_conn.recv(4096).decode('utf-8')
        
        ssh.close()
        
        return {"output": output}
        
    except Exception as e:
        return {"error": str(e)}

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configure-l2vpn', methods=['POST'])
def configure_l2vpn():

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

    # Executar os comandos via SSH
    response_pe1 = execute_ssh('177.66.5.82', pe1_commands)
    response_pe2 = execute_ssh('177.66.5.84', pe2_commands)

    return jsonify({
        "PE1_response": response_pe1,
        "PE2_response": response_pe2
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
