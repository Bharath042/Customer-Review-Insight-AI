from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from services.file_service import FileService
from services.text_service import TextService
from services.auth_service import AuthService
from config import Config

files_bp = Blueprint('files', __name__)
file_service = FileService(Config.UPLOAD_FOLDER)

@files_bp.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    user = AuthService.get_current_user()
    if not user:
        return redirect(url_for('auth.login_page'))
    
    success, message = file_service.delete_file(file_id, user.id)
    flash(message, "success" if success else "danger")
    
    return redirect(url_for('main.profile'))

@files_bp.route('/edit_file/<int:file_id>', methods=['POST'])
def edit_file(file_id):
    user = AuthService.get_current_user()
    if not user:
        return redirect(url_for('auth.login_page'))
    
    new_name = request.form.get('new_name')
    success, message = file_service.edit_file(file_id, new_name, user.id)
    flash(message, "success" if success else "danger")
    
    return redirect(url_for('main.profile'))

@files_bp.route('/delete_raw_text/<int:text_id>', methods=['POST'])
def delete_raw_text(text_id):
    user = AuthService.get_current_user()
    if not user:
        return redirect(url_for('auth.login_page'))
    
    success, message = TextService.delete_raw_text(text_id, user.id)
    flash(message, "success" if success else "danger")
    
    return redirect(url_for('main.profile'))

@files_bp.route('/edit_raw_text/<int:text_id>', methods=['GET', 'POST'])
def edit_raw_text(text_id):
    user = AuthService.get_current_user()
    if not user:
        return redirect(url_for('auth.login_page'))
    
    if request.method == 'POST':
        new_content = request.form['content']
        success, message = TextService.edit_raw_text(text_id, new_content, user.id)
        flash(message, "success" if success else "danger")
        
        if success:
            return redirect(url_for('main.profile'))
    
    text = TextService.get_raw_text(text_id, user.id)
    if not text:
        flash("Text not found.", "danger")
        return redirect(url_for('main.profile'))
    
    return render_template('edit_raw_text.html', text=text)
