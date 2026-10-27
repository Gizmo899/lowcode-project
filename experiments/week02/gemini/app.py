import re
from flask import Flask, render_template, request

app = Flask(__name__)

# Standard library regex for basic email validation
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Retrieve and sanitize input data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()
        
        errors = []
        
        # Server-side validation
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        elif not EMAIL_REGEX.match(email):
            errors.append("Please enter a valid email address.")
        if not message:
            errors.append("Message is required.")
            
        if errors:
            # Re-render form with error message(s), preserve user input, and return HTTP 400
            return render_template(
                'contact.html',
                error=" ".join(errors),
                name=name,
                email=email,
                message=message
            ), 400
            
        # On success, render confirmation page
        return render_template('success.html', name=name)
        
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)