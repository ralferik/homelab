# 04 Home Assistant and Zigbee

Home Assistant OS in its own VM on Proxmox, with the Zigbee dongle passed
through to it. The lights run on Zigbee through Zigbee2MQTT and show up in
Apple Home through the HomeKit Bridge integration.

## Layout

| Setting | Value |
|---------|-------|
| VM ID | 102 |
| Name | ha |
| OS | Home Assistant OS |
| CPU, RAM | 2 cores, 4 GB |
| Disk | 32 GB |
| Address | 192.168.1.30/24 |
| DNS | 192.168.1.20, then 192.168.1.1 |
| USB | SONOFF Dongle Lite MG21 (`10c4:ea60`) |

| Component | Version or setting |
|-----------|--------------------|
| Dongle firmware | EmberZNet 9.1.1 (Zigbee NCP), 115200 baud |
| Zigbee2MQTT | 2.14.2, adapter `ember` |
| MQTT broker | Mosquitto add-on |
| Zigbee channel | 11 |

## Creating the VM

HAOS is published as a ready disk image, so there is no installer. The image
is imported the same way as the Ubuntu cloud image in
[02](02-vms-and-ansible.md):

```bash
cd /root
URL=$(curl -s https://api.github.com/repos/home-assistant/operating-system/releases/latest \
  | grep -o 'https://[^"]*haos_ova-[^"]*\.qcow2\.xz')
wget -O haos.qcow2.xz "$URL"
unxz -f haos.qcow2.xz

qm create 102 --name ha --memory 4096 --cores 2 --cpu host \
  --machine q35 --bios ovmf \
  --efidisk0 local-lvm:0,efitype=4m,pre-enrolled-keys=0 \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci \
  --ostype l26 --agent enabled=1 --onboot 1
qm set 102 --scsi0 local-lvm:0,import-from=/root/haos.qcow2
qm set 102 --boot order=scsi0
qm resize 102 scsi0 32G
qm set 102 --usb0 host=10c4:ea60
qm start 102
```

HAOS needs UEFI, but its kernel is not signed with Microsoft's keys, so the
EFI disk is created without pre-enrolled keys and Secure Boot stays off.

The dongle is passed through by vendor and product ID, not by port. It can be
moved to another USB port and still ends up in the VM. It sits on a short USB
2.0 extension cable, away from the server's USB 3 ports, which cause
interference on 2.4 GHz.

The VM is created by hand. The commands are kept here so it can be rebuilt
the same way.

## Static address

HAOS does not use cloud-init. The address is set from the `ha` CLI in the
Proxmox console:

```
network update enp6s18 --ipv4-method static --ipv4-address 192.168.1.30/24 \
  --ipv4-gateway 192.168.1.1 --ipv4-nameserver 192.168.1.20 --ipv4-nameserver 192.168.1.1
```

The interface is `enp6s18`, not `enp0s18`, because the q35 machine type
numbers the PCI buses differently.

Every other device on the LAN uses AdGuard only. Home Assistant has the router
as a second DNS server on purpose: the lights should keep working while
docker01 is down for an upgrade, and HA does not need any `home.arpa` names.

## Zigbee2MQTT

I chose Zigbee2MQTT over the built-in ZHA integration. It supports more
devices, and its configuration and network backup live in one place
(`/config/zigbee2mqtt`, included in HA backups).

Setup in Home Assistant:

1. Mosquitto broker add-on and the MQTT integration.
2. Zigbee2MQTT add-on from the `zigbee2mqtt/hassio-zigbee2mqtt` repository.
3. Serial port set by its stable path,
   `/dev/serial/by-id/usb-SONOFF_SONOFF_Dongle_Lite_MG21_<serial>-if00-port0`,
   with `adapter: ember`, `baudrate: 115200` and `rtscts: false`.

The network keys are generated randomly on first start and are only stored in
HA and its backups.

### Channel

The network started on channel 25 to stay away from Wi-Fi. It moved to
channel 11 before any devices joined, because KAJPLATS bulbs in Zigbee mode
were reported to only look for a network on channels 11 and 17. The router's
2.4 GHz Wi-Fi is on channel 11 (2462 MHz), which does not overlap Zigbee
channel 11 (2405 MHz).

## Lights

The lights are IKEA KAJPLATS bulbs. They ship as Matter-over-Thread devices
but also have a Zigbee mode, entered with a sequence of power cycles. After
the switch they join Zigbee2MQTT as routers and appear in Home Assistant as
normal `light` entities.

Switching takes patience: the bulb has to light up fully before each power
off, otherwise the cycle is not counted.

The VARMBLIXT lamp did not enter Zigbee mode with power cycles or Touchlink,
so it is not in use for now.

## Why not Thread

The bulbs are Matter devices, so the first attempt was Thread. I flashed the
MG21 with OpenThread RCP firmware and ran the OpenThread Border Router and
Matter Server add-ons. The bulbs paired and worked for a short time, then
became unavailable.

The OTBR log showed `radio tx timeout` and `RCP failure detected` every few
seconds once Matter traffic to the bulbs started. I ruled out the parts I
could check, one at a time:

| Suspect | Test | Result |
|---------|------|--------|
| Baud rate | RCP build at 460800 instead of 921600 | no change |
| USB power or port | extension cable, other port | no change |
| Proxmox passthrough | `dmesg` on the host | clean |
| Wi-Fi interference | router on Wi-Fi channel 11, Thread on 15 | no overlap |

The same failure with EFR32MG21 RCP firmware and IKEA Thread devices is
reported in the Nerivec/silabs-firmware-builder issue #125, without a fix. I
reflashed the dongle with Zigbee firmware and moved the bulbs to Zigbee. They
have responded instantly since.

Getting Matter back would need a different Thread radio, for example an MG24
based dongle or an Apple home hub acting as a border router.

The OTBR and Matter Server add-ons are stopped and no longer start on boot.

## Apple Home

Home Assistant stays the source of truth. The HomeKit Bridge integration
exposes selected entities to Apple Home over the LAN, so no cloud service is
involved.

There are two bridges, one for my Apple Home and one for my partner's, because
sharing a home in Apple Home needs an Apple home hub, which I do not have.
Both bridges are limited to the `light` domain in include mode. Before that,
the Zigbee2MQTT permit join switch was exposed in Apple Home as well.

Known issue: the Apple Watch shows the bulbs as "No Response" while the phone
controls them fine. Re-pairing the bridge did not help. My guess is that this
comes from having no home hub, but I have not confirmed it.

## Snapshots and backups

Before each firmware change I stopped the add-on using the dongle and took a
Proxmox snapshot of VM 102:

```bash
qm snapshot 102 pre-zigbee
qm listsnapshot 102
```

A snapshot lives on the same disk as the VM, so it only protects against bad
changes, not a failed disk. A full HA backup, downloaded off the server,
covers that case and includes the Zigbee network keys.

## Sauna

The sauna heater is a Huum UKU Local. It has a Wi-Fi radio, but the Wi-Fi
function is a paid upgrade, and until then the heater never connects to the
network. I decided not to buy it, so the sauna stays controlled from its own
panel and is not part of Home Assistant.

## Still to do

- Route `ha.home.arpa` through Traefik
- Remove the Thread and Matter add-ons and integrations
- Update Home Assistant Core
- Pair the IKEA STYRBAR remote, which is Zigbee only
