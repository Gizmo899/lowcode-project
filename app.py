import re
from urllib.parse import urlparse
from flask import Flask, render_template, request

app = Flask(__name__)

# Basic RFC 5322-compliant regex for validating email format
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_contact_form(name, email, message):
    errors = {}

    if not name or not name.strip():
        errors["name"] = "Name is required."

    if not email or not email.strip():
        errors["email"] = "Email address is required."
    elif not EMAIL_REGEX.match(email.strip()):
        errors["email"] = "Please enter a valid email address."

    if not message or not message.strip():
        errors["message"] = "Message cannot be empty."

    return errors

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        errors = validate_contact_form(name, email, message)

        if errors:
            # Re-render with user input preserved and HTTP 400 Bad Request status
            return (
                render_template(
                    "contact.html",
                    errors=errors,
                    values={"name": name, "email": email, "message": message},
                ),
                400,
            )

        # Process form submission (e.g., send email, log, or store in DB)
        return render_template("contact.html", success=True, name=name)

    return render_template("contact.html", errors={}, values={})

if __name__ == "__main__":
    app.run(debug=True)