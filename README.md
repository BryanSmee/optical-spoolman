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

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. On a phone, the **Take / choose photo** button
opens the camera directly.

> Camera access in browsers requires a secure context. `localhost` is treated as
> secure; to use it from another device, serve over HTTPS (e.g. behind a reverse
> proxy) or use a tunneling tool.

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
