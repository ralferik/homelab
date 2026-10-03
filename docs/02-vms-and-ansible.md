# 02 VM template, Docker host and Ansible

Building an Ubuntu 24.04 cloud-init template on Proxmox, cloning the first VM
from it and managing that VM with Ansible from WSL.

## Cloud-init template

Ubuntu publishes cloud images that boot without an installer. Proxmox can
attach a small cloud-init drive that sets the user, SSH key and network on
first boot.

```bash
cd /root
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
qm create 9000 --name ubuntu-2404-template --memory 2048 --cores 2 --cpu host \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --ostype l26 \
  --agent enabled=1 --serial0 socket --vga serial0
qm set 9000 --scsi0 local-lvm:0,import-from=/root/noble-server-cloudimg-amd64.img
qm set 9000 --ide2 local-lvm:cloudinit --boot order=scsi0
qm template 9000
```

The serial console settings are needed because the cloud image writes its
console output to the serial port.

## docker01

| Setting | Value |
|---------|-------|
| VM ID | 101 |
| CPU, RAM | 2 cores, 4 GB |
| Disk | 32 GB |
| Address | 192.168.1.20/24 |
| User | ralf (key only, passwordless sudo) |

```bash
grep windows-homelab /root/.ssh/authorized_keys > /root/ralf-windows.pub
qm clone 9000 101 --name docker01 --full
qm set 101 --memory 4096 --cores 2 --onboot 1 \
  --ciuser ralf --sshkeys /root/ralf-windows.pub \
  --ipconfig0 ip=192.168.1.20/24,gw=192.168.1.1 \
  --nameserver 192.168.1.1 --searchdomain home.arpa
qm resize 101 scsi0 +28G
qm start 101
```

I used a full clone so the VM does not depend on the template disk. The
`grep` keeps the Proxmox host's own root key out of the VM.

## Ansible control node

Ansible runs in WSL (Ubuntu 24.04), installed with pipx:

```bash
sudo apt install -y pipx
pipx install --include-deps ansible
```

The repository is cloned inside the WSL filesystem (`~/code/homelab`), not
under `/mnt/c`. Windows drives show up as world-writable in WSL and Ansible
ignores `ansible.cfg` in a world-writable directory.

WSL has its own SSH key. Because the VM has no password login, the key was
installed through the Windows `ssh.exe`, which already had access:

```bash
cat ~/.ssh/id_ed25519.pub | ssh.exe ralf@192.168.1.20 "cat >> ~/.ssh/authorized_keys"
```

## Inventory

`ansible/inventory/hosts.yml` has two groups: `proxmox` (the host, as root)
and `docker` (docker01, as ralf).

```console
$ ansible all -m ping
pve | SUCCESS
docker01 | SUCCESS
```

## Baseline playbook

`ansible/playbooks/baseline.yml` upgrades packages, installs the QEMU guest
agent, unattended-upgrades and a few tools, sets the time zone, enables UFW
with SSH allowed from the LAN only, and reboots if an upgrade asks for it.

The first `--check` run failed on starting `qemu-guest-agent`, because in check
mode the package is never actually installed. That task now has
`ignore_errors: "{{ ansible_check_mode }}"`.

A second real run reports `changed=0`.

UFW is only used inside the VM. The Proxmox host has its own firewall, and
running UFW next to it would cause conflicts.

## Docker

`ansible/playbooks/docker.yml` adds Docker's apt repository, installs Docker
Engine with the Compose plugin and adds `ralf` to the `docker` group.

Two things to keep in mind:

- Membership in the `docker` group is effectively root access.
- Ports published by containers bypass UFW, because Docker inserts its own
  iptables rules ahead of UFW's. Services will sit behind a reverse proxy
  instead of publishing their own ports.
