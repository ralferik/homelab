# 05 Monitoring

Prometheus collects host metrics from the Proxmox host and docker01, and
Grafana shows them on a dashboard. Both run as one Compose stack on docker01.
The dashboard and the data source are files in this repository, not settings
made in the Grafana UI.

## Layout

| Component | Where | Address |
|-----------|-------|---------|
| Node Exporter | pve and docker01, system package | `:9100` |
| Prometheus | docker01, container | `https://prometheus.home.arpa` |
| Grafana | docker01, container | `https://grafana.home.arpa` |

Home Assistant is not monitored yet. HAOS does not let me install packages on
the host, so it needs a different approach.

## Node Exporter

Node Exporter reads CPU, memory, disk and network counters from the kernel and
serves them as plain text over HTTP. It is installed from the Ubuntu and
Debian package repositories by `ansible/playbooks/node-exporter.yml`, on both
the `docker` and `proxmox` groups.

It runs as a system package and not as a container because it should see the
host as it is, and the Proxmox host does not run Docker at all.

On docker01, UFW allows port 9100 only from `172.16.0.0/12`. Prometheus runs
in a container, so its requests to the host come from a Docker network
address, not from the LAN.

```bash
curl -s http://192.168.1.10:9100/metrics | grep node_load1
```

The playbook starts the service, which fails in `--check` mode on a fresh host
because the package was never really installed. That task has
`ignore_errors: "{{ ansible_check_mode }}"` so a dry run still finishes.

## Prometheus

Prometheus pulls metrics from each target every 30 seconds and keeps them for
30 days in the `prometheus-data` volume. Targets are listed statically in
`compose/monitoring/prometheus.yml`, with an `instance` label so graphs show
`pve` and `docker01` instead of IP addresses:

```yaml
- job_name: node
  static_configs:
    - targets: ["192.168.1.10:9100"]
      labels:
        instance: pve
    - targets: ["192.168.1.20:9100"]
      labels:
        instance: docker01
```

Status > Targets in the Prometheus UI shows whether each target is up. The UI
has no login, which is acceptable here because it is only reachable from the
LAN.

## Grafana

### Admin password

The admin password is not in the compose file. The compose file reads
`${GRAFANA_ADMIN_PASSWORD}`, and `stacks.yml` copies
`~/homelab-secrets/monitoring.env` from my workstation to
`/opt/stacks/monitoring/.env` with mode 0600. Compose reads `.env` from the
stack directory automatically. `.env` files are in `.gitignore`.

### Provisioning

Everything under `compose/monitoring/grafana/provisioning/` is mounted
read-only into the container and loaded on startup:

```
provisioning/
  datasources/prometheus.yml   Prometheus as the default data source
  dashboards/homelab.yml       tells Grafana to load dashboards from this folder
  dashboards/homelab.json      the Homelab dashboard
```

The data source has a fixed `uid: prometheus`, and every panel in the
dashboard refers to it by that uid. Without a fixed uid Grafana generates one,
and a dashboard exported from one install would not find its data source on
another.

`allowUiUpdates: false` makes the dashboard read-only in the UI. Git is the
only place it changes, so a change made by hand cannot silently disappear on
the next deploy.

### Dashboard

Three panels, one question each:

| Panel | Query |
|-------|-------|
| CPU | `100 - avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100` |
| RAM | `(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100` |
| Disk | `100 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100` |

`node_cpu_seconds_total` is a counter. It only grows from boot, so graphing it
directly gives a rising line that says nothing about load. `rate()` turns it
into seconds per second over the last five minutes. Idle time per second,
averaged over the cores and subtracted from 100, is the CPU usage. Memory and
disk values are gauges, current values that go up and down, so they are used
as they are.

On pve, RAM sits around 50 percent because the memory given to the VMs counts
as used on the host.

## Problems I ran into

**Grafana 13 exports a new format.** Export as JSON produced a
`dashboard.grafana.app/v2` resource. File provisioning expects the classic
dashboard JSON, so the file in the repository is written in the classic
format.

**Changing the data source uid broke startup.** The data source was first
provisioned without a uid. After I added `uid: prometheus`, Grafana looked up
the existing data source by the new uid, did not find it, and the container
restarted in a loop with `Datasource provisioning error: data source not
found`. Traefik answered 404 because the container was not running. The fix
was a one-time `deleteDatasources` entry for `Prometheus` in the same file, so
Grafana removed the old one and created it again with the new uid. I removed
the entry after one successful start. The lesson is to set the uid from the
start.

## Still to do

- Alerts for disk usage and targets that are down
- Pin image versions instead of `latest`
- Monitor the Home Assistant VM
- Export failed SSH login counts as a metric (see the log analyzer project)
