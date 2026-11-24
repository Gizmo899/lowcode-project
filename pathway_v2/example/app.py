"""A deliberately tiny Flask app for the club equipment loans example.

Run it (after: python tools/migrate.py app.db --schema schema):
    Mac:      python3 app.py
    Windows:  python app.py
Then open http://127.0.0.1:5000

All database work happens in db.py. This file only deals with web pages.
"""
import sqlite3

from flask import Flask, abort, redirect, render_template_string, request, url_for

import db

app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Club equipment loans</title></head>
<body style="font-family: sans-serif; max-width: 46rem; margin: 2rem auto;">
<h1>Club equipment loans</h1>
{% if error %}<p role="alert" style="color:#C0392B">{{ error }}</p>{% endif %}
<table border="1" cellpadding="6" style="border-collapse: collapse;">
<tr><th>Item</th><th>Member</th><th>Borrowed</th><th>Due</th><th>Returned</th></tr>
{% for loan in loans %}
<tr><td>{{ loan.tag }} {{ loan.equipment_name }}</td><td>{{ loan.full_name }}</td>
<td>{{ loan.borrowed_on }}</td><td>{{ loan.due_on or "" }}</td><td>{{ loan.returned_on or "still out" }}</td></tr>
{% else %}<tr><td colspan="5">No loans yet.</td></tr>{% endfor %}
</table>
<h2>Lend an item</h2>
<form method="post" action="{{ url_for('create_loan') }}">
<label>Member <select name="member_id">{% for m in members %}<option value="{{ m.id }}">{{ m.full_name }}</option>{% endfor %}</select></label>
<label>Item <select name="equipment_id">{% for e in equipment %}<option value="{{ e.id }}">{{ e.tag }} {{ e.name }}</option>{% endfor %}</select></label>
<button type="submit">Lend</button>
</form>
</body></html>"""


def home_page(error=None, status=200):
    return render_template_string(
        PAGE, loans=db.list_loans(), members=db.list_members(),
        equipment=db.list_equipment(), error=error), status


@app.get("/")
def index():
    return home_page()


@app.post("/loans")
def create_loan():
    try:
        db.create_loan(int(request.form["member_id"]), int(request.form["equipment_id"]))
    except (KeyError, ValueError):
        return home_page("Please choose a member and an item.", 400)
    except sqlite3.IntegrityError:
        return home_page("That item is already out on loan, or the member or item no longer exists.", 409)
    return redirect(url_for("index"))


@app.get("/loans/<int:loan_id>")
def show_loan(loan_id):
    loan = db.get_loan(loan_id)
    if loan is None:
        abort(404)  # not found is a 404, never a crash (500)
    return loan  # Flask turns a dict into JSON


if __name__ == "__main__":
    app.run(debug=False)
