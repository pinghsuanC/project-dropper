# Deploy: Oracle VM (Ubuntu, VM.Standard.E2.1.Micro)

Server: `ssh -i ~/.ssh/oracle-ssh-key-2026-11-18.key ubuntu@<public-ip>` (or `ssh dropper` with the SSH config entry).

## Done
- [x] Instance created (Montreal, E2.1.Micro, 1 GB RAM)
- [x] SSH access working
- [x] `sudo apt update && sudo apt upgrade -y`
- [x] 2 GB swap file (`free -h` shows Swap ≈ 2.0Gi)

## Next

### 1. Python 3.14 (code uses `uuid.uuid7()`, which needs 3.14+)
Ubuntu's built-in Python is older — install 3.14 with uv, don't touch the system one:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv python install 3.14
```
(Alternative: switch the code to `uuid.uuid4()`, which works on any version.)

### 2. Get the code
```bash
cd ~
git clone https://github.com/pinghsuanC/project-dropper.git
cd project-dropper/server
```
If the repo is **private**, cloning over HTTPS needs auth. Options:
- a GitHub **deploy key**: generate a key pair on the VM (`ssh-keygen -t ed25519`), add the `.pub` to the repo under Settings → Deploy keys (read-only), clone with the `git@github.com:` URL
- or a fine-grained personal access token with read-only access to this one repo

### 3. Virtual environment + dependencies
```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements.txt     # or: pip install -r requirements.txt
python --version                        # should say 3.14.x
```

### 4. Production `.env` (on the server only — never committed, never the dev values)
```bash
nano .env
```
Fill in every variable the server reads (same names as dev). Generate a **new** HMAC secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Checklist:
- [ ] `HMAC_SECRET` — new value
- [ ] `DB_PATH` — e.g. `data/dropper.db` (folder is created on startup)
- [ ] R2: account id, access key id, secret key, bucket (consider a separate R2 token for production)
- [ ] `chmod 600 .env` so only your user can read it

### 5. Try it by hand
```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```
In a second SSH session:
```bash
curl localhost:8000/health        # → {"status":"ok"}
```
Bind to `127.0.0.1` (not `0.0.0.0`): only the tunnel should reach it, nothing from the internet directly.

### 6. Cloudflare Tunnel → `dropper.pinghsuan.dev`
- Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create a tunnel (Cloudflared)
- Pick the **Linux / Debian, x86-64** install command, run it on the VM (installs `cloudflared` as a service)
- Public hostname: subdomain `dropper`, domain `pinghsuan.dev`, service `http://localhost:8000`
- Test from anywhere: `https://dropper.pinghsuan.dev/health`

### 7. systemd service (starts on boot, restarts on crash)
`sudo nano /etc/systemd/system/dropper.service`:
```ini
[Unit]
Description=File Dropper API
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/project-dropper/server
ExecStart=/home/ubuntu/project-dropper/server/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dropper
systemctl status dropper          # should say active (running)
journalctl -u dropper -f          # live logs
```

### 8. Production hardening
- [ ] Turn off `/docs` in production (`FastAPI(docs_url=None, redoc_url=None)` when an env flag is set)
- [ ] Security list: only port 22 open inbound (the tunnel needs no inbound ports)
- [ ] Daily SQLite backup (e.g. copy `data/dropper.db` to R2 under `backups/` — exclude that prefix from the lifecycle rule)
- [ ] `sudo apt install unattended-upgrades` for automatic security updates

### 9. Point the clients at it
- Desktop `.env`: `API_BASE_URL=https://dropper.pinghsuan.dev`
- Phone `.env`: `EXPO_PUBLIC_API_BASE_URL=https://dropper.pinghsuan.dev` (restart `npx expo start`)
- Devices register again on the new server (fresh database), then re-pair

## Updating later
```bash
ssh dropper
cd ~/project-dropper && git pull
cd server && source .venv/bin/activate && uv pip install -r requirements.txt
sudo systemctl restart dropper
```