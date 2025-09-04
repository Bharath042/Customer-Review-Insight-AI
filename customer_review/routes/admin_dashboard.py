from flask import Blueprint, render_template, redirect, url_for, session, flash
from functools import wraps
from models import User, RawText, db
from nlp_processor import clean_text, analyze_sentiment

admin_dashboard_bp = Blueprint('admin_dashboard', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("You must be logged in as an admin to view this page.", "danger")
            return redirect(url_for('admin_auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_dashboard_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    all_users = User.query.all()
    return render_template('admin_dashboard.html', users=all_users)

@admin_dashboard_bp.route('/admin/analysis')
@admin_required
def analysis_page():
    all_reviews = RawText.query.all()
    results = []
    for review in all_reviews:
        cleaned = clean_text(review.content)
        sentiment = analyze_sentiment(cleaned)
        confidence_percentage = int(sentiment['score'] * 100)
        results.append({
            'original': review.content,
            'user_id': review.user_id,
            'sentiment_label': sentiment['label'].upper(),
            'confidence': confidence_percentage
        })
    return render_template('admin_analysis.html', results=results)

@admin_dashboard_bp.route('/admin/logout')
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('landing_page'))
