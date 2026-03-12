from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# This route will display your confirmation page
@app.route('/')
def index():
    # This renders the templates/index.html file
    return render_template('index.html')

# This route handles the "Yes" and "No" button clicks
@app.route('/confirm_button', methods=['POST'])
def confirm_button():
    # 'submit_button' is the 'name' of our buttons in the HTML
    action = request.form.get('submit_button')

    if action == 'confirm':
        # User clicked "Yes"
        print("Email blast confirmed! Sending emails...")
        # Add your email sending logic here
        # You might want to redirect to a "success" page afterwards
        return "Emails are being sent!" # Placeholder response
    else:
        # User clicked "No" or something went wrong
        print("Email blast cancelled.")
        # Redirect back to the home page or a "cancelled" page
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
