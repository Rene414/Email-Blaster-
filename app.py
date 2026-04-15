from flask import Flask, render_template, request, flash, abort, send_file, redirect, url_for, session
import pandas as pd
from io import StringIO
import csv
from datetime import datetime
from zoneinfo import ZoneInfo

from functools import wraps

from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, fresh_login_required, login_required, UserMixin, login_user, logout_user
from flask_socketio import SocketIO

import secrets
import string
import re
import base64
import uuid


app=Flask(__name__)

app.secret_key = 'qL5=shBVtq*V+J#H*F]wew.5CFGG!oZj' 
socketio = SocketIO(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_BINDS'] = {
    'count': 'sqlite:///logs.db', # Secondary DB
    'token_links': 'sqlite:///confirm_links.db', #Third DB
    'documentation' : 'sqlite:///email_blast_documentation.db',
    'saved_emails': 'sqlite:///saved_emails.db',
    'email_contents': 'sqlite:///email_contents.db'
}
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)

login_manager=LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'login_page'
login_manager.login_message = "Please log in to access this page."



db = SQLAlchemy(app)

'''class Counter(db.Model):
    __bind_key__='count'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    count = db.Column(db.Integer, default=0)
'''
class Logs(db.Model):
    __bind_key__='count'
    id = db.Column(db.Integer, primary_key=True)
    email_unique_id = email_subject = db.Column(db.String(15), unique=True)
    email_subject = db.Column(db.String(200))
    email_timestamp = db.Column(db.String(100))
    confirmation_one = db.Column(db.String(80), nullable =True)
    confirmation_two = db.Column(db.String(80), nullable = True)
    status = db.Column(db.String(100))
    submitted = db.Column(db.Boolean, default = False)

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable = False)
    email_address = db.Column(db.String(100), unique = True)
    password = db.Column(db.String(100), nullable = False)
    admin = db.Column(db.Boolean, default = False)

class SingleUseLink(db.Model):
    __bind_key__= "token_links"
    id = db.Column(db.Integer, primary_key=True)
    email_unique_id = db.Column(db.String(15))
    user_email = db.Column(db.String(120))
    email_subject = db.Column(db.String(180))
    is_used = db.Column(db.Boolean, default = False)
    created_at = db.Column(db.DateTime, default = datetime.utcnow)
    
class Documentation(db.Model):
    __bind_key__= "documentation"
    id = db.Column(db.Integer, primary_key=True)
    client_email = db.Column(db.String(100), nullable = False)
    client_name = db.Column(db.String(100), nullable = True)
    email_subject = db.Column(db.String(180), nullable = False)
    email_unique_id = db.Column(db.String(15))
    date_sent = db.Column(db.String(100))

class SavedEmails(db.Model):
    __bind_key__= "saved_emails"
    id = db.Column(db.Integer, primary_key=True)
    email_unique_id = db.Column(db.String(15))
    creator = db.Column(db.String(100), nullable = False)
    email_subject = db.Column(db.String(180), nullable = False)
    email_content = db.Column(db.Text, nullable = False)
    date_saved = db.Column(db.String(100))

class EmailContent(db.Model):
    __bind_key__= "email_contents"
    id = db.Column(db.Integer, primary_key=True)
    email_unique_id = db.Column(db.String(15))
    creator = db.Column(db.String(100), nullable = False)
    email_subject = db.Column(db.String(180), nullable = False)
    email_content = db.Column(db.Text, nullable = False)
    date_saved = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, int(user_id))

def initialize_database():
    with app.app_context():
        # Create all tables defined by the models
        db.create_all()
        # Check if the 'button_clicks' counter exists, if not, create it
        '''if not Counter.query.filter_by(name='button_clicks').first():
            initial_counter = Counter(name='button_clicks', count=0)
            db.session.add(initial_counter)
            db.session.commit()'''
        if not Users.query.filter_by(username='Rena').first():
            rena_user = Users(username='Rena', email_address = "renatestt@gmail.com", password = 'password', admin = True)
            rena2_user = Users(username='RenaTwo', email_address = "rena@cbt.io", password = 'password', admin = True)
            db.session.add(rena_user)
            db.session.add(rena2_user)
            db.session.commit()

'''def create_link():
    link = url_for('confirm_email_page', token = "", _external=True)'''

html_template="""\
<html>
    <body style = "background-color: white; display:flex; justify-content: center; align-items: center;" >
    
        <div class = "box" style = "background-color: rgb(189, 218, 226); border-radius: 10px; padding: 30px; height: 700px; width:600px; text-align: center;">
            <h2>Test</h2>
            <div class = "message" style = "position: relative; top: 50px; left: -250px;">
                <p>{message}</p>
            </div>
        </div>
        
    </body>
</html>
"""

button_template="""\
<html>
    <body>
        <p>Please click the button if this is the correct email you'd like to send.</p>
        <form method="POST" action="/confirm_email/<token>">
            <a href = "http://127.0.0.1:5000/confirm_email/<id>/<admin_email>" class = "confirm_button"> Confirm</a>
        </form>
    </body>
</html>
"""


def find_time():
    token_received_time = datetime.now(timezone.utc)
    return token_received_time

def message_function (text, subject, client_name, html):
    msg_root = MIMEMultipart('related')
    msg_alternative =  MIMEMultipart('alternative')
    msg_root.attach(msg_alternative)
    #if "[client]" in text:
    customized_body = text.replace("[Client]", client_name)
    html_content = html_template.format(message=customized_body)
    msg_root['Subject'] = subject
    if html == None:
        image_pattern = r'src="data:image/(?P<ext>.*?);base64,(?P<data>.*?)"'
        images = re.finditer(image_pattern, text)
        final_html=customized_body
        if images:
            for i, match in enumerate(images):
                ext = match.group('ext')
                data = match.group('data')
                content_id = f"image_{i}_{uuid.uuid4().hex}"
                base64_string = f"data:image/{ext};base64,{data}"
                final_html = final_html.replace(base64_string, f"cid:{content_id}")
                image_bytes = base64.b64decode(data)
                msg_image = MIMEImage(image_bytes, _subtype=ext)
                msg_image.add_header('Content-ID', f'<{content_id}>')
                msg_image.add_header('Content-Disposition', 'inline', filename=f"{content_id}.{ext}")
                msg_root.attach(msg_image)
        msg_alternative.attach(MIMEText(final_html, 'html'))
    else:
        image_pattern = r'src="data:image/(?P<ext>.*?);base64,(?P<data>.*?)"'
        images = re.finditer(image_pattern, text)
        final_html=html_content
        if images:
            for i, match in enumerate(images):
                ext = match.group('ext')
                data = match.group('data')
                content_id = f"image_{i}_{uuid.uuid4().hex}"
                base64_string = f"data:image/{ext};base64,{data}"
                final_html = final_html.replace(base64_string, f"cid:{content_id}")
                image_bytes = base64.b64decode(data)
                msg_image = MIMEImage(image_bytes, _subtype=ext)
                msg_image.add_header('Content-ID', f'<{content_id}>')
                msg_image.add_header('Content-Disposition', 'inline', filename=f"{content_id}.{ext}")
                msg_root.attach(msg_image)
        msg_alternative.attach(MIMEText(final_html, 'html'))
    return msg_root


def confirm_button_function (email_id, text, subject, html, admin_email):
    msg_mixed =  MIMEMultipart('mixed')
    msg_root = MIMEMultipart('related')
    msg_alternative =  MIMEMultipart('alternative')
    msg_mixed.attach(msg_alternative)
    msg_mixed.attach(msg_root)
    html_content = html_template.format(message=text)
    msg_mixed['Subject'] = "Email Blast Request: "+ subject
    if html == None:
        image_pattern = r'src="data:image/(?P<ext>.*?);base64,(?P<data>.*?)"'
        images = re.finditer(image_pattern, text)
        final_html=text
        if images:
            for i, match in enumerate(images):
                ext = match.group('ext')
                data = match.group('data')
                content_id = f"image_{i}_{uuid.uuid4().hex}"
                base64_string = f"data:image/{ext};base64,{data}"
                final_html = final_html.replace(base64_string, f"cid:{content_id}")
                image_bytes = base64.b64decode(data)
                msg_image = MIMEImage(image_bytes, _subtype=ext)
                msg_image.add_header('Content-ID', f'<{content_id}>')
                msg_image.add_header('Content-Disposition', 'inline', filename=f"{content_id}.{ext}")
                msg_root.attach(msg_image)
        msg_alternative.attach(MIMEText(final_html, 'html'))
    else:
        image_pattern = r'src="data:image/(?P<ext>.*?);base64,(?P<data>.*?)"'
        images = re.finditer(image_pattern, text)
        final_html=html_content
        if images:
            for i, match in enumerate(images):
                ext = match.group('ext')
                data = match.group('data')
                content_id = f"image_{i}_{uuid.uuid4().hex}"
                base64_string = f"data:image/{ext};base64,{data}"
                final_html = final_html.replace(base64_string, f"cid:{content_id}")
                image_bytes = base64.b64decode(data)
                msg_image = MIMEImage(image_bytes, _subtype=ext)
                msg_image.add_header('Content-ID', f'<{content_id}>')
                msg_image.add_header('Content-Disposition', 'inline', filename=f"{content_id}.{ext}")
                msg_root.attach(msg_image)
        msg_alternative.attach(MIMEText(final_html, 'html'))
    '''token_of_admin = SingleUseLink.query.filter_by(email_subject = subject, user_email=admin_email).first()
    token = token_of_admin.token'''
    new_button_template =  button_template.replace("<id>", email_id)
    final_button_template =  new_button_template.replace("<admin_email>", admin_email)
    msg_mixed.attach(MIMEText(final_button_template, "html"))
    return msg_mixed




@app.route('/')
@login_required
def frontend():
    all_saved_emails = SavedEmails.query.filter_by(creator = current_user.email_address).all()
    all_confirmed_emails= Logs.query.filter_by(status = "Waiting Confirmation").all()
    confirm1 = Logs.query.filter(Logs.confirmation_one.isnot(None)).all()
    confirm2 = Logs.query.filter(Logs.confirmation_two.isnot(None)).all()
    return render_template('Frontend.html', email_list = all_saved_emails, confirmed_emails= all_confirmed_emails, confirm1 = confirm1, confirm2 = confirm2)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method =="POST":
        user = Users.query.filter_by(username = request.form['username']).first()
        password =request.form['password']
        if user and password==user.password:
            login_user(user, fresh=True)
            print('Logged in')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('frontend'))
        flash('Invalid Credentials')
    return render_template('login.html')

'''def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.admin ==False:
            flash('access denied')
            return redirect(url_for('frontend'))
        return f(*args, **kwargs)
    return decorated_function'''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You're being logged out")
    return redirect(url_for('login_page'))


'''def get_date():
    pst = pytz.timezone("US/Pacific")
    now_pst=datetime.now(pst)
    today = now_pst.date()
    return today'''

'''def create_csv(row, date):
    csv_name = f"{date} Emails_Outputted.csv"
    with open(csv_name, mode = 'a', newline = '') as file:
        writer = csv.writer(file)
        writer.writerow(row)'''

def send_email(CSV_File, email_content, email_id, email_subject, html):
    smtp = smtplib.SMTP('send.smtp.com', 587)
    smtp.ehlo()
    smtp.starttls()
    if CSV_File:
        content = CSV_File.decode('utf-8')
        df=pd.read_csv(StringIO(content))
        csv_row_count = len(df)
        csv_row =0
        #create_csv(['Organization', "Name","Email"], get_date())
        while csv_row<csv_row_count:
            email_name = df.loc[csv_row, "Name"]
            email=df.loc[csv_row, "Email"]
            #email_organization=df.loc[csv_row, "Organization"]
            msg = message_function(email_content, email_subject, email_name, html)
            smtp.sendmail(from_addr= "noreply@cbt.io", to_addrs= email, msg = msg.as_string())
            new_documentation = Documentation(client_email = email, client_name = email_name, email_subject = email_subject, email_unique_id= email_id, date_sent = datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p'))
            db.session.add(new_documentation)
            db.session.commit()
            #create_csv([email_organization, email_name, email], get_date())
            csv_row+=1
        smtp.quit()
        latest_log = Logs.query.filter_by(email_unique_id=email_id).first()
        latest_log.submitted = True
        db.session.commit()
        return render_template('Submitted.html')
    else:
        return render_template('Frontend.html', data = {}) #Replace with way to show that files haven't been inputted

#Note, in order for the different names to occur, you must put [client] exactly

'''def assign_token_links(email_subject):
    users_database = Users.query.all()
    for users in users_database:
        if users.admin == True:
            random_token = str(uuid.uuid4())
            random_link = SingleUseLink(token=random_token, user_email=users.email_address, email_subject = email_subject)
            db.session.add(random_link)
            db.session.commit()'''



def confirm_email(email_id, email_content, email_subject, html):
    #assign_token_links(email_subject)
    smtp = smtplib.SMTP('send.smtp.com', 587)
    smtp.ehlo()
    smtp.starttls()
    
    '''global start_time 
    start_time = find_time()'''
    '''counter_obj = Counter.query.filter_by(name="button_clicks").first()
    counter_obj.count = 0'''
    #db.session.commit()
    admin_users = Users.query.filter_by(admin=True).all()
    
    for admin in admin_users:
        msg = confirm_button_function(email_id, email_content, email_subject, html, admin.email_address)
        smtp.sendmail(from_addr= "noreply@cbt.io", to_addrs= admin.email_address, msg = msg.as_string())
    #smtp.sendmail(from_addr= "noreply@cbt.io", to_addrs= 'rena@cbt.io', msg = msg.as_string())
    smtp.quit()

def generate_short_id():
    # Alphabet: uppercase, lowercase, and digits (62 possible characters)
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def assign_admin_to_email(email_id, email_subject):
    users_database = Users.query.all()
    for users in users_database:
        if users.admin == True:
            token_entry= SingleUseLink(email_unique_id=email_id, user_email=users.email_address, email_subject = email_subject)
            db.session.add(token_entry)
            db.session.commit()

#finished_pending={'finished_pending':'False'}
@app.route('/create_email', methods=['GET','POST'])
def create_email():
    if request.method == 'POST':
        '''csv_category = request.form.get('csv_type')
        if csv_category == "preset_csv":
            preset_chosen = request.form.get('preset_csv_options')
            if preset_chosen =="Rena Emails":
                with open('Rena Email CSV.csv', 'rb') as f:
                    file = f.read()
        elif csv_category == "custom_csv":
            files = request.files.get('file')
            file = files.read()'''
        btn_clicked = request.form.get('action_type')
        #file =request.files.get('file')
        email=request.form['emailContent']
        subject = request.form['subject']
        html = request.form.get('HtmlButton')
        data = {
                'emailContent': email, 
                'subject': subject, 
                'html':html}
        if btn_clicked == "save":
            email_unique_id = generate_short_id()
            #datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p')
            new_saved_email = SavedEmails(email_unique_id = email_unique_id, creator = current_user.email_address, email_subject = subject, email_content = email, date_saved = datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p'))
            db.session.add(new_saved_email)
            db.session.commit()
            new_log = Logs(email_subject= subject, email_unique_id = email_unique_id, email_timestamp =datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p'), status = "Saved")
            db.session.add(new_log)
            db.session.commit()
            return redirect(url_for('frontend'))
        if btn_clicked == 'confirm':
            print('confirm button clicked')
            email_unique_id = generate_short_id()
            print(f"Function triggered at: {datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p')}")
            log_email_entry = Logs(email_subject= subject, email_unique_id = email_unique_id, email_timestamp =datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p'),status = "Waiting Confirmation")
            db.session.add(log_email_entry)
            db.session.commit()
            new_email_entry = EmailContent(email_unique_id=email_unique_id, creator = current_user.email_address, email_subject = subject, email_content = email, date_saved = datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p'))
            db.session.add(new_email_entry)
            db.session.commit()
            assign_admin_to_email(email_unique_id, subject)
            confirm_email(email_unique_id, email, subject, html)
            return render_template('confirmed_emails.html', email_unique_id = email_unique_id, data = data)
    
    return render_template('create_email.html')

@app.route('/get_status/<email_unique_id>')
def get_status(email_unique_id):
    log_entry = Logs.query.filter_by(email_unique_id=email_unique_id).first()
    if log_entry.confirmation_one and log_entry.confirmation_two:
        return {'status': 'confirms_done'}
    else:
        return {'status': 'confirms not done'}


@app.route('/saved_emails/<email_unique_id>', methods=['GET','POST'])
def saved_emails(email_unique_id):
    find_saved_email = SavedEmails.query.filter_by(creator = current_user.email_address, email_unique_id=email_unique_id).first()
    data={
                'emailContent': find_saved_email.email_content, 
                'subject': find_saved_email.email_subject,
                'date_saved': find_saved_email.date_saved}
    
    if request.method == 'POST':
        
        btn_clicked = request.form.get('action_type')
        email=request.form['emailContent']
        subject = request.form['subject']
        html = request.form.get('HtmlButton')
        if btn_clicked == 'update':
            saved_email = SavedEmails.query.filter_by(email_unique_id=email_unique_id).first()
            saved_email.email_content = email
            saved_email.email_subject = subject
            saved_email.date_saved = datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p')
            db.session.commit()
            data2={
                'emailContent': find_saved_email.email_content, 
                'subject': find_saved_email.email_subject,
                'date_saved': find_saved_email.date_saved
            }
            return render_template('saved_emails.html', email_unique_id = email_unique_id, data=data2)
        if btn_clicked == 'confirm':
            data3={
                'emailContent': find_saved_email.email_content, 
                'subject': find_saved_email.email_subject,
                'date_saved': find_saved_email.date_saved}
            log_email_entry = Logs.query.filter_by(email_unique_id=email_unique_id).first()
            log_email_entry.status = "Waiting Confirmation"
            db.session.commit()
            print('confirm button clicked')
            assign_admin_to_email(email_unique_id, subject)
            confirm_email(email_unique_id, email, subject, html)
            delete_saved_email = SavedEmails.query.filter_by(email_unique_id=email_unique_id).first()
            if delete_saved_email:
                db.session.delete(delete_saved_email)
                db.session.commit()
            new_email_entry = EmailContent(email_unique_id=email_unique_id, creator = current_user.email_address, email_subject = subject, email_content = email, date_saved = datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%m/%d/%y %I:%M %p'))
            db.session.add(new_email_entry)
            db.session.commit()
            return render_template('confirmed_emails.html', email_unique_id = email_unique_id, data = data3)
    return render_template('saved_emails.html', email_unique_id = email_unique_id, data=data)

@app.route('/confirmed_emails/<email_unique_id>', methods=['GET','POST'])
def confirmed_emails(email_unique_id):
    email_data = EmailContent.query.filter_by(email_unique_id=email_unique_id).first()
    subject = email_data.email_subject
    content = email_data.email_content
    data = {
                'emailContent': content, 
                'subject': subject}
    check_confirms= Logs.query.filter_by(email_unique_id=email_unique_id).first()
   
    confirms = True if check_confirms.confirmation_two else False

    if request.method == 'POST':
        btn_clicked = request.form.get('action_type')
        if btn_clicked == 'submit':
            print('confirm button clicked')
            log_email_entry = Logs.query.filter_by(email_unique_id=email_unique_id).first()
            log_email_entry.status = "Confirmed"
            db.session.commit()
            

            return render_template('submit_email.html', email_unique_id = email_unique_id, data = data)
    return render_template('confirmed_emails.html', email_unique_id = email_unique_id, data=data, confirms=confirms)



#form_info={'file': '', 'email': '', 'subject': '', 'html':''}
@app.route('/submit/<email_unique_id>', methods=['GET', 'POST'])
def submit_email(email_unique_id):
    if request.method == 'POST':
        csv_category = request.form.get('csv_type')
        if csv_category == "preset_csv":
            preset_chosen = request.form.get('preset_csv_options')
            if preset_chosen =="Rena Emails":
                with open('Rena Email CSV.csv', 'rb') as f:
                    file = f.read()
        elif csv_category == "custom_csv":
            files = request.files.get('file')
            file = files.read()
        btn_clicked = request.form.get('action_type')
        #file =request.files.get('file')
        email=request.form['emailContent']
        subject = request.form['subject']
        html = request.form.get('HtmlButton')
        email_data = EmailContent.query.filter_by(email_unique_id=email_unique_id).first()
        subject = email_data.email_subject
        content = email_data.email_content
        data = {
                'emailContent': content, 
                'subject': subject}
        '''data = {
                'emailContent': email, 
                'subject': subject, 
                'html':html}'''
        
        if btn_clicked == 'submit':
            #FIX THISSSSS
            record = Logs.query.filter_by(email_unique_id=email_unique_id).first()
            if record:
                record.status = "Submitted"
                db.session.commit()
            record2 = EmailContent.query.filter_by(email_unique_id=email_unique_id).first()
            if record2:
                db.session.delete(record2)
                db.session.commit()
            send_email(file, email, email_unique_id, subject, html)
            return redirect(url_for('frontend'))
      
    return render_template("submit_email.html", email_unique_id= email_unique_id, data=data)



@app.route('/confirm_email/<id>/<admin_email>', methods = ['GET', 'POST'])
@login_required
def confirm_email_page(id, admin_email):
    link_record = SingleUseLink.query.filter_by(email_unique_id=id, user_email = admin_email).first_or_404()
    if link_record.is_used==True:
            return render_template('used_link.html')
    else:
        if request.method == 'POST':
            first_user_id =0
            username = current_user.username
            confirm_logs = Logs.query.filter_by(email_unique_id=id).first_or_404()

            is_button_clicked = request.form.get('submit_button')
            if is_button_clicked == "confirm":
                link_record.is_used = True
                db.session.commit()
                if confirm_logs.confirmation_one is None:
                    first_user_id = current_user.id
                    confirm_logs.confirmation_one=username
                    db.session.commit()
                elif confirm_logs.confirmation_one is not None and first_user_id != current_user.id:
                    confirm_logs.confirmation_two=username
                    db.session.commit()
                return render_template('confirmation_page.html')
             #return render_template('confirmation_email.html', token = token)
        
        
    return render_template('confirmation_email.html', id = id, admin_email = admin_email)
    
    

    

@app.route('/email')
def email():
    return render_template('Frontend.html', data = {})

@app.route('/confirm', methods=['POST'])
def confirm_page():
    return render_template('confirmation_page.html')


    
    
    #return render_template('confirmation_email.html')
counter = 0

@db.event.listens_for(Logs, 'before_update')
def event_listener(mapper, connection, target):
    state=db.inspect(target)
    confirm_one = state.attrs.confirmation_one.history.has_changes()
    confirm_two = state.attrs.confirmation_two.history.has_changes()
    submitted = state.attrs.submitted.history.has_changes()
    if confirm_one:
        global counter
        counter +=1
        print('confirmation with first person')
        socketio.emit('confirmation_channel', {'amount': counter})
    elif confirm_two:
        counter+=1
        print('confirmation with second person')
        socketio.emit('button_enabled', {'status':'True'})
        socketio.emit('confirmation_channel', {'amount': counter})
    if submitted:
        counter = 0



    

def add_users(username, password, admin):
    new_user = Users(username = username, password =password, admin = admin)
    db.session.add(new_user)
    db.session.commit()

def delete_users(id):
    user_delete = Users.query.get(id)
    db.session.delete(user_delete)
    db.session.commit()

@app.route('/admin_page', methods=['GET','POST'])  
def admin_page():
    form_category = request.form.get('user_form_type')
    if form_category == 'add_user':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = request.form.get('admin')
        if admin =="on":
            admin_status = True
        else:
            admin_status=False
        add_users(username, password, admin_status)
    elif form_category == "delete_user":
        id = request.form.get('user_id')
        delete_users(id)
    users_table = Users.query.all()
    return render_template('admin_page.html', users_table=users_table)



@app.route('/pending')
def pending():
    
    return render_template(f'partials/{pending}.html')

'''@app.route('/csv')
def download_csv():
    return send_file('Emails_Outputted.csv', as_attachment=True)'''


if __name__ == '__main__':
    initialize_database()
    socketio.run(app, debug=True)
    #app.run(port=5000)
