import re
from flask import Flask, render_template, request, flash, redirect, url_for

app = Flask(__name__)
# A secret key is required by Flask for session-based flash messages
app.secret_key = 'super-secret-key-change-in-production'

# Basic email regex for validating common email structures
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Retrieve form data and strip whitespace
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        
        # 1. Validation: Check for empty fields
        missing_fields = []
        if not name:
            missing_fields.append('Name')
        if not email:
            missing_fields.append('Email')
            
        if missing_fields:
            if len(missing_fields) == 1:
                flash(f"Please enter your {missing_fields[0]}.", "danger")
            else:
                flash(f"Please fill in all required fields: {', '.join(missing_fields)}.", "danger")
            # Render page with previously entered values so the user doesn't lose input
            return render_template('contact.html', name=name, email=email)

        # 2. Validation: Check email format validity
        if not re.match(EMAIL_REGEX, email):
            flash("Please enter a valid email address (e.g., user@example.com).", "danger")
            return render_template('contact.html', name=name, email=email)

        # 3. Success state (No data stored as requested)
        flash("Thank you! Your message has been successfully submitted.", "success")
        return redirect(url_for('contact'))

    # GET request
    return render_template('contact.html')


if __name__ == '__main__':
    app.run(debug=True)