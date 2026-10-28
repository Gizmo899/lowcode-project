import re

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

# Pragmatic email check: something@domain.tld, no spaces, one "@".
# For stricter validation (e.g. DNS checks), swap in the `email-validator` package.
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")

FIELDS = ("name", "email", "message")


def validate_contact(form):
    """Validate submitted form data on the server.

    Returns (cleaned_values, errors), where errors maps a field name
    to a human-readable message.
    """
    values = {field: (form.get(field) or "").strip() for field in FIELDS}
    errors = {}

    if not values["name"]:
        errors["name"] = "Enter your name."

    if not values["email"]:
        errors["email"] = "Enter your email address."
    elif len(values["email"]) > 254 or not EMAIL_RE.match(values["email"]):
        errors["email"] = "Enter a valid email address, like name@example.com."

    if not values["message"]:
        errors["message"] = "Enter a message."

    return values, errors


@app.route("/")
def index():
    return redirect(url_for("contact"))


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        return render_template("contact.html", values={}, errors={}, success=False)

    values, errors = validate_contact(request.form)

    if errors:
        # 400 so API clients and tests can tell the submission was rejected.
        return render_template("contact.html", values=values, errors=errors, success=False), 400

    # Nothing is stored yet. This is where you'd save to a DB or send an email.
    return render_template("contact.html", values={}, errors={}, success=True, name=values["name"])


if __name__ == "__main__":
    app.run(debug=True)
