from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login-page')
def login_page():
    return render_template('login.html')

@auth_bp.route('/auth/register', methods=['POST'])
def register():
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')
    
    success, message = AuthService.register_user(email, username, password)
    flash(message, "success" if success else "danger")
    
    if success:
        return redirect(url_for('auth.login_page'))
    else:
        return redirect(url_for('main.register_page'))

@auth_bp.route('/auth/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    success, message, user = AuthService.login_user(email, password)
    
    if success:
        return redirect(url_for('main.home'))
    else:
        flash(message, "danger")
        return redirect(url_for('auth.login_page'))

@auth_bp.route('/logout')
def logout():
    AuthService.logout_user()
    return redirect(url_for('auth.login_page'))
