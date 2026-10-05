# 03 DNS and reverse proxy

AdGuard Home as the DNS server for the whole LAN and Traefik as the reverse
proxy for web interfaces, both running as Docker Compose stacks on docker01.

## Layout

| Name | Address | What answers |
|------|---------|--------------|
| `*.home.arpa` | 192.168.1.20 | Traefik, which routes by host name |
| `pve.home.arpa` | 192.168.1.10 | Proxmox web interface |
| DNS | 192.168.1.20:53 | AdGuard Home |

Three ports are published on docker01: 53 for DNS, and 80 and 443 for
Traefik. Port 80 only redirects to HTTPS. The
AdGuard web interface listens on port 3000 inside the Docker network and is
only reachable through Traefik.

## Freeing port 53

Ubuntu runs the `systemd-resolved` stub listener on `127.0.0.53:53`, which
blocks anything else from binding port 53.
`ansible/playbooks/dns-prep.yml` disables it with a drop-in file and points
`/etc/resolv.conf` at the real upstream servers, so the VM can still resolve
names:

```ini
# /etc/systemd/resolved.conf.d/10-no-stub.conf
[Resolve]
DNSStubListener=no
```

The service is restarted from a handler, so a second run reports
`changed=0`.

## Deploying stacks

Each stack lives in `compose/<name>/compose.yml`.
`ansible/playbooks/stacks.yml` copies them to `/opt/stacks/<name>` on docker01
and starts them with `community.docker.docker_compose_v2`.

```bash
cd ansible
ansible-playbook playbooks/stacks.yml
```

Data that the containers write (AdGuard's `conf/` and `work/`) stays on the
server. It contains the admin password hash and query logs, so it does not
belong in a public repository.

## Traefik

Traefik reads container labels through the Docker socket (mounted read-only)
and builds its routes from them. `exposedbydefault=false` means only
containers with `traefik.enable=true` get a route.

The Traefik stack creates a Docker network called `proxy`. Other stacks join
it as an external network, so Traefik reaches them internally and they do not
need to publish ports. This also keeps them out of the UFW problem described
in [02](02-vms-and-ansible.md): Docker's published ports bypass UFW, so the
fewer of them the better.

A route for a new service is three labels:

```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.adguard.rule=Host(`adguard.home.arpa`)
  - traefik.http.services.adguard.loadbalancer.server.port=3000
```

Before DNS was in place, routes were tested with a `Host` header:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: traefik.home.arpa" http://192.168.1.20/dashboard/
```

## HTTPS with a local CA

Let's Encrypt cannot issue certificates for `home.arpa`, so I run my own CA
with `mkcert`. The CA and the certificate are created on the control node and
kept outside the repository:

```bash
mkcert -install
mkdir -p ~/homelab-secrets/tls && chmod 700 ~/homelab-secrets
cd ~/homelab-secrets/tls
mkcert -cert-file home.arpa.crt -key-file home.arpa.key \
  traefik.home.arpa adguard.home.arpa grafana.home.arpa prometheus.home.arpa ha.home.arpa
```

The certificate lists each name instead of using `*.home.arpa`. A new service
means adding its name and running `mkcert` again. The certificate expires on
5 January 2029.

`stacks.yml` copies the certificate and key to `/opt/stacks/traefik/certs`
(directory `0700`, key `0600`). The copy task has `diff: false` so that
`--diff` never prints the key.

Traefik loads it as the default certificate from a file provider:

```yaml
# compose/traefik/dynamic/tls.yml
tls:
  stores:
    default:
      defaultCertificate:
        certFile: /certs/home.arpa.crt
        keyFile: /certs/home.arpa.key
```

The `web` entrypoint redirects everything to `websecure`, and `websecure` has
TLS enabled, so routers only need `entrypoints=websecure`. TLS ends at
Traefik. Traffic to the containers stays plain HTTP inside the Docker network.

The root certificate is trusted on Windows with:

```powershell
certutil -addstore -f ROOT homelab-rootCA.crt
```

On iOS the profile has to be installed and then trusted separately under
General > About > Certificate Trust Settings. I have not done this on the
phone yet.

`rootCA-key.pem` (in `mkcert -CAROOT`) can sign a certificate for any name
that my devices would accept, so it is kept off the server and backed up
offline.

## AdGuard Home

In the setup wizard the admin interface is set to port 3000 to match the
Traefik label. The wizard suggests port 80 by default.

Local names are DNS rewrites, set under Filters > DNS rewrites:

| Domain | Answer |
|--------|--------|
| `*.home.arpa` | 192.168.1.20 |
| `pve.home.arpa` | 192.168.1.10 |

The exact entry for `pve` takes priority over the wildcard. With the
wildcard in place, a new service only needs Traefik labels and no DNS change.

The rewrites are stored in `conf/AdGuardHome.yaml` on the server, not in this
repository.

Checked with:

```console
$ nslookup traefik.home.arpa 192.168.1.20
Name:   traefik.home.arpa
Address: 192.168.1.20

$ nslookup doubleclick.net 192.168.1.20
Name:   doubleclick.net
Address: 0.0.0.0
```

### Resetting the admin password

AdGuard stores a bcrypt hash. To set a new password, generate a hash, stop
the container (AdGuard rewrites its config on shutdown), replace the
`password` value under `users` and start it again:

```bash
htpasswd -B -C 10 -n admin
cd /opt/stacks/adguard
docker compose stop
sudo nano conf/AdGuardHome.yaml
docker compose start
```

## Rolling it out to the LAN

I tested with one machine first by setting its DNS manually to
192.168.1.20. Once that worked, I changed the DNS server handed out by the
router's DHCP server to 192.168.1.20, with no secondary server. A secondary
pointing at the router would let clients skip AdGuard at random.

The static addresses .10 and .20 are below the DHCP range (.64 to .243), so
the router never hands them out.

### IPv6

Windows used AdGuard straight away, but the iPhone did not show up in the
query log. Its DNS list had 192.168.1.20 and an IPv6 address: the router
advertises itself as an IPv6 DNS server, and the router firmware has no option
to change that.

I turned IPv6 off on the router. The connection has a public IPv4 address and
nothing is exposed to the internet, so IPv6 was not giving me anything here.
After that, the phone's queries appeared in the log.

### Failure mode

All DNS on the LAN now depends on docker01. The VM starts on boot and the
containers use `restart: unless-stopped`. If docker01 is down for longer,
setting the router's DNS back to automatic restores name resolution.

## Still to do

- Trust the CA on the phone
- Manage the DNS rewrites from the repository
- Back up `/opt/stacks/*/conf`
