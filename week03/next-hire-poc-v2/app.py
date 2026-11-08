from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    # This is the one place the in-process scheduler is started for development.
    # create_app() never starts it, so `flask run`, gunicorn and the CLI commands are
    # unaffected; for those, run `flask --app run.py run-scheduler` in one extra process.
    if app.config["START_SCHEDULER"]:
        from app.automations import start_scheduler
        start_scheduler(app)
        print("Background scheduler started (weekly digest Mondays 08:00, follow-up nudges hourly).")
    else:
        print("Background scheduler not started (START_SCHEDULER=false).")
    # The built-in server is intended for local PoC use only. use_reloader must stay
    # False: the reloader would run this block in two processes and start two schedulers.
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
