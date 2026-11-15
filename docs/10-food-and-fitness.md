# 10 Recipes, meal plans and food tracking

I wanted to replace a paid iOS food tracker with self-hosted tools. Two
existing projects cover most of it, so I run both instead of writing my own:

| Need | Tool |
|------|------|
| Recipe collection, import from a URL | Mealie |
| Meal plans and shopping lists | Mealie |
| Food diary with calories and macros, photo recognition | SparkyFitness |
| Water, exercise and weight | SparkyFitness |

The two apps do not share data. Recipes in Mealie are not logged in
SparkyFitness automatically. I will use both for a few weeks before deciding
whether a bridge between their REST APIs is worth writing.

Both run on docker01 behind Traefik at `https://mealie.home.arpa` and
`https://fitness.home.arpa`. Like everything else they are reachable only on
the LAN and through Tailscale. On the iPhone they are added to the home
screen from Safari as web apps.

## Choice

**Mealie** is the most widely used self-hosted recipe manager. It parses
recipes from most cooking sites, scales ingredients, and builds a shopping
list from a meal plan.

**SparkyFitness** is a self-hosted alternative to MyFitnessPal. It looks up
foods in Open Food Facts and other databases, and can send a photo of a meal
to an AI provider configured in its settings to estimate calories and macros.

**docker01 instead of a new container.** The apps get HTTPS, DNS and backups
from what is already there: Traefik and the local CA, the `*.home.arpa`
wildcard in AdGuard, and the nightly vzdump of the VM. A separate LXC would
need its own Docker install, certificate and backup checks. Proxmox also
recommends VMs over LXC for Docker.

## Deployment

| Item | Mealie | SparkyFitness |
|------|--------|---------------|
| Stack | [`compose/mealie`](../compose/mealie/compose.yml) | [`compose/sparkyfitness`](../compose/sparkyfitness/compose.yml) |
| Images | `ghcr.io/mealie-recipes/mealie:v3.31.0` | `codewithcj/sparkyfitness:v1.12.1`, `codewithcj/sparkyfitness_server:v1.12.1`, `postgres:18.3-alpine` |
| Database | SQLite in the data volume | PostgreSQL 18, own container |
| Volumes | `mealie-data` | `sparkyfitness-db`, `sparkyfitness-uploads`, `sparkyfitness-backup` |
| Memory limits | 1 GB | 512 MB database, 768 MB server, 128 MB frontend |
| Secrets | none | `~/homelab-secrets/sparkyfitness.env` |

No container publishes a port on the host. Traefik reaches Mealie and the
SparkyFitness frontend on the `proxy` network. The SparkyFitness server and
database are only on the stack's own network; the frontend's nginx forwards
`/api` to the server.

Mealie uses SQLite. PostgreSQL would add fuzzy search, but for two users it is
one more container to run and upgrade for little gain.

docker01 had 4 GB of memory. With the two stacks added it was raised to 6 GB:

```bash
qm set 101 --memory 6144   # on pve, then reboot the VM
```

### Secrets

SparkyFitness needs two database passwords, an encryption key for API keys
stored in its database, and a session signing secret. They are created once on
the control node:

```bash
umask 077
cat > ~/homelab-secrets/sparkyfitness.env <<ENV
SPARKY_FITNESS_DB_PASSWORD=$(openssl rand -hex 24)
SPARKY_FITNESS_APP_DB_PASSWORD=$(openssl rand -hex 24)
SPARKY_FITNESS_API_ENCRYPTION_KEY=$(openssl rand -hex 32)
BETTER_AUTH_SECRET=$(openssl rand -base64 32)
SPARKY_FITNESS_ADMIN_EMAIL=
SPARKY_FITNESS_DISABLE_SIGNUP=false
ENV
```

`BETTER_AUTH_SECRET` must never change: it also encrypts two-factor secrets,
so a new value locks out every user with 2FA. The database password is read
only when the database is first created.

`stacks.yml` copies the file to `/opt/stacks/sparkyfitness/.env` with mode
`0600` and `diff: false`. The compose file fails early with a clear message if
a required variable is missing.

### Certificate

`mealie.home.arpa` and `fitness.home.arpa` were added to the `mkcert` command
in [03](03-dns-and-reverse-proxy.md). Then:

```bash
ansible-playbook playbooks/stacks.yml
ansible docker -b -m command -a "docker restart traefik"
```

## First start

**Mealie.** Log in with the default admin account (`changeme@example.com`,
password `MyPassword`), follow the setup wizard and change the email and
password at once. Sign-up is off, so further users are invited from the admin
page.

**SparkyFitness.** Register the first account, set its address as
`SPARKY_FITNESS_ADMIN_EMAIL`, then set `SPARKY_FITNESS_DISABLE_SIGNUP=true`
and deploy again so nobody else can register.

Photo recognition needs an AI provider. It is added per user in the
SparkyFitness settings, and the API key is stored encrypted with
`SPARKY_FITNESS_API_ENCRYPTION_KEY`. A local Ollama model would work too but
is slow without a GPU.

## iPhone

The phone must trust the local CA, or Safari shows a certificate warning and
the web app does not install cleanly:

1. Send `rootCA.pem` from `mkcert -CAROOT` to the phone (AirDrop or Files).
2. Settings, Profile Downloaded, Install.
3. Settings, General, About, Certificate Trust Settings: turn on full trust
   for the mkcert root.

Then open each site in Safari, Share, Add to Home Screen. Away from home the
phone needs Tailscale connected.

## Backups and upgrades

The volumes are inside docker01, so the nightly vzdump covers them. Before an
upgrade I also take an app-level backup, because both apps migrate their
database on start and a failed migration is easier to undo from the app's own
export than from a full VM restore:

- Mealie: Admin, Backups, Create. The archive is kept in `mealie-data`.
- SparkyFitness: the server writes backups to `sparkyfitness-backup`.

Upgrade by changing the tag in the compose file, reading the release notes,
and running `stacks.yml`. A PostgreSQL major version change needs a dump and
restore, not just a new tag.

## Not done yet

- Uptime checks for both sites in Prometheus (blackbox exporter) and an alert
  in Grafana.
- Estonian food data: Open Food Facts covers barcodes; the national Nutridata
  database needs its terms checked first.
- Shopping lists go to Estonian online shops by copy and paste. None of them
  has a public API.
