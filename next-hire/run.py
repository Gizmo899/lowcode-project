from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    # The built-in server is intended for local PoC use only.
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
