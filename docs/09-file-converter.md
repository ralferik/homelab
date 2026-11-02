# 09 File converter

I wanted one place on the LAN to convert files between common formats:
Markdown to PDF, office documents to PDF, images between PNG, JPEG, WebP and
HEIC, and audio or video when needed. Online converters would see every file I
upload, so this runs on docker01 at `https://convert.home.arpa`.

## Choice

I use [ConvertX](https://github.com/C4illin/ConvertX). It is a web interface
over existing command line tools: pandoc, LibreOffice, ImageMagick, vips,
ffmpeg, Calibre, Inkscape and others. Conversion quality is the same as running
those tools by hand, and one container covers all the formats I need.

I also looked at Stirling-PDF. It is a PDF toolbox (merge, split, OCR, sign)
rather than a general converter. If I need those features later it can run
next to ConvertX.

The cost is image size. All those tools, including TeX Live for pandoc's PDF
output, make the image several gigabytes.

## Deployment

| Item | Value |
|------|-------|
| Stack | [`compose/convertx/compose.yml`](../compose/convertx/compose.yml) |
| Image | `ghcr.io/c4illin/convertx:v0.20.0` (pinned) |
| URL | `https://convert.home.arpa`, through Traefik |
| Data | Docker volume `convertx-data` at `/app/data` |
| Memory limit | 1 GB |
| Secret | `CONVERTX_JWT_SECRET` in `~/homelab-secrets/convertx.env` |

The container publishes no ports on the host. Traefik reaches it on the
`proxy` network, the same as Grafana and Prometheus.

The secret signs login tokens. Without it ConvertX generates a new one on every
start and all sessions are logged out. It is created once on the control node:

```bash
umask 077
echo "CONVERTX_JWT_SECRET=$(openssl rand -hex 32)" > ~/homelab-secrets/convertx.env
```

`stacks.yml` copies it to `/opt/stacks/convertx/.env` with mode `0600` and
`diff: false`. Compose reads `.env` from the project directory on its own.

The certificate needed a new name. I added `convert.home.arpa` to the `mkcert`
command in [03](03-dns-and-reverse-proxy.md), deployed with `stacks.yml` and
restarted Traefik, because Traefik reads the certificate files only at start.
DNS needed no change: AdGuard already answers for the service names.

```bash
ansible-playbook playbooks/stacks.yml
ansible docker -b -m command -a "docker restart traefik"
```

## Settings

| Variable | Value | Reason |
|----------|-------|--------|
| `ACCOUNT_REGISTRATION` | `false` | The first account is created on first visit. After that nobody can sign up. |
| `ALLOW_UNAUTHENTICATED` | `false` | Login is required. |
| `HTTP_ALLOWED` | `false` | Cookies are marked secure. All access is HTTPS through Traefik. |
| `AUTO_DELETE_EVERY_N_HOURS` | `24` | Uploaded and converted files are deleted after a day so the disk does not fill up. |

## Resources

docker01 has 4 GB of RAM and no swap. Before deploying it had 3 GB available
and 24 GB free on disk. A heavy conversion should not be able to push AdGuard
or Traefik out of memory, so the container is limited to 1 GB.

After a Markdown to PDF conversion the container used about 390 MB, so the
limit leaves room. If LibreOffice or ffmpeg jobs hit it, the container is
killed and restarts, and the other services keep running.

## Test

After deploying I converted a small Markdown file with a heading, bold text, a
list with Estonian letters and a table to PDF with pandoc. The PDF rendered
correctly, including the letters with diacritics, which is where LaTeX fonts
usually break.

## Updating

The image tag is pinned. To update, change the tag in the compose file, read
the release notes, and run `stacks.yml` from a merged branch. Old images are
removed with `docker image prune`.

## Not done

- No metrics. ConvertX has no Prometheus endpoint, and container metrics would
  need cAdvisor, which costs more memory than this service.
- Converted files are not backed up. They are temporary by design, and the
  volume is only covered by the nightly vzdump of the whole VM.
