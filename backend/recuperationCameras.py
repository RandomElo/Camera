import socket
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed

PORT = 554
TIMEOUT = 1
THREADS = 100 


def scan_ip(ip):
    """Test si le port 554 est ouvert sur une adresse IP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((str(ip), PORT))
        s.close()
        return ip, True
    except:
        return ip, False


def recuperation(ip):
    network = ipaddress.ip_network(ip, strict=False)
    ips = list(network.hosts())

    found = []

    # Initialise un pool de threads pour exécuter des scans en parallèle
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(scan_ip, ip): ip for ip in ips}
        
        # Mise en forme des IP récupérées
        for future in as_completed(futures):
            ip, state = future.result()
            if state:
                found.append(str(ip))

    return found