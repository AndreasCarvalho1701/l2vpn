import re
import time
import sqlite3
from ssh_pool import SSHConnectionPool

# Function to clean SSH output
def clean_output(output):
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    output = re.sub(r'\n+', '\n', output)
    return output.strip()

# Function to execute SSH commands
def execute_ssh(ip_address, commands, username, password, connection_pool):
    try:
        # Reuse SSH connection if possible
        connection_start_time = time.time()
        conn = connection_pool.get_connection(ip_address, username, password)
        connection_end_time = time.time()
        connection_time = connection_end_time - connection_start_time

        # Combine commands for single execution
        commands_combined = '\n'.join([cmd.strip() for cmd in commands.strip().split('\n') if cmd.strip()])

        run_start_time = time.time()
        stdin, stdout, stderr = conn.exec_command(commands_combined)
        output = stdout.read().decode() + stderr.read().decode()
        run_end_time = time.time()
        run_time = run_end_time - run_start_time

        output = clean_output(output)
        return {
            "commands_sent": commands_combined.split('\n'),
            "config_output": output.split('\n'),
            "connection_time_seconds": round(connection_time, 2),
            "run_time_seconds": round(run_time, 2)
        }
    except Exception as e:
        return {"error": str(e)}

# Function to log operations
def log_operacao(usuario_id, descricao, cidade):
    conn = sqlite3.connect('logs.db')
    conn.execute('''
        INSERT INTO logs_operacoes (usuario_id, descricao_operacao, cidade_alterada)
        VALUES (?, ?, ?)
    ''', (usuario_id, descricao, cidade))
    conn.commit()
    conn.close()

# Function to delete logs older than 1 year
def delete_old_logs():
    conn = sqlite3.connect('logs.db')
    conn.execute('''
        DELETE FROM logs_operacoes WHERE DATE(data_operacao) <= DATE('now', '-1 year')
    ''')
    conn.commit()
    conn.close()

def configure_device(ip, commands, username, password, key, connection_pool):
    device_start_time = time.time()
    response = execute_ssh(ip, commands, username, password, connection_pool)
    device_end_time = time.time()
    response['device_execution_time_seconds'] = round(device_end_time - device_start_time, 2)
    return response
