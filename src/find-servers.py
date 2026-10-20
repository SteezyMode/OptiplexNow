#!/usr/bin/python3
"""List selectable Tailscale devices. Discovery never authorizes connections."""
import ipaddress
import json
import subprocess
import sys


def candidates(status):
    if status.get('BackendState') != 'Running':
        raise ValueError('Connect Tailscale on this computer, then try Find server again.')
    rows = []
    seen = set()
    peers = status.get('Peer') or {}
    nodes = [(False, x) for x in peers.values()]
    for local, node in nodes:
        if not isinstance(node, dict):
            continue
        addresses = []
        for raw in node.get('TailscaleIPs') or []:
            try:
                addresses.append(ipaddress.ip_address(raw))
            except ValueError:
                continue
        addresses.sort(key=lambda a: a.version)
        if not addresses:
            continue
        address = str(addresses[0])
        if address in seen:
            continue
        seen.add(address)
        name = node.get('HostName') or node.get('DNSName') or address
        name = ''.join(c if c.isprintable() and c not in '\t\r\n' else ' ' for c in str(name))[:120]
        state = 'Online' if node.get('Online') else 'Offline'
        rows.append((0 if node.get('Online') else 1, name.casefold(), address, f'{name} — {state} — {address}'))
    return [(address, label) for _, _, address, label in sorted(rows)[:200]]


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
