import asyncio
import json
import time
import subprocess
import sqlite3
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session, flash
from concurrent.futures import ThreadPoolExecutor
from flask_apscheduler import APScheduler
from functools import wraps
import bcrypt
from datetime import datetime
# Suas outras importações personalizadas aqui
from db import get_db_connection,get_user_db_connection, initialize_user_db, initialize_db, check_user_credentials, create_admin_user, get_user_log_db_connection
from utils import clean_output, configure_device, log_operacao, delete_old_logs
from ssh_pool import SSHConnectionPool



app = Flask(__name__)
app.secret_key = 'teste'  # Coloque uma chave secreta aqui

# Initialize the databases
initialize_user_db()
create_admin_user()
initialize_db()

# Instantiate the global SSH connection pool
connection_pool = SSHConnectionPool()

# Schedule job to delete old logs
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@scheduler.task('interval', id='delete_old_logs', weeks=52)
def scheduled_delete():
    delete_old_logs()
    
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
    


# Rota para editar uma cidade (GET para exibir o formulário, POST para salvar)


# Rota para a página de administração (apenas para administradores)
@app.route('/admin', methods=['GET'])
@login_required
def admin_page():
    if session.get('tipo_usuario') != 'admin':
        return redirect(url_for('home'))

# Function to require login for protected routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Check user credentials
def check_user_credentials(username, password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE nome = ?', (username,)).fetchone()
    conn.close()

    if user:
        # Mensagens de depuração para checar os valores
        print(f"Tentativa de login para: {username}")
        print(f"Senha fornecida: {password}")
        print(f"Hash armazenado: {user['senha']}")

        # Verifique se a senha digitada corresponde ao hash armazenado
        if bcrypt.checkpw(password.encode('utf-8'), user['senha'].encode('utf-8')):
            return user
    return None
from datetime import datetime

from datetime import datetime

# Query para capturar logs com base no nome do usuário, cidade e descrição
@app.route('/logs', methods=['GET'])
@login_required
def view_logs():
    # Verifique se o usuário é um administrador
    if session.get('tipo_usuario') != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('configure_l2vpn'))

    # Obter parâmetros do formulário de filtro
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    cidade_alterada = request.args.get('cidade_alterada')
    descricao_operacao = request.args.get('descricao_operacao')

    # Conectar ao banco de dados de logs
    conn_logs = sqlite3.connect('logs.db')
    query = '''
        SELECT logs_operacoes.*, usuarios.nome as usuario_nome
        FROM logs_operacoes
        LEFT JOIN usuarios ON logs_operacoes.usuario_id = usuarios.id
        WHERE 1=1
    '''
    params = []

    # Filtros opcionais
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
            query += ' AND data_operacao BETWEEN ? AND ?'
            params.append(start_date)
            params.append(end_date)
        except ValueError:
            flash('Formato de data e hora inválido!', 'error')

    if cidade_alterada:
        query += ' AND cidade_alterada LIKE ?'
        params.append(f"%{cidade_alterada}%")

    if descricao_operacao:
        query += ' AND descricao_operacao LIKE ?'
        params.append(f"%{descricao_operacao}%")

    query += ' ORDER BY data_operacao DESC'

    # Executar a query filtrada
    logs = conn_logs.execute(query, params).fetchall()
    conn_logs.close()

    # Carregar informações dos usuários do banco `usuarios_log.db`
    conn_log_users = get_user_log_db_connection()
    usuarios = conn_log_users.execute('SELECT id, nome FROM usuarios').fetchall()
    conn_log_users.close()

    # Renderizar a página de logs com os resultados filtrados
    return render_template('logs.html', logs=logs, usuarios=usuarios)



# Rota para a página inicial que redireciona para a página de login
@app.route('/')
def home():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('configure_l2vpn'))

# Route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('login')
        password = request.form.get('senha')
        user = check_user_credentials(username, password)
        if user:
            session['usuario_id'] = user['id']
            session['tipo_usuario'] = user['tipo_usuario']
            return redirect(url_for('configure_l2vpn'))
        else:
            return "Login falhou. Verifique suas credenciais.", 401
    return render_template('login.html')

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
        result = subprocess.run(['ping', '-c', '4', ip_address], capture_output=True, text=True)
        if result.returncode == 0:
            output_lines = result.stdout.split('\n')
            stats_line = next(line for line in output_lines if 'min/avg/max' in line)
            avg_latency = stats_line.split('=')[-1].split('/')[1].strip()
            return {"ip": ip_address, "avg_latency_ms": avg_latency}
        else:
            return {"ip": ip_address, "error": "Ping failed"}
    except Exception as e:
        return {"ip": ip_address, "error": str(e)}

# Rota para configuração L2VPN
@app.route('/configure-l2vpn', methods=['GET', 'POST'])
@login_required
def configure_l2vpn():
    if request.method == 'POST':
        # Início da medição de tempo
        start_time = time.time()

        # Recupera as cidades selecionadas no formulário
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

        # Recupera os parâmetros do formulário para PE1 e PE2
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

        # Registrar a operação no log com descrição detalhada
        usuario_id = session.get('usuario_id')
        descricao = f"Alterou a configuração L2VPN entre PE1: {cidade_pe1} e PE2: {cidade_pe2}"
        log_operacao(usuario_id, descricao)

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
    
    # Se for um GET, exibe o formulário
    conn = get_db_connection()
    cidades = conn.execute('SELECT * FROM cidades').fetchall()
    conn.close()
    return render_template('configure_l2vpn.html', cidades=cidades)


@app.route('/manage-cities', methods=['GET'])
@login_required
def manage_cities():
    conn = get_db_connection()
    try:
        cidades = conn.execute('SELECT * FROM cidades').fetchall()
    except Exception as e:
        flash(f'Ocorreu um erro ao carregar as cidades: {str(e)}', 'error')
        cidades = []
    finally:
        conn.close()

    # Renderiza a página de gerenciamento de cidades
    return render_template('manage_cities.html', cidades=cidades)

@app.route('/add-city', methods=['POST'])
@login_required
def add_city():
    nome_cidade = request.form.get('nome_cidade')
    ip_cidade = request.form.get('ip_cidade')

    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO cidades (nome, ip) VALUES (?, ?)', (nome_cidade, ip_cidade))
        conn.commit()
        conn.close()

        # Registrar a operação no log
        descricao = "Adicionou cidade"
        log_operacao(usuario_id=session.get('usuario_id'), descricao=descricao, cidade=nome_cidade)
        
        flash('Cidade adicionada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar a cidade: {e}', 'error')

    return redirect(url_for('manage_cities'))





    
@app.route('/edit-city/<int:city_id>', methods=['GET', 'POST'])
@login_required
def edit_city(city_id):
    conn = get_db_connection()

    if request.method == 'GET':
        cidade = conn.execute('SELECT id, nome, ip FROM cidades WHERE id = ?', (city_id,)).fetchone()
        if not cidade:
            flash('Cidade não encontrada.', 'error')
            return redirect(url_for('manage_cities'))
        
        return render_template('edit_city.html', cidade=cidade)

    try:
        novo_nome = request.form.get('nome')
        novo_ip = request.form.get('ip')

        cidade_antiga = conn.execute('SELECT nome, ip FROM cidades WHERE id = ?', (city_id,)).fetchone()

        if cidade_antiga:
            conn.execute('UPDATE cidades SET nome = ?, ip = ? WHERE id = ?', (novo_nome, novo_ip, city_id))
            conn.commit()

            # Registrar a operação no log
            descricao = "Editou cidade"
            log_operacao(usuario_id=session.get('usuario_id'), descricao=descricao, cidade=novo_nome)

            flash('Cidade editada com sucesso!', 'success')
        else:
            flash('Cidade não encontrada.', 'error')
    except Exception as e:
        flash(f'Erro ao editar a cidade: {e}', 'error')
    finally:
        conn.close()

    return redirect(url_for('manage_cities'))





@app.route('/delete-city/<int:city_id>', methods=['POST'])
@login_required
def delete_city(city_id):
    try:
        conn = get_db_connection()
        cidade = conn.execute('SELECT nome FROM cidades WHERE id = ?', (city_id,)).fetchone()
        if cidade:
            conn.execute('DELETE FROM cidades WHERE id = ?', (city_id,))
            conn.commit()
            conn.close()

            # Registrar a operação no log
            descricao = "Apagou cidade"
            log_operacao(usuario_id=session.get('usuario_id'), descricao=descricao, cidade=cidade['nome'])

            flash('Cidade apagada com sucesso!', 'success')
        else:
            flash('Cidade não encontrada.', 'error')
    except Exception as e:
        flash(f'Erro ao apagar a cidade: {e}', 'error')

    return redirect(url_for('manage_cities'))



def log_operacao(usuario_id, descricao, cidade=None):
    conn = sqlite3.connect('logs.db')
    conn.execute('''
        INSERT INTO logs_operacoes (usuario_id, descricao_operacao, cidade_alterada)
        VALUES (?, ?, ?)
    ''', (usuario_id, descricao, cidade))
    conn.commit()
    conn.close()




if __name__ == '__main__':
    # Execute a aplicação Flask
    app.run(host='0.0.0.0', port=5000)
