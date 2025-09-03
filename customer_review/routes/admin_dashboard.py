from flask import Blueprint, render_template, redirect, url_for, session, flash
from functools import wraps
from models import User, UploadedFile, RawText

# Create a Blueprint for the admin dashboard
admin_dashboard_bp = Blueprint('admin_dashboard', __name__)

# --- Admin Security Decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("You must be logged in as an admin to view this page.", "danger")
            return redirect(url_for('admin_auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Admin Routes ---
@admin_dashboard_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    # Fetch all users from the database
    all_users = User.query.all()
    return render_template('admin_dashboard.html', users=all_users)

@admin_dashboard_bp.route('/admin/logout')
def admin_logout():
    # Clear only the admin session key
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('landing_page'))