# Dev notes

Personal notes for working on Postie98 locally: setup details, editor config, and errors I've hit.

## Virtual environments

`server/` and `desktop/` each have their own `.venv` and `requirements.txt`.

```powershell
# create (the --prompt label shows as (server) or (desktop))
python -m venv .venv --prompt server

# activate (PowerShell)
.venv\Scripts\Activate.ps1

# install / record dependencies
pip install -r requirements.txt
pip freeze > requirements.txt        # after installing something new

deactivate
```

If PowerShell says scripts are disabled:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

A venv can't be moved or renamed. If the folder moves, delete `.venv` and recreate it.

**Which venv am I in?**
```powershell
python -c "import sys; print(sys.executable)"   # the running Python
pip -V                                          # where pip installs
where.exe python                                # every python on PATH, first one wins
```

## VS Code

- Multi-root workspace (`*.code-workspace`, gitignored): `server` and `desktop` as separate folders
- Each folder's `.vscode/settings.json` pins its interpreter:
  `"python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe"`
- New terminal for a specific folder: ⌄ next to **+** → pick `server` or `desktop`
- Ruff extension (Astral, `charliermarsh.ruff`), format + fix on save,
  **Ruff › Import Strategy → fromEnvironment** so the editor uses the venv's Ruff (same version as CI)
- Pylance type checking on `basic` (strict was too noisy with library unions)

## Running

```powershell
# server, from server/
uvicorn server:app --reload
python -m uvicorn server:app --reload     # if "uvicorn is not recognized"

# for the phone on the same Wi-Fi: listen on the LAN, phone uses http://<PC LAN IP>:8000
uvicorn server:app --host 0.0.0.0 --reload
```
`server:app` = file `server.py`, variable `app = FastAPI()`.

Local URLs: `http://127.0.0.1:8000/docs` (Swagger UI), `/health`.

## Environment variables

Secrets live in `.env`, never committed; `.env.example` holds placeholder names only.
Loaded with `python-dotenv` using a path built from `__file__` (not `./.env`, which depends on the working directory).

## Tests

```powershell
cd server
python -m unittest discover -s tests -v
python -m unittest tests.test_auth -v            # one file
coverage run -m unittest discover -s tests       # .coveragerc omits tests/ and .venv/
coverage report -m
```
Tests set `DB_PATH` to a temp file *before* importing the app, so they never touch the real database.

## Git

```powershell
git switch -c <branch>          # new branch
git push -u origin <branch>
git restore --staged <file>     # unstage
git commit --amend -m "..."     # fix the last commit message (then push --force-with-lease if pushed)
git rm -r --cached <path>       # stop tracking, keep the file
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `uvicorn is not recognized` | Wrong or inactive venv, or not installed | Activate `server/.venv`, `pip install -r requirements.txt`, or `python -m uvicorn` |
| Wrong venv in a new VS Code terminal | VS Code activates the folder's selected interpreter | Select Interpreter per folder; open terminals per folder |
| `No Python at ...` after moving folders | Venvs store absolute paths | Delete and recreate `.venv` |
| `ImportError: ... partially initialized module` | Circular import | Make dependencies one-directional (api clients ← auth ← agent) |
| `ImportError: cannot import name X` after a rename | Stale `__pycache__` | Delete the `__pycache__` folders |
| `cannot import name 'StrEnum' from 'enum'` | A local file named `enum.py` shadows the stdlib | Rename it (`enums.py`) |
| `attempted relative import beyond top-level package` | `from ..x import y` | Absolute imports, run from `server/` |
| `No module named 'PIL'` | `qrcode` images need Pillow | `pip install "qrcode[pil]"` |
| `Cannot convert str to a buffer` | Passed a path instead of file contents | `Path(...).read_bytes()` |
| `Error binding parameter … type 'X' is not supported` | Passing an object (key, UUID) to sqlite | Pass the string form (PEM, `str(uuid)`) |
| `Incorrect number of bindings supplied` | `(value)` instead of `(value,)`, or `?` count mismatch | One-item tuples need the comma; count columns / `?` / values |
| `cannot commit transaction - SQL statements in progress` | `RETURNING` rows not fetched | `.fetchall()` inside the `with` block |
| `'dict' object has no attribute ...` | Dict vs model access mixed up | Dicts/Rows: `x["key"]`; Pydantic models: `x.key` |
| `'X' object is not subscriptable` | Pydantic model accessed like a dict | `body.field`, not `body["field"]` |
| `except` doesn't catch the library's error | Own class with the same name shadows it | Import the library's exception; name own ones differently |
| Ruff differs locally vs CI | Different versions / config / first-party detection | Same Ruff version everywhere; root `ruff.toml` with `src = ["server", "desktop"]` |
| `CreateProcessW failed error:2` on `ssh` | SSH can't find `cloudflared.exe` | New terminal, or full path in `ProxyCommand` |