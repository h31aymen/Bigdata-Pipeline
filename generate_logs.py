import socket
import time
import random


SYSLOG_SERVER = "127.0.0.1"
SYSLOG_PORT = 514


devices = ["switch-1", "switch-2", "switch-3", "router-1", "router-2"]


log_levels = ["INFO", "WARNING", "ERROR", "CRITICAL"]
log_probabilities = [0.88, 0.06, 0.02, 0.04]  # Plus de logs INFO et WARNING

def send_syslog_message(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP socket
    sock.sendto(message.encode(), (SYSLOG_SERVER, SYSLOG_PORT))
    sock.close()

while True:
    device = random.choice(devices)
    level = random.choices(log_levels, weights=log_probabilities, k=1)[0] 
    message = f"{device} - {level} - Port {random.randint(1, 48)}: Link {random.choice(['up', 'down'])}"

    send_syslog_message(message)
    print(f"Sent log: {message}")  

    time.sleep(random.uniform(0.5, 2))