# Contributing

## Setup

```
python -m venv venv && venv\Scripts\activate     # source venv/bin/activate on macOS / Linux
pip install -e ".[dev]"
```

Python 3.10 or newer.

## Checks (the same ones CI runs)

```
ruff check .
ruff format --check .      # `ruff format .` to fix
mypy                       # strict, covers crypto_alarm/
python -m unittest discover -s tests
```

## Conventions

- **Logic goes in pure functions** (`rules.py`, `engine.py`, `formatting.py`) that take values and
  return values: no clocks, locks or I/O. `Monitor` is the only place that owns shared state.
- **Shared state is guarded by one lock.** Do disk writes and callbacks outside it.
- **User-facing errors are `ValueError`s** with a message safe to show in the UI; the Socket.IO
  handler wrapper in `web.py` turns them into `error` events.
- **The browser shows, the server decides.** Add display text or derived numbers in `views.py` /
  `formatting.py`, not in JavaScript.
- Never log URLs that contain secrets (Telegram bot tokens are embedded in the request URL).

## Dependencies

Ranges live in `pyproject.toml`; exact versions for Docker are pinned in `requirements.lock`:

```
pip install -e ".[server]" && pip freeze --exclude-editable > requirements.lock
```

(keep the two comment lines at the top of that file).

## Running in production

One worker only; pairs, alarms and history live in the process:

```
gunicorn -k gthread -w 1 --threads 100 -b 127.0.0.1:5000 'crypto_alarm.web:create_app()'
```
