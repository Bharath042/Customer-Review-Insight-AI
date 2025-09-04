from flask import Flask, render_template, request, redirect, url_for, flash, session
import re
from routes.admin_auth import admin_auth_bp
from routes.admin_dashboard import admin_dashboard_bp 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import jwt
import datetime
import os
from dotenv import load_dotenv

# Import the db object and all models from the new models.py file
from models import db, User, UploadedFile, RawText, Admin

# Load environment variables
load_dotenv()

# ------------------------
# Flask app setup
# ------------------------
app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+pymysql://username:password@localhost:3306/db_name')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize the database with the app
db.init_app(app)

# Create all database tables
with app.app_context():
    db.create_all()

# Register the blueprint with the app
app.register_blueprint(admin_auth_bp)
app.register_blueprint(admin_dashboard_bp)

# ------------------------
# File Uploads
# ------------------------
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------------
# Routes
# ------------------------
@app.route('/')
def landing_page():
    return render_template('landing_page.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user = User.query.get(session['user_id'])
    username = user.username

    user_folder = os.path.join(UPLOAD_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)

    # ✅ Get uploaded files from DB
    uploaded_files = UploadedFile.query.filter_by(user_id=user.id).all()

    if request.method == 'POST':
        # If CSV file uploaded
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename.endswith('.csv'):
                file_path = os.path.join(user_folder, file.filename)
                file.save(file_path)

                # ✅ Save metadata in DB
                new_file = UploadedFile(filename=file.filename, user_id=user.id)
                db.session.add(new_file)
                db.session.commit()

                flash("CSV uploaded successfully!", "success")
            else:
                flash("Only CSV files are allowed.", "danger")

        # If raw text pasted
        elif 'raw_text' in request.form:
            raw_text = request.form['raw_text']
            if raw_text.strip():
                # ✅ Save raw text in DB
                new_text = RawText(content=raw_text, user_id=user.id)
                db.session.add(new_text)
                db.session.commit()

                flash("Raw text saved successfully!", "success")
            else:
                flash("Please enter some text before saving.", "danger")

        return redirect(url_for('home'))

    return render_template(
        'home.html',
        username=username,
        files=[f.filename for f in uploaded_files]
    )
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user = User.query.get(session['user_id'])
    files = UploadedFile.query.filter_by(user_id=user.id).all()
    raw_texts = RawText.query.filter_by(user_id=user.id).all()

    return render_template("profile.html", 
                           files=files, 
                           raw_texts=raw_texts,
                           username=user.username)

# Delete file
@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    file = UploadedFile.query.get(file_id)
    if file and file.user_id == session['user_id']:
        db.session.delete(file)
        db.session.commit()
        flash("File deleted successfully!", "success")

    return redirect(url_for('profile'))
@app.route('/delete_raw_text/<int:text_id>', methods=['POST'])
def delete_raw_text(text_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    text = RawText.query.get(text_id)
    if text and text.user_id == session['user_id']:
        db.session.delete(text)
        db.session.commit()
        flash("Raw text deleted successfully!", "success")

    return redirect(url_for('profile'))
@app.route('/edit_raw_text/<int:text_id>', methods=['GET', 'POST'])
def edit_raw_text(text_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    text = RawText.query.get_or_404(text_id)
    if text.user_id != session['user_id']:
        flash("You do not have permission to edit this.", "danger")
        return redirect(url_for('profile'))

    if request.method == 'POST':
        new_content = request.form['content']
        text.content = new_content
        db.session.commit()
        flash("Raw text updated successfully!", "success")
        return redirect(url_for('profile'))

    return render_template('edit_raw_text.html', text=text)


# Edit (Rename) file
@app.route('/edit_file/<int:file_id>', methods=['POST'])
def edit_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    new_name = request.form.get('new_name')
    file = UploadedFile.query.get(file_id)

    if file and file.user_id == session['user_id'] and new_name.strip():
        # You should also rename the actual file on the filesystem here
        # os.rename(...)
        file.filename = new_name
        db.session.commit()
        flash("File renamed successfully!", "success")
    else:
        flash("Invalid filename or permission denied!", "danger")

    return redirect(url_for('profile'))

@app.route('/login-page')
def login_page():
    return render_template('login.html')

@app.route('/auth/register', methods=['POST'])
def register():
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')

    if not email or not username or not password:
        flash("All fields (Email, Username, Password) are required.", "danger")
        return redirect(url_for('register_page'))
    
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for('register_page'))

    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('register_page'))

    if User.query.filter_by(email=email).first():
        flash("An account with this email address already exists.", "danger")
        return redirect(url_for('register_page'))

    if User.query.filter_by(username=username).first():
        flash("This username is already taken. Please choose another.", "danger")
        return redirect(url_for('register_page'))

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(email=email, username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    flash("Registration successful! Please log in.", "success")
    return redirect(url_for('login_page'))

@app.route('/auth/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect(url_for('login_page'))

    user = User.query.filter_by(email=email).first()
    
    if not user or not check_password_hash(user.password, password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for('login_page'))

    session['user_id'] = user.id
    session['username'] = user.username

    token = jwt.encode(
        {'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
        app.config['SECRET_KEY'],
        algorithm='HS256'
    )

    return redirect(url_for('home'))

@app.route('/logout')  # <-- DECORATOR WAS MISSING HERE
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login_page'))

# ------------------------
# Admin Creation Command
# ------------------------
@app.cli.command("create-admin")
def create_admin():
    """Creates a new admin user."""
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")

    if Admin.query.filter_by(admin_username=username).first():
        print(f"Error: Admin with username {username} already exists.")
        return

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_admin = Admin(admin_username=username, password=hashed_password)
    db.session.add(new_admin)
    db.session.commit()
    print(f"Admin {username} created successfully!")


# ------------------------
# Run App
# ------------------------
if __name__ == '__main__':
    app.run(debug=True)