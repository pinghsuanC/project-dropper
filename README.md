# File Dropper

Send files from my phone to my PC (and back) through my own server.
Devices log in with their own keys. No passwords.

## Stack

| Part | Tech |
|---|---|
| Server | Python + FastAPI + uvicorn + sqlite3 |
| Desktop client | Python scripts |
| Phone | Expo (separate repo) |
| File storage | Cloudflare R2 (S3-compatible) |
| Deployment | Oracle VM |

## Project layout

```
file-dropper/
  server/      FastAPI server, own .venv + requirements.txt
  desktop/     PC client, own .venv + requirements.txt
  file-dropper.code-workspace
  README.md
```

Expo is in its own repository.

---

## Setup (first time, or after cloning on a new machine)

*Do this separately inside `server/` and inside `desktop/`.*

```powershell
# create the venv (the label shows in the prompt as (server) or (desktop))
python -m venv .venv --prompt server

# activate it (PowerShell)
.venv\Scripts\Activate.ps1

# install dependencies
pip install -r requirements.txt
```

If PowerShell says scripts are disabled:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

> A venv can't be moved or renamed. If you move the folder, delete `.venv` and recreate it.

## Day-to-day

### Run the server (from `server/`)

```powershell
uvicorn server:app --reload
# if "uvicorn is not recognized":
python -m uvicorn server:app --reload
```

`server:app` means file `server.py`, variable `app = FastAPI()`.

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

### Run the desktop client (from `desktop/`, in a second terminal)

```powershell
python main.py
```

### After installing a new package

```powershell
pip freeze > requirements.txt
```

### Lint and format

```powershell
ruff check .
ruff format .
```

### Editor (VS Code)

- Install the **Ruff** extension (Astral Software, `charliermarsh.ruff`)
- Each folder's `.vscode/settings.json` sets its interpreter and enables format + fix on save

### Deactivate the venv

```powershell
deactivate
```

---

## Which venv am I in?

```powershell
python -c "import sys; print(sys.executable)"   # full path of the running Python
pip -V                                          # where pip will install
where python                                    # every python on PATH, first one wins
```

In VS Code: Ctrl+Shift+P → **Python: Select Interpreter** → pick the folder → pick its `.venv`.
New terminals: the ⌄ next to **+** in the terminal panel → choose `server` or `desktop`.

---

## Environment variables

Secrets live in `.env` (never committed). Copy `.env.example` and fill in real values.
The code loads them with `python-dotenv` (`load_dotenv()`), so it works the same in VS Code, a plain terminal, and on the server VM.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `uvicorn is not recognized` | Wrong or inactive venv, or uvicorn not installed | Activate `server/.venv`, `pip install -r requirements.txt`, or use `python -m uvicorn ...` |
| `No Python at ...` after moving folders | Venvs store absolute paths | Delete `.venv` and recreate it |
| `No module named 'PIL'` | `qrcode.make()` needs Pillow for images | `pip install "qrcode[pil]"`, then refreeze |
| `Cannot convert str to a buffer` in `load_pem_private_key` | Passed the file path instead of the file contents | Pass `Path(...).read_bytes()` |
| Data not saved in sqlite | Missing `conn.commit()` | Commit after inserts |

---

## Roadmap

- [x] M1 Server skeleton: tables, save + fetch a device, initial register round calls deskto -> server -> response
- [x] M2 Auth: get challenge → sign → server verify and return session token -> desktop gets session token; reject bad and expired challenges
- [x] M3 Tests: `python -m unittest` covers the auth failure cases
- [x] M4 Storage: upload a file to R2 through `storage.py`, prepare the endpoint for mobile uploads.
- [x] M5 Transfer: download with a presigned URL, verify the checksum, delete
- [x] M6 Mobile app preparation: device fingerprint (Android ID) and its own Ed25519 key in secure storage; register + login like the desktop, UI design
- [x] M6.1 upload functionality
- [x] M6.2 Tests for batch upload (happy path, other device's id untouched, missing upload → 409)
- [x] M7 Pairing: QR pairing adds a second device, classify files by file types
- [ ] M8 Prepare domain & deploy to Oracle Cloud VM, set up CD / docker
- [ ] M9 Mobile functionality upgrades (propertiy screen, daily quote fetch, unregister, file rename, delete files from server); desktop upgrade (unregister)
- [ ] M9 Mobile app polish (update GIFs, UI updates, workflow end-to-end testing) 
- [ ] M10 Entirety Polish: R2 lifecycle rule, deploy (Oracle VM + Cloudflare Tunnel), README screenshots & clean up

- [ ] Automate desktop to ping every configured minutes

## Future items
- GIF loading system from R2
- Instead of a while loop on desktpp, use web socket to wait for pairing
- login for mobile, or 2FA
- White list Oracle server
- For IOS compatibility, make the mobiel side into a webapp
- Hook up with local AI agent to rename the files & classify files into different folders
- Server web app for some visual
- Mobile side preview functionality
- Mobile side ability to rename file