
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from models import db, User, RawText, Admin, AspectSentiment, Category, Aspect
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

# Route to add a new aspect to a category
@admin_dashboard_bp.route('/admin/categories/<int:category_id>/add_aspect', methods=['POST'])
@admin_login_required
def add_aspect_to_category(category_id):
    from models import Aspect, AspectKeyword, Category
    category = Category.query.get_or_404(category_id)
    aspect_name = request.form.get('aspect_name', '').strip()
    aspect_description = request.form.get('aspect_description', '').strip()
    weightage = request.form.get('weightage', 1.0)
    keywords_raw = request.form.get('keywords', '').strip()
    keywords_list = [kw.strip() for kw in keywords_raw.split(',') if kw.strip()]

    if not aspect_name:
        flash('Aspect name is required.', 'danger')
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))

    try:
        aspect = Aspect(
            name=aspect_name,
            description=aspect_description,
            weightage=float(weightage),
            category_id=category.id
        )
        db.session.add(aspect)
        db.session.flush()  # Get aspect.id before adding keywords
        for kw in keywords_list:
            db.session.add(AspectKeyword(keyword=kw, aspect_id=aspect.id))
        db.session.commit()
        flash(f"Aspect '{aspect_name}' added to category '{category.name}'.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding aspect: {e}", 'danger')
    return redirect(url_for('admin_dashboard.manage_aspect_categories'))

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

    # 4. Calculate aspect-based summary statistics (same as user dashboard)
    all_reviews_with_aspects = RawText.query.options(db.joinedload(RawText.aspect_sentiments)).all()
    
    total_aspects = 0
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    total_confidence = 0
    confidence_count = 0
    
    for text in all_reviews_with_aspects:
        total_aspects += len(text.aspect_sentiments)
        for aspect in text.aspect_sentiments:
            if aspect.sentiment:
                sentiment_upper = aspect.sentiment.upper()
                if sentiment_upper == 'POSITIVE':
                    positive_count += 1
                elif sentiment_upper == 'NEGATIVE':
                    negative_count += 1
                else:
                    neutral_count += 1
                
                if aspect.score is not None:
                    total_confidence += aspect.score
                    confidence_count += 1
    
    avg_confidence = round((total_confidence / confidence_count * 100)) if confidence_count > 0 else 0

    # Render the template, passing all required data
    return render_template(
        'admin_home.html',
        stats=stats,
        recent_reviews=recent_reviews_for_template,
        chart_data=chart_data,
        total_aspects=total_aspects,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        avg_confidence=avg_confidence
    )

@admin_dashboard_bp.route('/admin/users')
@admin_login_required
def user_management():
    # Get all users with their review statistics
    users = User.query.all()
    
    # Calculate statistics for each user
    users_with_stats = []
    for user in users:
        # Get all reviews for this user
        user_reviews = RawText.query.filter_by(user_id=user.id).all()
        
        # Calculate sentiment counts
        positive_count = sum(1 for r in user_reviews if r.sentiment and r.sentiment.lower() == 'positive')
        negative_count = sum(1 for r in user_reviews if r.sentiment and r.sentiment.lower() == 'negative')
        neutral_count = sum(1 for r in user_reviews if r.sentiment and r.sentiment.lower() == 'neutral')
        
        # Calculate average confidence and aspect statistics
        total_confidence = 0
        confidence_count = 0
        total_aspects = 0
        positive_aspects = 0
        negative_aspects = 0
        
        for review in user_reviews:
            total_aspects += len(review.aspect_sentiments)
            for aspect in review.aspect_sentiments:
                if aspect.score is not None:
                    total_confidence += aspect.score
                    confidence_count += 1
                
                # Count aspect sentiments
                if aspect.sentiment:
                    sentiment_upper = aspect.sentiment.upper()
                    if sentiment_upper == 'POSITIVE':
                        positive_aspects += 1
                    elif sentiment_upper == 'NEGATIVE':
                        negative_aspects += 1
        
        avg_confidence = round((total_confidence / confidence_count * 100)) if confidence_count > 0 else 0
        aspect_confidence = avg_confidence  # Same as overall confidence for aspects
        
        users_with_stats.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'created_at': None,  # User model doesn't have created_at field
            'review_count': len(user_reviews),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'avg_confidence': avg_confidence,
            'total_aspects': total_aspects,
            'positive_aspects': positive_aspects,
            'negative_aspects': negative_aspects,
            'aspect_confidence': aspect_confidence
        })
    
    return render_template('admin_user_management.html', users=users_with_stats)

@admin_dashboard_bp.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_login_required
def delete_user(user_id):
    from flask import flash, redirect, url_for
    
    user = User.query.get_or_404(user_id)
    username = user.username
    
    try:
        # Delete all reviews and associated data for this user
        # The cascade delete should handle aspect_sentiments automatically
        RawText.query.filter_by(user_id=user_id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User "{username}" and all their reviews have been successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard.user_management'))

@admin_dashboard_bp.route('/admin/analysis')
@admin_login_required
def analysis_page():
    # Get filter and sort parameters from the request
    current_filter = request.args.get('sentiment', 'all').lower()
    current_sort = request.args.get('sort', 'confidence').lower()
    min_confidence = request.args.get('min_confidence')
    user_id_filter = request.args.get('user_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = RawText.query.join(User).options(db.joinedload(RawText.aspect_sentiments)) # Eager load aspects

    # Apply sentiment filter
    if current_filter != 'all':
        query = query.filter(RawText.sentiment == current_filter.upper())
    
    # Apply confidence filter
    if min_confidence:
        try:
            min_conf_val = float(min_confidence)
            query = query.filter(RawText.score >= min_conf_val)
        except ValueError:
            pass
    
    # Apply user ID filter
    if user_id_filter:
        try:
            user_id_val = int(user_id_filter)
            query = query.filter(RawText.user_id == user_id_val)
        except ValueError:
            pass
    
    # Apply date filters
    if start_date:
        try:
            from datetime import datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RawText.timestamp >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            from datetime import datetime, timedelta
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RawText.timestamp < end_dt)
        except ValueError:
            pass

    # Apply sorting
    if current_sort == 'confidence':
        query = query.order_by(RawText.score.desc())
    elif current_sort == 'sentiment':
        query = query.order_by(RawText.sentiment.asc()) # Alphabetical for POSITIVE, NEGATIVE, NEUTRAL
    elif current_sort == 'userid':
        query = query.order_by(RawText.user_id.asc())
    elif current_sort == 'date':
        query = query.order_by(RawText.timestamp.desc())
    
    reviews_from_db = query.all()

    print(f"DEBUG: Number of reviews fetched: {len(reviews_from_db)}")
    if reviews_from_db:
        print(f"DEBUG: First review: id={reviews_from_db[0].id}, user_id={reviews_from_db[0].user_id}, content={reviews_from_db[0].content}")

    # Prepare results for the template, including highlighting
    results = []
    for review in reviews_from_db:
        try:
            highlighted_content = nlp_processor.highlight_review_aspects(review.content, review.aspect_sentiments)
            if not highlighted_content:
                highlighted_content = review.content
        except Exception:
            highlighted_content = review.content
        results.append({
            'id': review.id,
            'original': highlighted_content,
            'user_id': review.user_id,
            'sentiment_label': review.sentiment if review.sentiment else 'N/A',
            'sentiment_score': review.score if review.score is not None else 'N/A'
        })

    # Ensure aspect summary variables are always defined for the template
    categorized_aspect_summary = []
    uncategorized_aspect_summary = []
    return render_template(
        'admin_analysis.html',
        results=results,
        current_filter=current_filter,
        current_sort=current_sort,
        categorized_aspect_summary=categorized_aspect_summary,
        uncategorized_aspect_summary=uncategorized_aspect_summary
    )

# --- NEW ROUTES FOR ASPECT CATEGORY MANAGEMENT ---

@admin_dashboard_bp.route('/admin/aspect_categories', methods=['GET', 'POST'])
@admin_login_required
def manage_aspect_categories():
    if request.method == 'POST':
        from models import AspectKeyword
        
        category_name = request.form.get('category_name', '').strip()
        category_description = request.form.get('category_description', '').strip()

        if not category_name:
            flash("Category name cannot be empty.", "danger")
            return redirect(url_for('admin_dashboard.manage_aspect_categories'))

        # Check for duplicate category name
        existing_category = Category.query.filter(func.lower(Category.name) == func.lower(category_name)).first()
        if existing_category:
            flash(f"A category with the name '{category_name}' already exists.", "danger")
            return redirect(url_for('admin_dashboard.manage_aspect_categories'))

        # Create new category
        new_category = Category(name=category_name, description=category_description)
        
        try:
            db.session.add(new_category)
            db.session.flush()  # Get new_category.id before adding aspects
            
            # Process aspects from form data
            # Form sends: aspects[0][name], aspects[0][description], aspects[0][weightage], aspects[0][keywords]
            aspects_count = 0
            aspect_index = 0
            
            while True:
                aspect_name_key = f'aspects[{aspect_index}][name]'
                if aspect_name_key not in request.form:
                    break
                
                aspect_name = request.form.get(aspect_name_key, '').strip()
                aspect_description = request.form.get(f'aspects[{aspect_index}][description]', '').strip()
                aspect_weightage = request.form.get(f'aspects[{aspect_index}][weightage]', '3')
                aspect_keywords_raw = request.form.get(f'aspects[{aspect_index}][keywords]', '').strip()
                
                if aspect_name:  # Only create aspect if name is provided
                    try:
                        weightage_float = float(aspect_weightage)
                    except ValueError:
                        weightage_float = 3.0
                    
                    new_aspect = Aspect(
                        name=aspect_name,
                        description=aspect_description,
                        weightage=weightage_float,
                        category_id=new_category.id
                    )
                    db.session.add(new_aspect)
                    db.session.flush()  # Get aspect.id for keywords
                    
                    # Add keywords for this aspect
                    if aspect_keywords_raw:
                        keywords_list = [kw.strip() for kw in aspect_keywords_raw.split(',') if kw.strip()]
                        for keyword in keywords_list:
                            new_keyword = AspectKeyword(keyword=keyword, aspect_id=new_aspect.id)
                            db.session.add(new_keyword)
                    
                    aspects_count += 1
                
                aspect_index += 1
            
            db.session.commit()
            
            # Reload NLP processor categories
            if nlp_processor.initialized:
                nlp_processor._load_aspect_categories()
            
            if aspects_count > 0:
                flash(f"Category '{category_name}' created with {aspects_count} aspect(s)!", "success")
            else:
                flash(f"Category '{category_name}' created (no aspects added).", "success")
                
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding category: {e}", "danger")
        
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))
    
    # GET request: Display existing categories with aspects
    categories = Category.query.options(db.joinedload(Category.aspects).joinedload(Aspect.keywords)).order_by(Category.name.asc()).all()
    return render_template('admin_aspect_categories.html', categories=categories)


@admin_dashboard_bp.route('/admin/aspect_categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_login_required
def edit_aspect_category(category_id):
    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        new_name = request.form.get('name').strip()
        new_description = request.form.get('description').strip()
        keywords_raw = request.form.get('keywords', '').strip()
        keywords_list = [kw.strip() for kw in keywords_raw.split(',') if kw.strip()]

        if not new_name:
            flash("Category name cannot be empty.", "danger")
            return redirect(url_for('admin_dashboard.edit_aspect_category', category_id=category.id))

        # Check for duplicate name, excluding the current category being edited
        existing_category = Category.query.filter(
            func.lower(Category.name) == func.lower(new_name),
            Category.id != category_id
        ).first()

        if existing_category:
            flash(f"An aspect category with the name '{new_name}' already exists.", "danger")
            return redirect(url_for('admin_dashboard.edit_aspect_category', category_id=category.id))

        try:
            category.name = new_name
            category.description = new_description
            # Update keywords: remove old, add new
            # Aspects and keywords will be updated in a separate step/UI
            db.session.commit()
            # After adding/modifying categories, force a re-load in the nlp_processor
            if nlp_processor.initialized:
                nlp_processor._load_aspect_categories()
            flash(f"Aspect category '{category.name}' updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating aspect category: {e}", "danger")
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))

    # Pass keywords to template
    return render_template('admin_edit_aspect_category.html', category=category)

@admin_dashboard_bp.route('/admin/aspect_categories/delete/<int:category_id>', methods=['POST'])
@admin_login_required
def delete_aspect_category(category_id):
    category = Category.query.get_or_404(category_id)
    category_name = category.name # Store name before deletion

    try:
        # When a Category is deleted, its aspects and related data will be handled by cascade rules.
        db.session.delete(category)
        db.session.commit()
        # After adding/modifying categories, force a re-load in the nlp_processor
        if nlp_processor.initialized:
            nlp_processor._load_aspect_categories()
        flash(f"Category '{category_name}' deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting category: {e}", "danger")
    
    return redirect(url_for('admin_dashboard.manage_aspect_categories'))

@admin_dashboard_bp.route('/admin/aspect/<int:aspect_id>/edit', methods=['POST'])
@admin_login_required
def edit_aspect(aspect_id):
    """Edit an existing aspect"""
    aspect = Aspect.query.get_or_404(aspect_id)
    
    aspect_name = request.form.get('aspect_name', '').strip()
    aspect_description = request.form.get('aspect_description', '').strip()
    weightage = request.form.get('weightage', '3')
    keywords_raw = request.form.get('keywords', '').strip()
    
    if not aspect_name:
        flash("Aspect name cannot be empty.", "danger")
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))
    
    try:
        weightage_float = float(weightage)
    except ValueError:
        weightage_float = 3.0
    
    try:
        aspect.name = aspect_name
        aspect.description = aspect_description
        aspect.weightage = weightage_float
        
        # Update keywords
        from models import AspectKeyword
        # Delete old keywords
        AspectKeyword.query.filter_by(aspect_id=aspect_id).delete()
        
        # Add new keywords
        if keywords_raw:
            keywords_list = [kw.strip().lower() for kw in keywords_raw.split(',') if kw.strip()]
            for keyword in keywords_list:
                new_keyword = AspectKeyword(aspect_id=aspect.id, keyword=keyword)
                db.session.add(new_keyword)
        
        db.session.commit()
        
        # Reload NLP processor
        if nlp_processor.initialized:
            nlp_processor._load_aspect_categories()
        
        flash(f"Aspect '{aspect.name}' updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating aspect: {e}", "danger")
    
    return redirect(url_for('admin_dashboard.manage_aspect_categories'))

@admin_dashboard_bp.route('/admin/aspect/<int:aspect_id>/delete', methods=['POST'])
@admin_login_required
def delete_aspect(aspect_id):
    """Delete an aspect"""
    aspect = Aspect.query.get_or_404(aspect_id)
    aspect_name = aspect.name
    
    try:
        db.session.delete(aspect)
        db.session.commit()
        
        # Reload NLP processor
        if nlp_processor.initialized:
            nlp_processor._load_aspect_categories()
        
        flash(f"Aspect '{aspect_name}' deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting aspect: {e}", "danger")
    
    return redirect(url_for('admin_dashboard.manage_aspect_categories'))

@admin_dashboard_bp.route('/admin/category/<int:category_id>/edit', methods=['POST'])
@admin_login_required
def edit_category_ajax(category_id):
    """Edit category name and description"""
    category = Category.query.get_or_404(category_id)
    
    new_name = request.form.get('category_name', '').strip()
    new_description = request.form.get('category_description', '').strip()
    
    if not new_name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))
    
    # Check for duplicate
    from sqlalchemy import func
    existing = Category.query.filter(
        func.lower(Category.name) == func.lower(new_name),
        Category.id != category_id
    ).first()
    
    if existing:
        flash(f"Category '{new_name}' already exists.", "danger")
        return redirect(url_for('admin_dashboard.manage_aspect_categories'))
    
    try:
        category.name = new_name
        category.description = new_description
        db.session.commit()
        
        # Reload NLP processor
        if nlp_processor.initialized:
            nlp_processor._load_aspect_categories()
        
        flash(f"Category '{category.name}' updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating category: {e}", "danger")
    
    return redirect(url_for('admin_dashboard.manage_aspect_categories'))