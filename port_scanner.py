import asyncio
import socket
import argparse
from datetime import datetime

async def scan_port(target_ip, port, semaphore, timeout=1.0):
    async with semaphore:
        try:
            conn = asyncio.open_connection(target_ip, port)
            reader, writer = await asyncio.wait_for(conn, timeout=timeout)
            
            banner = ""
            try:
                banner_bytes = await asyncio.wait_for(reader.read(1024), timeout=0.5)
                banner = banner_bytes.decode(errors='ignore').strip()
            except Exception:
                pass
                
            writer.close()
            await writer.wait_closed()
            return port, True, banner
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return port, False, ""

async def main():
    parser = argparse.ArgumentParser(description="Async Network Port Scanner")
    parser.add_argument("host", help="Target IP address or hostname")
    parser.add_argument("-p", "--ports", default="1-1024", help="Port range (e.g. 1-1024 or 80,443)")
    parser.add_argument("-c", "--concurrency", type=int, default=500, help="Max concurrent connections")
    parser.add_argument("-t", "--timeout", type=float, default=1.0, help="Connection timeout in seconds")
    args = parser.parse_args()

    try:
        target_ip = socket.gethostbyname(args.host)
    except socket.gaierror:
        print(f"[-] Impossible de résoudre l'hôte: {args.host}")
        return

    ports = []
    if "," in args.ports:
        ports = [int(p.strip()) for p in args.ports.split(",") if p.strip().isdigit()]
    elif "-" in args.ports:
        start, end = map(int, args.ports.split("-"))
        ports = list(range(start, end + 1))
    else:
        ports = [int(args.ports)]

    print(f"[*] Démarrage du scan sur {args.host} ({target_ip})")
    print(f"[*] Ports à scanner: {len(ports)} | Concurrence max: {args.concurrency}")
    print(f"[*] Début du scan : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    semaphore = asyncio.Semaphore(args.concurrency)
    tasks = [scan_port(target_ip, port, semaphore, args.timeout) for port in ports]

    open_ports = []
    for future in asyncio.as_completed(tasks):
        port, is_open, banner = await future
        if is_open:
            open_ports.append((port, banner))
            banner_info = f" -> {banner}" if banner else ""
            print(f"[+] Port {port:<5}/TCP : OUVERT{banner_info}")

    print(f"\n[*] Scan terminé. {len(open_ports)} port(s) ouvert(s) trouvé(s).")

if __name__ == "__main__":
    asyncio.run(main())
