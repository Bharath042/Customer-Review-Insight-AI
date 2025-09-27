# routes/admin_dashboard.py

from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from models import db, User, RawText, Admin, AspectSentiment, AspectCategory # <--- NEW IMPORT: AspectCategory
from werkzeug.security import check_password_hash
import functools
from nlp_processor import nlp_processor
from sqlalchemy import func 

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

# --- NEW ROUTES FOR ASPECT CATEGORY MANAGEMENT ---

@admin_dashboard_bp.route('/admin/aspect_categories', methods=['GET', 'POST'])
@admin_login_required
def manage_aspect_categories():
    if request.method == 'POST':
        category_name = request.form.get('name').strip()
        category_description = request.form.get('description').strip()

        if not category_name:
            flash("Category name cannot be empty.", "danger")
            return redirect(url_for('admin_dashboard.manage_aspect_categories'))

        # Check for duplicate category name
        existing_category = AspectCategory.query.filter(func.lower(AspectCategory.name) == func.lower(category_name)).first()
        if existing_category:
            flash(f"An aspect category with the name '{category_name}' already exists.", "danger")
            return redirect(url_for('admin_dashboard.manage_aspect_categories'))

        new_category = AspectCategory(name=category_name, description=category_description)
        try:
            db.session.add(new_category)
            db.session.commit()
            # After adding/modifying categories, force a re-load in the nlp_processor
            if nlp_processor.initialized:
                nlp_processor._load_aspect_categories()
            flash(f"Aspect category '{category_name}' added successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding aspect category: {e}", "danger")
        
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))
    
    # GET request: Display existing categories
    categories = AspectCategory.query.order_by(AspectCategory.name.asc()).all()
    return render_template('admin_aspect_categories.html', categories=categories)


@admin_dashboard_bp.route('/admin/aspect_categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_login_required
def edit_aspect_category(category_id):
    category = AspectCategory.query.get_or_404(category_id)

    if request.method == 'POST':
        new_name = request.form.get('name').strip()
        new_description = request.form.get('description').strip()

        if not new_name:
            flash("Category name cannot be empty.", "danger")
            return redirect(url_for('admin_dashboard.edit_aspect_category', category_id=category.id))

        # Check for duplicate name, excluding the current category being edited
        existing_category = AspectCategory.query.filter(
            func.lower(AspectCategory.name) == func.lower(new_name),
            AspectCategory.id != category_id
        ).first()

        if existing_category:
            flash(f"An aspect category with the name '{new_name}' already exists.", "danger")
            return redirect(url_for('admin_dashboard.edit_aspect_category', category_id=category.id))

        try:
            category.name = new_name
            category.description = new_description
            db.session.commit()
            # After adding/modifying categories, force a re-load in the nlp_processor
            if nlp_processor.initialized:
                nlp_processor._load_aspect_categories()
            flash(f"Aspect category '{category.name}' updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating aspect category: {e}", "danger")
        
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))

    return render_template('admin_edit_aspect_category.html', category=category)

@admin_dashboard_bp.route('/admin/aspect_categories/delete/<int:category_id>', methods=['POST'])
@admin_login_required
def delete_aspect_category(category_id):
    category = AspectCategory.query.get_or_404(category_id)
    category_name = category.name # Store name before deletion

    try:
        # When an AspectCategory is deleted, its aspect_category_id in AspectSentiment
        # will be set to NULL due to ON DELETE SET NULL constraint. No cascade delete of aspects.
        db.session.delete(category)
        db.session.commit()
        # After adding/modifying categories, force a re-load in the nlp_processor
        if nlp_processor.initialized:
            nlp_processor._load_aspect_categories()
        flash(f"Aspect category '{category_name}' deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting aspect category: {e}", "danger")
    
    return redirect(url_for('admin_dashboard.manage_aspect_categories'))