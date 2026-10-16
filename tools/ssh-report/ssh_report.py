import re
import sys
import argparse
import os


ipv6 = r'''(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|
([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:)
{1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1
,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}
:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{
1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA
-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a
-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0
-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,
4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}
:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9
])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0
-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]
|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]
|1{0,1}[0-9]){0,1}[0-9]))'''


def count_attempts(log):
    attempts = {}
    p1 = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
    p2 = re.compile(ipv6, re.VERBOSE)

    for line in log:
        if "Connection closed by" in line and "[preauth]" in line:
            matchipv4 = p1.search(line)
            matchipv6 = p2.search(line)

            if matchipv6:
                ip = matchipv6.group()
                if ip in attempts:
                    attempts[ip] += 1
                else:
                    attempts[ip] = 1

            elif matchipv4:
                ip = matchipv4.group()
                if ip in attempts:
                    attempts[ip] += 1
                else:
                    attempts[ip] = 1

    return attempts

def format_metrics(attempts):
    lines = [
        "# HELP ssh_failed_attempts Failed SSH login attempts per IP in the last 24 hours.",
        "# TYPE ssh_failed_attempts gauge",
    ]
    for ip, count in attempts.items():
        lines.append(f'ssh_failed_attempts{{ip="{ip}"}} {count}')
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Count failed SSH login attempts per IP.")
    parser.add_argument("logfile", help="sshd log, or /dev/stdin")
    parser.add_argument("--prom", help="write Prometheus metrics to this file instead of printing")
    args = parser.parse_args()

    with open(args.logfile) as log:
        attempts = count_attempts(log)

    if args.prom:
        tmp = args.prom + ".tmp"
        with open(tmp, "w") as f:
            f.write(format_metrics(attempts))
        os.replace(tmp, args.prom)
    else:
        desc = {k: v for k, v in sorted(attempts.items(), key=lambda item: item[1], reverse=True)}
        for k, v in desc.items():
            print(k, v)

if __name__ == "__main__":
    main()