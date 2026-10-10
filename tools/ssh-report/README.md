# ssh-report

Counts failed SSH login attempts per IP address from an sshd log and prints
them with the most attempts first.

The servers here only accept keys, so sshd never logs `Failed password`.
Every failed attempt ends with one `Connection closed by ... [preauth]` line,
so that is the line the script counts.

Usage:

    python3 ssh_report.py tests/sample.log
    ssh root@192.168.1.10 'journalctl -u ssh --no-pager' | python3 ssh_report.py /dev/stdin

`tests/sample.log` has real lines from my Proxmox host plus a few made-up
attempts from documentation addresses (RFC 5737).
