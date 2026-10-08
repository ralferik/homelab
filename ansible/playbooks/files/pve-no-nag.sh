#!/bin/sh
# Hide the "No valid subscription" popup in the Proxmox web UI.
# Runs after every dpkg run, so it survives package upgrades.
f=/usr/share/javascript/proxmox-widget-toolkit/proxmoxlib.js
[ -f "$f" ] || exit 0
grep -q "void({ //" "$f" && exit 0
sed -Ezi "s/(Ext.Msg.show\(\{\s+title: gettext\('No valid sub)/void\(\{ \/\/\1/g" "$f"
systemctl restart pveproxy.service
echo patched
