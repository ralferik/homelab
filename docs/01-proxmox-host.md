# 01 Proxmox host

Installing Proxmox VE 9 on the HP EliteDesk 705 G4, switching to the
no-subscription repository and locking SSH down to key authentication.

## Firmware

BIOS version Q27 02.25.00. Changed in Computer Setup (F10):

| Setting | Value | Why |
|---------|-------|-----|
| SVM CPU Virtualization | Enabled | needed for KVM |
| USB Storage Boot | Enabled | boot the installer |
| After Power Loss | Power On | start again after a power cut |

There is no separate IOMMU option on this board. USB passthrough does not need
it.

## Installer USB

Checked the ISO against the published SHA256 sum:

```powershell
Get-FileHash .\proxmox-ve_9*.iso -Algorithm SHA256
```

Wrote it with Rufus in DD mode. The Proxmox ISO is a hybrid image and ISO mode
can leave it unbootable.

## Install

| Option | Value |
|--------|-------|
| Disk | 512 GB NVMe, ext4 |
| Hostname | pve.home.arpa |
| Address | 192.168.1.10/24 |
| Gateway, DNS | 192.168.1.1 |
| Time zone | Europe/Tallinn |

The web interface is at `https://192.168.1.10:8006`.

## Package repositories

The enterprise repositories are enabled by default and return
`401 Unauthorized` without a subscription, which makes `apt-get update` fail.

Under Updates > Repositories I disabled `pve-enterprise` and the Ceph
enterprise repository, added `pve-no-subscription`, then refreshed and
upgraded.

```console
root@pve:~# pveversion
pve-manager/9.2.21/4f6e0ac86f9e8c7f (running kernel: 7.0.14-20-pve)
```

## Subscription popup

Without a subscription the web interface shows a "No valid subscription"
dialog at every login. There is no setting for it. The dialog comes from
one call in `proxmoxlib.js`, and a `sed` replaces that call with a no-op.

Any upgrade of `proxmox-widget-toolkit` restores the original file, so the
change is a script that apt runs after every dpkg run:

```
# /etc/apt/apt.conf.d/99-pve-no-nag
DPkg::Post-Invoke { "/usr/local/sbin/pve-no-nag.sh"; };
```

The script exits early if the file is already patched, so it only restarts
`pveproxy` when something changed. Both files are installed by
`ansible/playbooks/proxmox.yml`.

Tested by reinstalling the package, which put back the original file:

```console
root@pve:~# apt install --reinstall -y proxmox-widget-toolkit
...
Setting up proxmox-widget-toolkit (5.2.10) ...
patched
```

## SSH keys

On the Windows workstation:

```powershell
ssh-keygen -t ed25519 -C "ralf@windows-homelab"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@192.168.1.10 "cat >> /root/.ssh/authorized_keys"
```

## Disabling password login

With the Proxmox web shell open as a fallback:

```bash
cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
sshd -t && systemctl reload ssh
```

Root needs to keep key-based SSH because Proxmox uses it internally, so
`PermitRootLogin no` is not an option here.

Checked the effective config and tried a password login:

```console
root@pve:~# sshd -T | grep -Ei 'passwordauthentication|permitrootlogin'
permitrootlogin without-password
passwordauthentication no
```

```console
PS> ssh -o PubkeyAuthentication=no root@192.168.1.10
root@192.168.1.10: Permission denied (publickey).
```

The first attempt did not take effect because the file had not been created.
`sshd -T` showed password authentication still on, which made the cause
obvious.

## Client setup

The Windows `ssh-agent` service is set to start automatically and the key is
loaded with `ssh-add`. `~/.ssh/config` has a host alias:

```
Host pve
    HostName 192.168.1.10
    User root
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```
