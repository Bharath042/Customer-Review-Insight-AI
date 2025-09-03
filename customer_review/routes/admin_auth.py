from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from models import Admin

admin_auth_bp = Blueprint('admin_auth', __name__)

@admin_auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # --- Enhanced Form Validation ---
        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for('admin_auth.admin_login'))

        # Query the Admin table by username
        admin = Admin.query.filter_by(admin_username=username).first()

        # Validate credentials
        if not admin or not check_password_hash(admin.password, password):
            flash("Invalid username or password.", "danger")
            return redirect(url_for('admin_auth.admin_login'))

        session['admin_id'] = admin.id
        flash("Admin login successful!", "success")
        return redirect(url_for('admin_dashboard.dashboard'))

    return render_template('admin_login.html')