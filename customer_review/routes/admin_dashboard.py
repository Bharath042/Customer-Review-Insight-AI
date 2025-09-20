# routes/admin_dashboard.py

from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from models import db, User, RawText, Admin, AspectSentiment
from werkzeug.security import check_password_hash
import functools
from nlp_processor import nlp_processor
from sqlalchemy import func # IMPORTANT: Ensure this import is present

admin_dashboard_bp = Blueprint('admin_dashboard', __name__)

# Admin login required decorator
def admin_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "admin_id" not in session:
            flash("Please log in as an administrator to access this page.", "warning")
            return redirect(url_for("admin_dashboard.admin_login"))
        return view(**kwargs)
    return wrapped_view

@admin_dashboard_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(admin_username=username).first()

        if admin and check_password_hash(admin.password, password):
            session['admin_id'] = admin.id
            flash("Logged in successfully as Admin!", "success")
            return redirect(url_for('admin_dashboard.admin_home'))
        else:
            flash("Invalid username or password", "danger")
    return render_template('admin_login.html')

@admin_dashboard_bp.route('/admin/logout')
@admin_login_required
def admin_logout():
    session.pop('admin_id', None)
    flash("You have been logged out as Admin.", "info")
    return redirect(url_for('admin_dashboard.admin_login'))

@admin_dashboard_bp.route('/admin')
@admin_login_required
def admin_home():
    # Initialize a dictionary to hold all dashboard statistics
    stats = {}
    chart_data = {'positive': 0, 'negative': 0, 'neutral': 0} # Initialize for safety

    # 1. Total Users and Reviews
    stats['total_users'] = User.query.count()
    stats['total_reviews'] = RawText.query.count()

    # 2. Sentiment Distribution and Percentages
    if stats['total_reviews'] > 0:
        sentiment_counts = db.session.query(
            RawText.sentiment,
            func.count(RawText.id)
        ).group_by(RawText.sentiment).all()

        total_analyzed_reviews = sum(count for sentiment, count in sentiment_counts)

        # Ensure all sentiment types are covered, even if count is 0
        sentiment_dict = {s.lower(): 0 for s in ['POSITIVE', 'NEGATIVE', 'NEUTRAL']}
        for sentiment, count in sentiment_counts:
            sentiment_dict[sentiment.lower()] = count
        
        for key, count in sentiment_dict.items():
            chart_data[key] = count
            stats[f'{key}_percentage'] = round((count / total_analyzed_reviews) * 100, 2)
    else:
        # If no reviews, all percentages are 0
        stats['positive_percentage'] = 0
        stats['negative_percentage'] = 0
        stats['neutral_percentage'] = 0
        # chart_data already initialized to 0s

    # 3. Recent Reviews (e.g., last 5, ordered by timestamp)
    # Use 'options(db.joinedload(RawText.user))' if you need User details in recent_reviews_for_template
    recent_reviews = RawText.query.order_by(RawText.timestamp.desc()).limit(5).all()
    
    recent_reviews_for_template = []
    for review in recent_reviews:
        # Assuming review.sentiment_label might be a property or a direct attribute
        sentiment_label = review.sentiment if hasattr(review, 'sentiment') else 'UNKNOWN'
        
        recent_reviews_for_template.append({
            'user_id': review.user_id,
            'content': review.content,
            'sentiment_label': sentiment_label,
            'timestamp': review.timestamp.strftime('%Y-%m-%d %H:%M') if review.timestamp else 'N/A' # Format timestamp
        })


    # Render the template, passing all required data
    return render_template(
        'admin_home.html',
        stats=stats,
        recent_reviews=recent_reviews_for_template,
        chart_data=chart_data
    )

@admin_dashboard_bp.route('/admin/users')
@admin_login_required
def user_management():
    users = User.query.all()
    return render_template('admin_user_management.html', users=users)

@admin_dashboard_bp.route('/admin/analysis')
@admin_login_required
def analysis_page():
    # Get filter and sort parameters from the request
    current_filter = request.args.get('sentiment', 'all').lower()
    current_sort = request.args.get('sort', 'confidence').lower()

    query = RawText.query.join(User).options(db.joinedload(RawText.aspect_sentiments)) # Eager load aspects

    # Apply sentiment filter
    if current_filter != 'all':
        query = query.filter(RawText.sentiment == current_filter.upper())

    # Apply sorting
    if current_sort == 'confidence':
        query = query.order_by(RawText.score.desc())
    elif current_sort == 'sentiment':
        query = query.order_by(RawText.sentiment.asc()) # Alphabetical for POSITIVE, NEGATIVE, NEUTRAL
    elif current_sort == 'userid':
        query = query.order_by(RawText.user_id.asc())
    
    reviews_from_db = query.all()

    # Prepare results for the template, including highlighting
    results = []
    for review in reviews_from_db:
        # Pass the review content and its associated aspects to the highlighting function
        highlighted_content = nlp_processor.highlight_review_aspects(review.content, review.aspect_sentiments)
        
        results.append({
            'id': review.id,
            'original': highlighted_content, # Now contains HTML for highlighting
            'user_id': review.user_id,
            'sentiment_label': review.sentiment,
            'sentiment_score': review.score
        })

    return render_template('admin_analysis.html', results=results, current_filter=current_filter, current_sort=current_sort)