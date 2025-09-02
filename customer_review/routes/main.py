from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from services.auth_service import AuthService
from services.file_service import FileService
from services.text_service import TextService
from config import Config

main_bp = Blueprint('main', __name__)
file_service = FileService(Config.UPLOAD_FOLDER)

@main_bp.route('/')
def register_page():
    return render_template('register.html')

@main_bp.route('/home', methods=['GET', 'POST'])
def home():
    user = AuthService.get_current_user()
    if not user:
        return redirect(url_for('auth.login_page'))
    
    if request.method == 'POST':
        # Handle CSV file upload
        if 'file' in request.files:
            file = request.files['file']
            success, message = file_service.upload_csv_file(file, user.id, user.username)
            flash(message, "success" if success else "danger")
        
        # Handle raw text input
        elif 'raw_text' in request.form:
            raw_text = request.form['raw_text']
            success, message = TextService.save_raw_text(raw_text, user.id)
            flash(message, "success" if success else "danger")
        
        return redirect(url_for('main.home'))
    
    # Get user's uploaded files
    uploaded_files = file_service.get_user_files(user.id)
    
    return render_template(
        'home.html',
        username=user.username,
        files=[f.filename for f in uploaded_files]
    )

@main_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user = AuthService.get_current_user()
    if not user:
        return redirect(url_for('auth.login_page'))
    
    files = file_service.get_user_files(user.id)
    raw_texts = TextService.get_user_texts(user.id)
    
    return render_template("profile.html", 
                         files=files, 
                         raw_texts=raw_texts,
                         username=user.username)
