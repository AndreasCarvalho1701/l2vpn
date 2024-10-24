import re
import asyncio
import time

# Function to clean SSH output
def clean_output(output):
    """
    Removes ANSI escape characters and formats the output.

    Args:
        output (str): Raw SSH command output.

    Returns:
        str: Cleaned and formatted output.
    """
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)
    output = output.replace('\r\n', '\n').replace('\r', '\n')
    output = re.sub(r'\n+', '\n', output)
    return output.strip()

# Asynchronous function to execute SSH commands
async def execute_ssh(ip_address, commands, username, password, connection_pool):
    try:
        connection_start_time = time.time()
        conn = await connection_pool.get_connection(ip_address, username, password)
        connection_end_time = time.time()
        connection_time = connection_end_time - connection_start_time

        # Process the commands
        commands_list = [cmd.strip() for cmd in commands.strip().split('\n') if cmd.strip()]
        commands_combined = '\n'.join(commands_list)

        run_start_time = time.time()
        result = await conn.run(commands_combined, check=False)
        run_end_time = time.time()
        run_time = run_end_time - run_start_time

        # Capture stdout and stderr
        output = result.stdout + result.stderr
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

# Asynchronous function to configure a device
async def configure_device(ip, commands, username, password, responses, key, connection_pool):
    device_start_time = time.time()
    response = await execute_ssh(ip, commands, username, password, connection_pool)
    device_end_time = time.time()
    response['device_execution_time_seconds'] = round(device_end_time - device_start_time, 2)
    responses[key] = response
