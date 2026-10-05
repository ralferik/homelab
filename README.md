# homelab

Configuration and notes for my home server. It runs Proxmox VE on a small HP
desktop and hosts DNS, smart home and monitoring services for my home network.

I manage it the way I would manage a server at work: changes go through Git,
setup is automated with Ansible where possible, and each stage is written up
in `docs/`.

## Architecture

```mermaid
flowchart LR
    subgraph LAN["LAN 192.168.1.0/24"]
        router["Router<br/>192.168.1.1"]
        ws["Workstation"]
        subgraph pve["Proxmox VE (pve.home.arpa, 192.168.1.10)"]
            subgraph docker["docker01, 192.168.1.20"]
                traefik["Traefik :80"]
                adguard["AdGuard Home :53"]
            end
            ha["Home Assistant VM"]
        end
    end
    ws -- "SSH, HTTPS :8006" --> pve
    ws -- "*.home.arpa" --> traefik
    traefik -- "web UI" --> adguard
    ws -- "DNS :53" --> adguard
    router --- pve
    dongle["Zigbee USB dongle"] -. passthrough .-> ha
```

The Home Assistant VM is not built yet.

## Hardware

| Component | Model |
|-----------|-------|
| Host | HP EliteDesk 705 G4 35W |
| CPU | AMD PRO A10-9700E (4 cores) |
| RAM | 16 GB |
| Storage | Samsung 512 GB NVMe SSD |
| Network | 1 GbE |
| Zigbee | SONOFF Dongle Lite MG21 |

## Status

| Area | Tooling | State |
|------|---------|-------|
| Hypervisor | Proxmox VE 9 | done |
| Remote access | OpenSSH, key-only | done |
| Configuration management | Ansible | in progress |
| Containers | Docker Engine, Compose | done |
| DNS and ad blocking | AdGuard Home | done |
| Reverse proxy | Traefik | in progress (HTTP only) |
| Monitoring | Prometheus, Node Exporter, Grafana | not started |
| Smart home | Home Assistant, Zigbee | not started |

## Layout

```
docs/      build notes, one file per stage
ansible/   inventory and playbooks
compose/   Docker Compose stacks
```

## Docs

1. [Proxmox host: install, updates, SSH](docs/01-proxmox-host.md)
2. [VM template, Docker host and Ansible](docs/02-vms-and-ansible.md)
3. [DNS and reverse proxy](docs/03-dns-and-reverse-proxy.md)

## Decisions

**Proxmox instead of Ubuntu on bare metal.** VMs can be snapshotted before
risky changes and rebuilt from scratch, and the Zigbee dongle can be passed
through to the one VM that needs it.

**ext4 with LVM-thin instead of ZFS.** There is only one disk, so ZFS would not
add redundancy, and its ARC cache would take memory the VMs need.

**`home.arpa` as the local domain.** RFC 8375 reserves it for home networks.
`.local` is used by mDNS and causes name resolution conflicts.

**Traefik instead of Nginx Proxy Manager.** Routes are Docker labels in the
compose files, so they are in Git and deployed by Ansible. Nginx Proxy Manager
keeps its configuration in a database that is edited through a web interface.

**IPv6 turned off on the LAN.** The ISP router advertises itself as the IPv6
DNS server and cannot be told otherwise, so clients bypassed AdGuard. With a
public IPv4 address and nothing exposed to the internet, IPv6 was not adding
anything.

**SSH settings in a drop-in file.** `/etc/ssh/sshd_config.d/10-hardening.conf`
is not overwritten by package upgrades and is easy to manage with Ansible.

## Security

- SSH accepts public keys only. Root can log in with a key but not a password.
- Secrets are kept out of the repository (Ansible Vault or ignored `.env` files).
- Only private LAN addresses are published here.

## License

MIT
