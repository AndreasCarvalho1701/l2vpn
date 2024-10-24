# ssh_pool.py
import threading
import paramiko

class SSHConnectionPool:
    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()

    def get_connection(self, ip, username, password):
        key = (ip, username)
        with self.lock:
            if key not in self.connections:
                # Estabeleça uma nova conexão SSH
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client.connect(ip, username=username, password=password)
                self.connections[key] = ssh_client
            return self.connections[key]
