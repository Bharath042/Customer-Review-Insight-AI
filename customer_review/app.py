from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages
import re
from nlp_processor import clean_text
from routes.admin_auth import admin_auth_bp
from routes.admin_dashboard import admin_dashboard_bp 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import jwt
import datetime
import os
from dotenv import load_dotenv
from routes.analysis import analysis_bp
import pandas as pd

from models import db, User, UploadedFile, RawText, Admin

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+pymysql://username:password@localhost:3306/db_name')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'

db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(admin_auth_bp)
app.register_blueprint(admin_dashboard_bp)
app.register_blueprint(analysis_bp)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def landing_page():
    return render_template('landing_page.html')

@app.route('/register')
def register_page():
    return render_template('register.html', flashed_messages=get_flashed_messages(with_categories=True))

from nlp_processor import analyze_sentiment  # make sure this is imported at the top

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        # --- Handle File Upload ---
        if 'file' in request.files:
            file = request.files.get('file')
            
            if file and file.filename != '' and file.filename.endswith('.csv'):
                try:
                    df = pd.read_csv(file)
                    
                    if 'review_text' in df.columns:
                        reviews_to_add = []
                        for review_text in df['review_text'].dropna():
                            sentiment_result = analyze_sentiment(str(review_text))
                            new_text = RawText(
                                content=str(review_text),
                                user_id=user.id,
                                sentiment=sentiment_result['label'],
                                score=sentiment_result['score']
                            )
                            reviews_to_add.append(new_text)
                        
                        db.session.bulk_save_objects(reviews_to_add)
                        db.session.commit()
                        flash(f"{len(reviews_to_add)} reviews from '{file.filename}' uploaded & analyzed successfully!", "success")
                    else:
                        flash("CSV must contain a column named 'review_text'.", "danger")

                except Exception as e:
                    flash(f"Error processing file: {e}", "danger")
            else:
                flash("Please select a valid CSV file.", "danger")

        # --- Handle Raw Text ---
        elif 'raw_text' in request.form:
            raw_text = request.form.get('raw_text')
            if raw_text and raw_text.strip():
                sentiment_result = analyze_sentiment(raw_text)
                new_text = RawText(
                    content=raw_text,
                    user_id=user.id,
                    sentiment=sentiment_result['label'],
                    score=sentiment_result['score']
                )
                db.session.add(new_text)
                db.session.commit()
                flash("Raw text saved & analyzed successfully!", "success")
            else:
                flash("Please enter some text before saving.", "danger")
        
        return redirect(url_for('home'))

    # --- For GET Request ---
    raw_texts = RawText.query.filter_by(user_id=user.id).order_by(RawText.id.desc()).all()

    return render_template(
        'home.html',
        username=user.username,
        raw_texts=raw_texts,
        flashed_messages=get_flashed_messages(with_categories=True)
    )


@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    file_to_delete = UploadedFile.query.get_or_404(file_id)
    if file_to_delete.user_id == session['user_id']:
        db.session.delete(file_to_delete)
        db.session.commit()
        flash("File deleted successfully!", "success")
    else:
        flash("You do not have permission to delete this file.", "danger")
    return redirect(url_for('home'))

@app.route('/delete_raw_text/<int:text_id>', methods=['POST'])
def delete_raw_text(text_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    text_to_delete = RawText.query.get_or_404(text_id)
    if text_to_delete.user_id == session['user_id']:
        db.session.delete(text_to_delete)
        db.session.commit()
        flash("Raw text deleted successfully!", "success")
    else:
        flash("You do not have permission to delete this text.", "danger")
    return redirect(url_for('home'))

@app.route('/login-page')
def login_page():
    return render_template('login.html', flashed_messages=get_flashed_messages(with_categories=True))

@app.route('/auth/register', methods=['POST'])
def register():
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')

    if not email or not username or not password:
        flash("All fields (Email, Username, Password) are required.", "danger")
        return redirect(url_for('register_page'))
    
    # Using email-validator library is more robust, but regex is here as requested
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
    return redirect(url_for('home'))

@app.route('/logout')
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

    # CORRECTED: Check for admin by admin_username, not email
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