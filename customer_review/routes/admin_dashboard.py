from flask import Blueprint, render_template, redirect, url_for, session, flash, request
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

# --- Main Admin Homepage Route ---
@admin_dashboard_bp.route('/admin/dashboard')
@admin_required
def admin_home():
    # --- Fetch all necessary data ---
    all_users = User.query.all()
    all_reviews = RawText.query.all()
    
    total_users = len(all_users)
    total_reviews_count = len(all_reviews)

    # --- Sentiment Calculation for Chart and Stats ---
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    for review in all_reviews:
        sentiment = analyze_sentiment(clean_text(review.content))
        label = sentiment['label'].upper()
        if label == 'POSITIVE':
            positive_count += 1
        elif label == 'NEGATIVE':
            negative_count += 1
        else:
            neutral_count += 1
            
    positive_percentage = int((positive_count / total_reviews_count) * 100) if total_reviews_count > 0 else 0
    negative_percentage = int((negative_count / total_reviews_count) * 100) if total_reviews_count > 0 else 0

    stats = {
        'total_users': total_users,
        'total_reviews': total_reviews_count,
        'positive_percentage': positive_percentage,
        'negative_percentage': negative_percentage
    }

    # --- Data for the donut chart ---
    chart_data = {
        'positive': positive_count,
        'negative': negative_count,
        'neutral': neutral_count
    }

    # --- Get 5 most recent reviews ---
    recent_reviews_raw = sorted(all_reviews, key=lambda r: r.id, reverse=True)[:5]
    recent_reviews_processed = []
    for review in recent_reviews_raw:
        sentiment = analyze_sentiment(clean_text(review.content))
        recent_reviews_processed.append({
            'content': review.content,
            'user_id': review.user_id,
            'sentiment_label': sentiment['label'].upper()
        })

    # --- Render the template with all the data ---
    return render_template(
        'admin_home.html', 
        stats=stats, 
        recent_reviews=recent_reviews_processed,
        chart_data=chart_data  # Now this data is being sent correctly
    )

# --- RENAMED: User Management Route ---
@admin_dashboard_bp.route('/admin/users')
@admin_required
def user_management():
    all_users = User.query.all()
    return render_template('admin_user_management.html', users=all_users)

@admin_dashboard_bp.route('/admin/analysis')
@admin_required
def analysis_page():
    # ... (This function remains the same)
    sentiment_filter = request.args.get('sentiment', 'all')
    sort_by = request.args.get('sort', 'confidence')
    all_reviews = RawText.query.all()
    results = []
    for review in all_reviews:
        cleaned = clean_text(review.content)
        sentiment = analyze_sentiment(cleaned)
        results.append({
            'original': review.content, 'user_id': review.user_id,
            'sentiment_label': sentiment['label'].upper(), 'sentiment_score': sentiment['score']
        })
    if sentiment_filter != 'all':
        results = [r for r in results if r['sentiment_label'] == sentiment_filter.upper()]
    if sort_by == 'sentiment':
        order = {'POSITIVE': 0, 'NEUTRAL': 1, 'NEGATIVE': 2}
        results.sort(key=lambda r: order.get(r['sentiment_label'], 3))
    elif sort_by == 'userid':
        results.sort(key=lambda r: r['user_id'])
    else:
        results.sort(key=lambda r: r['sentiment_score'], reverse=True)
    return render_template('admin_analysis.html', results=results, current_filter=sentiment_filter, current_sort=sort_by)

@admin_dashboard_bp.route('/admin/logout')
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('landing_page'))