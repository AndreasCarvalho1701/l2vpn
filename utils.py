# utils.py
import re
import time
import paramiko

def clean_output(output):
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    output = re.sub(r'\n+', '\n', output)
    return output.strip()

def execute_ssh(ip_address, commands, username, password, connection_pool):
    try:
        connection_start_time = time.time()
        conn = connection_pool.get_connection(ip_address, username, password)
        connection_end_time = time.time()
        connection_time = connection_end_time - connection_start_time

        # Processa os comandos
        commands_list = [cmd.strip() for cmd in commands.strip().split('\n') if cmd.strip()]
        commands_combined = '\n'.join(commands_list)

        run_start_time = time.time()
        stdin, stdout, stderr = conn.exec_command(commands_combined)
        output = stdout.read().decode() + stderr.read().decode()
        run_end_time = time.time()
        run_time = run_end_time - run_start_time

        # Limpa a saída
        output = clean_output(output)
        output_lines = output.split('\n')
        return {
            "commands_sent": commands_list,
            "config_output": output_lines,
            "connection_time_seconds": round(connection_time, 2),
            "run_time_seconds": round(run_time, 2)
        }
    except Exception as e:
        return {"error": str(e)}

def configure_device(ip, commands, username, password, key, connection_pool):
    device_start_time = time.time()
    response = execute_ssh(ip, commands, username, password, connection_pool)
    device_end_time = time.time()
    response['device_execution_time_seconds'] = round(device_end_time - device_start_time, 2)
    return response
