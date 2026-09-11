import socket
import json

def run(ip, ports):
    """
    Scanne une liste de ports TCP sur une IP cible (timeout 1s par port).
    
    Args:
        ip (str): Adresse IP cible.
        ports (list | str): Liste des ports (ou chaîne séparée par virgules).
    
    Returns:
        str: JSON contenant le statut, la cible, les ports ouverts et les erreurs.
    """
    open_ports = []
    errors = []

    # Normalisation : accepte une liste ou une chaîne "80, 443, 8080"
    if isinstance(ports, str):
        ports = [p.strip() for p in ports.split(",") if p.strip().isdigit()]

    for port in ports:
        try:
            port = int(port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
        except socket.gaierror:
            errors.append(f"IP invalide ou introuvable : {ip}")
            break
        except (ValueError, OSError) as e:
            errors.append(f"Erreur sur le port {port} : {e}")

    return json.dumps({
        "status": "success" if not errors else "partial_error",
        "target": ip,
        "open_ports": open_ports,
        "errors": errors
    }, ensure_ascii=False)