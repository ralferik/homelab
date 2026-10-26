# 08 Backups

All guests live on the single internal NVMe drive of the Proxmox host. The
configuration is in this repository, but the state is not: Home Assistant
history, the Zigbee network database, Grafana data and the Tailscale node
identity. If that drive fails, this state is gone. Every night Proxmox backs up
all guests to a second drive, a USB NVMe disk attached to the host.

## Layout

| Component | Value |
|-----------|-------|
| Disk | Samsung PM981a 512 GB NVMe in a Realtek RTL9210B USB enclosure |
| File system | ext4, label `pve-backup`, mounted at `/mnt/pve-backup` |
| Proxmox storage | `usb-backup`, type Directory, content `backup` only |
| Backup job | `daily-usb`, every day at 03:00, all guests, snapshot mode, zstd |
| Retention | 7 daily, 4 weekly, 3 monthly per guest |
| Automation | [`ansible/playbooks/pve-backup.yml`](../ansible/playbooks/pve-backup.yml) |

## Hardware notes

The PM981a is a PCIe NVMe drive, so the enclosure has to support NVMe. Many
cheap M.2 enclosures only take SATA M.2 drives. The RTL9210B bridge supports
both.

The enclosure draws close to 900 mA, the full budget of a USB 3 port. It must
be plugged directly into a USB 3 (SuperSpeed) port on the host. Through a short
passive extender it did not show up at all: no device in `lsusb` and nothing in
the kernel log. Connected directly, the kernel uses the `uas` driver at
SuperSpeed.

Before using a second-hand drive, check its health. The `-d sntrealtek` option
lets `smartctl` reach the NVMe drive behind the USB bridge:

```bash
smartctl -H -A -d sntrealtek /dev/sda
```

The values to look at are `Percentage Used`, `Available Spare` and
`Media and Data Integrity Errors`.

## Preparing the disk

These steps are done once by hand. They erase the disk, so the disk is
addressed by its stable `/dev/disk/by-id` path, never by `/dev/sdX`, which can
change between boots.

```bash
DISK=/dev/disk/by-id/usb-Realtek_RTL9210B_NVME_<serial>-0:0

sgdisk --zap-all "$DISK"
sgdisk -n 1:0:0 -t 1:8300 -c 1:pve-backup "$DISK"
udevadm settle
wipefs -a "${DISK}-part1"
mkfs.ext4 -L pve-backup -m 0 "${DISK}-part1"
```

`sgdisk --zap-all` only removes the partition tables. The new partition started
at the same sector as an old EFI partition, and ext4 does not overwrite the
first 1024 bytes of a partition, so the old FAT boot sector survived and
`blkid` reported the partition as vfat. `wipefs -a` before `mkfs` removes such
leftover signatures. `wipefs -n` lists the signatures without changing
anything and should show only ext4.

`-m 0` drops the 5% of blocks that ext4 reserves for root by default. That
reserve protects system partitions and is wasted on a data disk.

ext4 was chosen over ZFS. A single USB disk gives ZFS no redundancy to work
with, and a pool on USB is suspended when the connection drops and has to be
recovered by hand. ext4 is simple and any Linux system can read it.

## Mount

```
UUID=<fs-uuid> /mnt/pve-backup ext4 defaults,noatime,nofail,x-systemd.device-timeout=10s 0 2
```

- `nofail` lets the host boot normally when the disk is not attached. Without
  it, systemd stops in emergency mode.
- `x-systemd.device-timeout=10s` waits 10 seconds for the disk, not the
  default 90.
- The empty mountpoint directory has the immutable flag (`chattr +i`). When the
  disk is not mounted, nothing can write into it, so a backup cannot fill the
  root file system by mistake.

## Proxmox storage and job

```bash
pvesm add dir usb-backup --path /mnt/pve-backup --content backup \
  --is_mountpoint yes \
  --prune-backups keep-daily=7,keep-weekly=4,keep-monthly=3

pvesh create /cluster/backup --id daily-usb --schedule "03:00" \
  --storage usb-backup --all 1 --mode snapshot --compress zstd \
  --notes-template "{{guestname}}" --enabled 1
```

- `--is_mountpoint yes` makes Proxmox check that the path is a mount point.
  If the disk is missing, the storage goes offline and the job fails instead
  of writing to the root disk. Together with the immutable mountpoint that is
  two layers of protection.
- `--all 1` includes guests created later, so a new VM cannot be forgotten.
- Snapshot mode keeps the guests running. QEMU copies the disk while the VM
  runs and saves the old content of a block before the guest overwrites it, so
  the backup is consistent.
- The job has no retention of its own and falls back to the storage's
  `prune-backups` setting.

The playbook does the same: it mounts the disk and creates the storage and the
job if they do not exist yet. It does not change an existing storage or job.

```bash
ansible-playbook playbooks/pve-backup.yml --check --diff
ansible-playbook playbooks/pve-backup.yml
```

## First run

The first run, started with Run now in Datacenter → Backup, took about six
minutes for four guests and produced 8.8 GB of archives. The A10 CPU runs at
full load during compression, so the fan is audible for those minutes at 03:00.

## Restore test

A backup counts only after a restore has been tested. The test restores the
smallest guest under a new ID and does not start it, because a running copy
would conflict with the original on IP address and Tailscale node identity:

```bash
pct restore 9110 /mnt/pve-backup/dump/vzdump-lxc-110-<timestamp>.tar.zst \
  --storage local-lvm --unique 1
pct mount 9110
cat /var/lib/lxc/9110/rootfs/etc/hostname
ls /var/lib/lxc/9110/rootfs/var/lib/tailscale/
pct unmount 9110
pct destroy 9110 --purge
```

`--unique 1` gives the copy a new MAC address. The archive extracted at about
250 MiB/s, and the hostname and `tailscaled.state` were intact.

## Limits and next steps

- The USB disk is in the same room as the server. A fire or theft takes both,
  so an offsite copy is still missing (3-2-1 rule: three copies, two media,
  one offsite).
- vzdump reads every disk in full on each run. Proxmox Backup Server would
  only read blocks changed since the last backup and deduplicate the archives.
  It is a candidate for the NAS stage.
- Snapshots are not backups. A Proxmox snapshot lives on the same disk as the
  guest and is useful for a quick rollback before an upgrade, not for disk
  failure.
