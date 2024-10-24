import asyncio
import asyncssh
from collections import defaultdict

# Class to manage SSH connections with per-IP locks
class SSHConnectionPool:
    def __init__(self):
        self.connections = {}
        self.locks = defaultdict(lambda: asyncio.Lock())  # Per-IP locks

    async def get_connection(self, ip_address, username, password):
        async with self.locks[ip_address]:
            if ip_address in self.connections:
                return self.connections[ip_address]
            else:
                conn = await asyncssh.connect(
                    ip_address,
                    username=username,
                    password=password,
                    known_hosts=None
                )
                self.connections[ip_address] = conn
                return conn
