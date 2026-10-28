from flask import Flask, render_template, request
import re

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_flash' # Required for session management if needed later

# Standard regex pattern for validating email format
EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    error = None
    success = None
    name = ''
    email = ''
    message = ''

    if request.method == 'POST':
        # Retrieve form fields and strip whitespace
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        # 1. Server-side check for empty fields
        missing_fields = []
        if not name:
            missing_fields.append('Name')
        if not email:
            missing_fields.append('Email')
        if not message:
            missing_fields.append('Message')

        if missing_fields:
            error = f"The following required field(s) are missing: {', '.join(missing_fields)}."
        
        # 2. Server-side check for valid email format (only if email isn't already empty)
        elif not re.match(EMAIL_REGEX, email):
            error = "Invalid email format. Please enter a valid email address (e.g., user@example.com)."
        
        # 3. Success state
        else:
            success = f"Thank you, {name}! Your message has been sent successfully."
            # Clear fields after successful submission
            name, email, message = '', '', ''

    return render_template('contact.html', error=error, success=success, name=name, email=email, message=message)

if __name__ == '__main__':
    app.run(debug=True)