import re
import sys

log = open(sys.argv[1])

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

desc = {k: v for k, v in sorted(attempts.items(), key=lambda item: item[1], reverse=True)}
for k, v in desc.items():
    print(k, v)
