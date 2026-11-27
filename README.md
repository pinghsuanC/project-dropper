# 📮 Postie98

Send files from my phone to my PC through my own server — with a Windows 98–style phone app.

Devices log in with their own Ed25519 keys (no passwords), pair by scanning a QR code, and transfer files
directly to and from Cloudflare R2 with presigned URLs, so file bytes never pass through the API server.

## Features

- **Passwordless device auth** — each device keeps its private key locally; the server verifies a signed,
  single-use, short-lived challenge and issues a session token (only its hash is stored)
- **Hardware-bound identity** — a keyed (HMAC) fingerprint of the device's hardware IDs is checked at login
- **QR pairing** — the desktop shows a one-time code; the phone scans it to pair (and to receive its access credentials)
- **Direct-to-storage transfer** — batch uploads and downloads via presigned R2 URLs; uploads are verified in
  storage before they count, downloads are checksum-verified (SHA-256) before the file is deleted from R2
- **Safe downloads** — files land in per-type folders with sanitized, non-clashing names
- **Zero open ports** — the server sits behind a Cloudflare Tunnel and Cloudflare Access (service tokens)

## Architecture

```
phone (Expo) ──┐                                         ┌── Oracle Cloud VM (no inbound ports)
               ├── Cloudflare Access ── Cloudflare Tunnel ┤     ├── FastAPI + SQLite (Docker)
desktop (Py) ──┘   (service tokens)                       │     └── cloudflared
                                                          │
phone ⇄ Cloudflare R2 (presigned URLs, file bytes) ⇄ desktop
```

Details: [`DEPLOY.md`](DEPLOY.md) · API contract: [`API.md`](API.md)

## Stack

| Part | Tech |
|---|---|
| Server | Python 3.14, FastAPI, Pydantic, SQLite, `cryptography` (Ed25519) |
| Desktop client | Python (requests, qrcode) |
| Phone | Expo / React Native, Windows 98–inspired UI (separate repo) |
| File storage | Cloudflare R2 (S3-compatible, boto3) |
| Hosting | Oracle Cloud VM (Ubuntu), Docker, Cloudflare Tunnel + Access |
| CI/CD | GitHub Actions: Ruff + tests → image to GHCR → deploy through the tunnel |

## Repository layout

```
postie98/
  server/        FastAPI app (routes, repositories, schemas, tests, Dockerfile)
  desktop/       PC client (auth, pairing, downloads)
  .github/       CI/CD workflows
  API.md         API contract
  DEPLOY.md      deployment and operations
  NOTES.md       local dev notes and troubleshooting
```

## Running locally

Server (from `server/`, with its venv active):
```powershell
pip install -r requirements.txt
uvicorn server:app --reload          # http://127.0.0.1:8000/docs
```

Desktop client (from `desktop/`, second terminal):
```powershell
pip install -r requirements.txt
python main.py
```

Both read their settings from a local `.env` (never committed) — copy `.env.example` and fill it in.
More setup details and common errors: [`NOTES.md`](NOTES.md).

## Tests and code quality

```powershell
cd server
python -m unittest discover -s tests -v
coverage run -m unittest discover -s tests && coverage report -m
ruff check . && ruff format --check .        # from the repo root
```

CI runs Ruff and the tests on every pull request; merges to `main` deploy automatically.

## Roadmap

- [x] **M1** Server skeleton: schema, device registration
- [x] **M2** Auth: challenge → sign → verify → session token; reject replayed and expired challenges
- [x] **M3** Tests for the auth failure cases, in CI
- [x] **M4** Storage: presigned R2 uploads, verified in storage
- [x] **M5** Transfer: presigned downloads, checksum verification, cleanup
- [x] **M6** Phone app: own key in secure storage, register + login, UI design, batch upload
- [x] **M7** Pairing via QR; downloads sorted into per-type folders
- [ ] **M8** Deploy: Docker image, Oracle VM, Cloudflare Tunnel + Access, CD from GitHub Actions
- [ ] **M9** Features: unregister (phone + desktop), outbox, rename and delete files on the server, daily quote
- [ ] **M10** Phone polish: GIFs, UI updates, end-to-end testing
- [ ] **M11** Project polish: screenshots, cleanup, desktop auto-polling at a configurable interval

## Ideas for later

- Desktop waits for pairing over a WebSocket instead of polling
- Desktop approval step for new pairings ("Pixel 8 wants to pair — accept?")
- Restrict `/auth/register` to trusted devices (enrollment code or a device limit)
- Verify Cloudflare Access JWTs in the API (defense in depth)
- iOS support through a web client (ASP.NET Core)
- Phone: file previews, renaming before upload, "Share to Postie98"
- Local AI agent to rename and sort received files
- Random GIFs served from R2
- A nicer desktop UI (progress bars, a window instead of the terminal)
- ESP32 e-ink status display