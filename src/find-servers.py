#!/usr/bin/python3
"""List selectable Tailscale devices. Discovery never authorizes connections."""
import ipaddress
import json
import subprocess
import sys
import socket
from concurrent.futures import ThreadPoolExecutor


def stream_port_reachable(address):
    """A reachable standard GameStream HTTP port is a hint, not proof of a Wolf server."""
    try:
        with socket.create_connection((address, 47989), timeout=0.4):
            return True
    except OSError:
        return False


def candidates(status, probe=stream_port_reachable):
    if not isinstance(status, dict) or status.get('BackendState') != 'Running':
        raise ValueError('Connect Tailscale on this computer, then try Find server again.')
    rows = []
    seen = set()
    peers = status.get('Peer') or {}
    if not isinstance(peers, dict):
        raise ValueError('Invalid Tailscale peer listing.')
    self_node = status.get('Self') or {}
    own_addresses = set(self_node.get('TailscaleIPs') or []) if isinstance(self_node, dict) else set()
    nodes = list(peers.values())
    for node in nodes:
        if not isinstance(node, dict):
            continue
        addresses = []
        for raw in node.get('TailscaleIPs') or []:
            try:
                addresses.append(ipaddress.ip_address(raw))
            except ValueError:
                continue
        addresses.sort(key=lambda a: a.version)
        addresses = [address for address in addresses if str(address) not in own_addresses]
        if not addresses:
            continue
        address = str(addresses[0])
        if address in seen:
            continue
        seen.add(address)
        name = node.get('HostName') or node.get('DNSName') or address
        name = ''.join(c if c.isprintable() and c not in '\t\r\n' else ' ' for c in str(name))[:120]
        state = 'Online' if node.get('Online') else 'Offline'
        rows.append((bool(node.get('Online')), name, address, state))
    # Probe only a bounded number of online peers, concurrently, to avoid stalling setup.
    online = sorted((row for row in rows if row[0]), key=lambda row: row[1].casefold())[:25]
    with ThreadPoolExecutor(max_workers=10) as pool:
        hints = dict(zip((row[2] for row in online), pool.map(probe, (row[2] for row in online))))
    ordered = sorted(rows, key=lambda row: (0 if hints.get(row[2]) else 1 if row[0] else 2, row[1].casefold()))
    result = []
    for is_online, name, address, state in ordered[:200]:
        hint = ' — Game streaming port reachable' if hints.get(address) else ''
        result.append((address, f'{name} — {state}{hint} — {address}'))
    return result


def main():
    try:
        result = subprocess.run(['tailscale', 'status', '--json'], capture_output=True, text=True, timeout=4)
        if result.returncode:
            raise ValueError('Tailscale is unavailable. Check that it is running and signed in.')
        rows = candidates(json.loads(result.stdout))
        if not rows:
            raise ValueError('No other Tailscale devices found. You can still enter a server address manually.')
        for address, label in rows:
            print(address + '\t' + label)
        return 0
    except FileNotFoundError:
        print('Install and connect Tailscale first, or enter the server address manually.')
    except (ValueError, subprocess.TimeoutExpired):
        print('Could not list devices. Check Tailscale is running and signed in, or enter an address manually.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
