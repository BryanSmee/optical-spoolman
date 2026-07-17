# Optical Spoolman

Take a photo of a 3D-printer filament package, let a vision model read the
details off it, review/edit the result, and create the matching **filament** and
**spool** in your [Spoolman](https://github.com/Donkie/Spoolman) instance.

```
 phone/browser ──photo──▶ FastAPI backend ──▶ Claude vision (extract)
                                  │
                                  └──▶ Spoolman REST API (create filament + spool)
```

## How it works

1. **Frontend** (`static/index.html`) — a single page that opens the camera,
   uploads the photo, shows the extracted fields in an editable form, and posts
   the confirmed values back.
2. **Backend** (`app/`) — FastAPI:
   - `POST /api/analyze` — sends the image to Claude (`messages.parse` with a
     structured schema) and returns the extracted fields, pre-filled with
     sensible defaults (e.g. density inferred from material, diameter → 1.75).
   - `POST /api/create` — finds-or-creates the vendor, then creates the filament
     and one full spool via the Spoolman REST API.
   - `GET /api/health` — reports whether the API key is set and Spoolman is
     reachable.

The review step means the model's guesses never go straight into Spoolman — you
confirm or fix every field first.

## Setup

Requires Python 3.10+ and a running Spoolman instance.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and SPOOLMAN_URL
```

`.env` keys:

| Variable            | Default                   | Notes                                  |
| ------------------- | ------------------------- | -------------------------------------- |
| `ANTHROPIC_API_KEY` | —                         | Required. https://console.anthropic.com |
| `ANTHROPIC_MODEL`   | `claude-opus-4-8`         | Vision model used for extraction.      |
| `SPOOLMAN_URL`      | `http://localhost:7912`   | Base URL of your Spoolman instance.    |

## Run (local Python)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. On a phone, the **Take / choose photo** button
opens the camera directly.

## Run (Docker)

A `Dockerfile` and `docker-compose.yml` are included. Create a `.env` first
(`cp .env.example .env`, set `ANTHROPIC_API_KEY`).

**Against your existing Spoolman** — set `SPOOLMAN_URL` in `.env` to a reachable
address (use `http://host.docker.internal:7912` for a Spoolman running on the
Docker host), then:

```bash
docker compose up --build
```

**With a bundled Spoolman** (starts Spoolman alongside the app):

```bash
docker compose --profile with-spoolman up --build
```

In bundled mode the backend reaches Spoolman at `http://spoolman:8000` (the
default), while clickable spool links use `SPOOLMAN_PUBLIC_URL`
(`http://localhost:7912` by default) so they open in your browser. Spoolman data
persists in the `spoolman_data` volume.

The app listens on <http://localhost:8000>.

### Pull the prebuilt image

CI publishes the image to GitHub Container Registry on every push to `main` and
on version tags (`v*`):

```bash
docker pull ghcr.io/bryansmee/optical-spoolman:latest
```

`docker-compose.yml` already references this image, so `docker compose pull`
fetches it instead of building locally.

> Camera access in browsers requires a secure context. `localhost` is treated as
> secure; to use it from another device, serve over HTTPS (e.g. behind a reverse
> proxy) or use a tunneling tool.

## NFC tags (OpenSpool)

After a spool is created, the app offers to write an **NFC tag** in
[OpenSpool](https://github.com/spuder/OpenSpool) format (the same shape
SpoolPainter / OpenSpoolMan write), so a printer or reader can identify the
filament. The tag is an NDEF `application/json` record:

```json
{
  "protocol": "openspool",
  "version": "1.0",
  "type": "PLA",
  "color_hex": "9C6B32",
  "brand": "FlashForge",
  "min_temp": "220",
  "max_temp": "240",
  "bed_min_temp": "25",
  "bed_max_temp": "60",
  "spool_id": "29",
  "subtype": "HS"
}
```

- Field names, ordering and string typing match real SpoolPainter tag dumps:
  every temperature **and** `spool_id` is a string, and the product line is
  written as `subtype`.
- `spool_id` links the tag back to the Spoolman spool. `subtype` and the `bed_*`
  fields are additive — OpenSpool readers ignore keys they don't recognise.
- Writing uses the browser **Web NFC API**, which works only on **Chrome/Edge on
  Android** and only in a **secure context (HTTPS)**. Serve the app over your
  Tailscale HTTPS URL (or another cert) and open it in Android Chrome.
- iOS browsers and desktop browsers cannot write NFC tags — the app shows the
  payload but hides the write button there.
- Use a blank **NTAG213/215/216** tag. Each button press is one write attempt;
  if it fails (tag not detected, moved too soon), just tap **Retry** and hold the
  tag steady against the back of the phone.

## Notes & limits

- **Density / diameter** are required by Spoolman. If the package doesn't print
  them, the backend infers density from the material (see
  `DENSITY_BY_MATERIAL` in `app/spoolman.py`) and defaults diameter to 1.75 mm.
  Both are editable before you submit.
- **Color** is the model's best estimate from the printed color name and the
  visible spool color; double-check it.
- A brand-new spool is created **full** (`remaining_weight` = net weight).
- No Spoolman authentication is handled — point `SPOOLMAN_URL` at an instance
  the backend can reach directly (Spoolman has no auth by default).
