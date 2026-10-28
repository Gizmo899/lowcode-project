# Hello from Fabio

A minimal Flask 3 web app. It serves one page at `/` that says "Hello from Fabio".

## Install

Requires Python 3.9 or newer.

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open <http://127.0.0.1:5000/> in your browser. Press `Ctrl+C` to stop.

## Notes

- `app.py` runs with `debug=True` for local development. Turn it off before deploying.
- If port 5000 is taken, change the last line of `app.py` to `app.run(debug=True, port=5001)`.
# lowcode-project