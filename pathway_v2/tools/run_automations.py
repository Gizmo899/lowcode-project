"""The hourly automation script: follow-up nudges, the Monday digest and the tidy-up.

Usage (from the top folder of the project):
    python tools/run_automations.py app.db

Start it every hour, on the hour, with the computer's own scheduler (see README.md).
It prints counts only, never personal data, so its output is safe to keep in a log file.
It works out Irish time itself, so the computer's own time zone does not matter.
"""

import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from automation_tasks import run_all  # noqa: E402
from db import get_connection  # noqa: E402
from utils import irish_now  # noqa: E402


def main(argv):
    config = {"SECRET_KEY": secrets.token_hex(32)}  # this script never signs a cookie, so a throwaway key is fine
    if len(argv) > 1:
        config["DATABASE"] = str(Path(argv[1]).resolve())
    app = create_app(config)
    with app.app_context():
        conn = get_connection()
        now = irish_now()
        results = run_all(conn, now)
    print(f"{now.isoformat(timespec='minutes')} {json.dumps(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
