# ssh_pool.py
import threading
import paramiko

# ssh_pool.py - Atualizado

class SSHConnectionPool:
    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()

    def get_connection(self, ip, username, password):
        key = (ip, username)
        with self.lock:
            # Reutilize a conexão se já estiver aberta
            if key in self.connections and self.connections[key].get_transport().is_active():
                return self.connections[key]
            else:
                # Feche a conexão existente se não estiver ativa
                if key in self.connections:
                    self.connections[key].close()
                # Estabeleça uma nova conexão
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client.connect(ip, username=username, password=password)
                self.connections[key] = ssh_client
                return ssh_client

