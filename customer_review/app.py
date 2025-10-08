from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages
import re
from routes.admin_auth import admin_auth_bp
from routes.admin_dashboard import admin_dashboard_bp
from werkzeug.security import generate_password_hash, check_password_hash
from nlp_processor import NLPProcessor 
from models import User, RawText, db, AspectSentiment, Admin
from flask_cors import CORS
import jwt
import datetime
import os
from dotenv import load_dotenv
from routes.analysis import analysis_bp
from sqlalchemy.orm import joinedload
import pandas as pd 
import logging 
from flask_migrate import Migrate

# Load environment variables
load_dotenv()

# Configure basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration for Flask app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or \
                           os.environ.get('FLASK_SECRET_KEY') or \
                           'your_super_secret_dev_key' 

if not app.config['SECRET_KEY']:
    logger.error("SECRET_KEY is not set. This is a security risk!")
    app.config['SECRET_KEY'] = 'a_fallback_secret_key_that_should_not_be_used_in_prod'

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
if not app.config['SQLALCHEMY_DATABASE_URI']:
    logger.error("DATABASE_URL is not set. Database connection will likely fail without a local MySQL.")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:admin%40123@localhost:3306/customer_review_db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem' 

# Initialize SQLAlchemy with the Flask app
db.init_app(app)

migrate = Migrate(app, db)

# --- DEBUGGING: Print resolved configs ---
logger.info(f"Resolved SECRET_KEY (first 5 chars): {app.config['SECRET_KEY'][:5]}...")
logger.info(f"Resolved SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
# --- END DEBUGGING ---

# --- Global placeholder for the NLPProcessor instance ---
nlp_processor_instance = None 

# Register blueprints
app.register_blueprint(admin_auth_bp)
app.register_blueprint(admin_dashboard_bp)
app.register_blueprint(analysis_bp)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper function to highlight aspects in text
def _highlight_aspects_in_text(review_content, aspect_sentiments):
    """
    Generates HTML with aspects highlighted based on their sentiment.
    This version uses a list of parts for robust HTML insertion,
    and only highlights POSITIVE and NEGATIVE aspects.
    """
    if not review_content or not aspect_sentiments:
        return review_content

    # Use the global nlp_processor_instance here
    if nlp_processor_instance is None or nlp_processor_instance.nlp is None:
        logger.warning("spaCy NLP model not initialized in _highlight_aspects_in_text. Aspect highlighting skipped.")
        return review_content

    doc = nlp_processor_instance.nlp(review_content) 

    final_highlighted_review_parts = []

    # Group aspects by the sentence they belong to
    # We'll use a more robust way to map aspects to spaCy's sentences
    # based on their character offsets.
    aspects_in_doc_sentences = {}
    for sent_idx, spacy_sent in enumerate(doc.sents):
        aspects_in_doc_sentences[sent_idx] = []
        for aspect_obj in aspect_sentiments:
            # Check if the aspect's character range falls within the spaCy sentence's range
            if spacy_sent.start_char <= aspect_obj.start_char < spacy_sent.end_char:
                aspects_in_doc_sentences[sent_idx].append(aspect_obj)

    for sent_idx, sent in enumerate(doc.sents):
        sentence_text = sent.text

        current_sentence_aspects = aspects_in_doc_sentences.get(sent_idx, [])

        # Sort aspects by their start_char within the *original review* for correct processing
        sorted_aspects = sorted(current_sentence_aspects, key=lambda a: a.start_char)

        sentence_segments = []
        last_idx = 0 

        for aspect_obj in sorted_aspects:
            # Highlight POSITIVE, NEGATIVE, and NEUTRAL aspects
            if aspect_obj.sentiment in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:

                # Calculate start_idx and end_idx relative to the current sentence
                # Subtract the sentence's start_char from the aspect's global start/end_char
                start_idx_relative = aspect_obj.start_char - sent.start_char
                end_idx_relative = aspect_obj.end_char - sent.start_char

                # Ensure indices are within the bounds of the current sentence_text
                start_idx_relative = max(0, start_idx_relative)
                end_idx_relative = min(len(sentence_text), end_idx_relative)

                if start_idx_relative >= len(sentence_text) or end_idx_relative <= last_idx:
                    # Aspect is out of bounds or already covered, skip it
                    continue

                # Add the text before the current aspect
                if start_idx_relative > last_idx:
                    sentence_segments.append(sentence_text[last_idx:start_idx_relative])

                inline_style = ""
                if aspect_obj.sentiment == "POSITIVE":
                    inline_style = "background-color: rgba(40, 167, 69, 0.2); color: #28a745; font-weight: bold;"
                elif aspect_obj.sentiment == "NEGATIVE":
                    inline_style = "background-color: rgba(220, 53, 69, 0.2); color: #dc3545; font-weight: bold;"
                elif aspect_obj.sentiment == "NEUTRAL":
                    inline_style = "background-color: rgba(108, 117, 125, 0.35); color: #adb5bd; font-weight: bold; border: 1px solid rgba(108, 117, 125, 0.4);"

                # Use the actual keyword_found from the aspect object for the span content
                highlight_span_html = f"<span class='highlight-aspect' style='{inline_style}'>{aspect_obj.keyword_found}</span>"
                sentence_segments.append(highlight_span_html)

                last_idx = end_idx_relative

        # Add any remaining text in the sentence after the last highlighted aspect
        if last_idx < len(sentence_text):
            sentence_segments.append(sentence_text[last_idx:])

        final_highlighted_review_parts.append("".join(sentence_segments))

    return "".join(final_highlighted_review_parts)


@app.route('/')
def landing_page():
    return render_template('landing_page.html')

@app.route('/register')
def register_page():
    return render_template('register.html', flashed_messages=get_flashed_messages(with_categories=True))

@app.route('/home')
def home():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user = User.query.get(session["user_id"])

    raw_texts = RawText.query.filter_by(user_id=user.id).options(db.joinedload(RawText.aspect_sentiments)).order_by(RawText.id.desc()).all()

    stats = {
        "total_reviews": len(raw_texts),
        "positive": sum(1 for r in raw_texts if r.sentiment.lower() == "positive"),
        "negative": sum(1 for r in raw_texts if r.sentiment.lower() == "negative"),
        "neutral": sum(1 for r in raw_texts if r.sentiment.lower() == "neutral"),
    }

    def pct(x): return round((x / stats["total_reviews"]) * 100, 2) if stats["total_reviews"] > 0 else 0

    stats["positive_percentage"] = pct(stats["positive"])
    stats["negative_percentage"] = pct(stats["negative"])
    stats["neutral_percentage"] = pct(stats["neutral"])

    # Calculate aspect-based summary statistics
    total_aspects = 0
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    total_confidence = 0
    confidence_count = 0
    
    for text in raw_texts:
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

    return render_template(
        "home.html",
        username=user.username,
        stats=stats,
        chart_data={
            "positive": stats["positive"],
            "negative": stats["negative"],
            "neutral": stats["neutral"],
        },
        recent_reviews=raw_texts[:5],
        total_aspects=total_aspects,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        avg_confidence=avg_confidence,
        flashed_messages=get_flashed_messages(with_categories=True)
    )

@app.route("/my_reviews", methods=["GET", "POST"])
def my_reviews():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user = User.query.get(session["user_id"])
    
    # Get all categories for the dropdown with their aspects
    from models import Category
    categories_raw = Category.query.options(db.joinedload(Category.aspects)).order_by(Category.name).all()
    
    # Convert to a format that can be JSON serialized with keywords
    categories = []
    for cat in categories_raw:
        aspects_with_keywords = []
        for asp in cat.aspects:
            keywords = [kw.keyword for kw in asp.keywords]
            aspects_with_keywords.append({
                'id': asp.id,
                'name': asp.name,
                'keywords': keywords
            })
        category_dict = {
            'id': cat.id,
            'name': cat.name,
            'aspects': aspects_with_keywords
        }
        categories.append(category_dict)
    
    logger.info(f"DEBUG: Found {len(categories)} categories for dropdown")
    for cat in categories:
        logger.info(f"  - Category: {cat['name']} (ID: {cat['id']}) with {len(cat['aspects'])} aspects")

    # Ensure NLPProcessor is initialized if it somehow wasn't (e.g. during specific requests)
    # This acts as a safeguard. The main initialization is in the app context startup.
    global nlp_processor_instance
    if nlp_processor_instance is None or not nlp_processor_instance.initialized:
        logger.warning("nlp_processor_instance not fully initialized within my_reviews. Attempting re-init.")
        # This will get the existing singleton if it was partially created, or create a new one
        nlp_processor_instance = NLPProcessor() 
        if not nlp_processor_instance.init_nlp():
            logger.error("Failed to re-initialize NLP models. Cannot process reviews.")
            flash("Error: NLP models could not be initialized. Please contact support.", "danger")
            # Consider returning early or providing a degraded experience
            raw_texts = RawText.query.filter_by(user_id=user.id).options(db.joinedload(RawText.aspect_sentiments)).order_by(RawText.id.desc()).all()
            for text in raw_texts:
                text.highlighted_content = text.content # No highlighting if NLP failed
            return render_template("my_reviews.html", raw_texts=raw_texts, categories=categories)


    if request.method == "POST":
        if "file" in request.files:
            file = request.files.get("file")
            if file and file.filename.endswith(".csv"):
                try:
                    df = pd.read_csv(file, encoding='latin1')
                    review_col = df.columns[0] # Assumes the first column contains the reviews

                    reviews_processed_count = 0
                    for review_text in df[review_col].dropna():
                        review_str = str(review_text)

                        # Process overall sentiment
                        overall_sentiment_result = nlp_processor_instance.analyze_sentiment(review_str) 
                        logger.info(f"CSV Review Overall Sentiment: {overall_sentiment_result['label']}, Score: {overall_sentiment_result['score']}")

                        new_raw_text = RawText(
                            content=review_str,
                            user_id=user.id,
                            sentiment=overall_sentiment_result["label"],
                            score=overall_sentiment_result["score"]
                        )
                        db.session.add(new_raw_text)
                        db.session.flush() # Flush to get new_raw_text.id

                        # Process aspects
                        extracted_aspects_raw = nlp_processor_instance.extract_aspects(review_str) 

                        # Store fully analyzed aspects to save to DB
                        for aspect_data_raw in extracted_aspects_raw:
                            aspect_sentiment_result = nlp_processor_instance.analyze_aspect_sentiment(
                                sentence=aspect_data_raw.get('sentence'),
                                aspect_keyword=aspect_data_raw.get('keyword_found'),
                                aspect_start=aspect_data_raw.get('start_char'),
                                aspect_end=aspect_data_raw.get('end_char')
                            )
                            
                            # Create and save AspectSentiment entry
                            new_aspect_sentiment = AspectSentiment(
                                raw_text_id=new_raw_text.id,
                                raw_extracted_aspect=aspect_data_raw['raw_extracted_aspect'],
                                keyword_found=aspect_data_raw['keyword_found'],
                                sentence=aspect_data_raw['sentence'],
                                sentiment=aspect_sentiment_result['label'],
                                score=aspect_sentiment_result['score'],
                                aspect_id=aspect_data_raw['aspect_category_id'],
                                start_char=aspect_data_raw['start_char'],
                                end_char=aspect_data_raw['end_char']
                            )
                            db.session.add(new_aspect_sentiment)
                            logger.debug(f"Created AspectSentiment for '{new_aspect_sentiment.raw_extracted_aspect}'. Aspect ID: {new_aspect_sentiment.aspect_id}, Keyword: '{new_aspect_sentiment.keyword_found}', Sentiment: {new_aspect_sentiment.sentiment}")

                        db.session.commit() # Commit changes for this review and its aspects
                        reviews_processed_count += 1

                    if reviews_processed_count > 0:
                        flash(f"{reviews_processed_count} reviews from '{file.filename}' uploaded & analyzed successfully!", "success")
                    else:
                        flash("No valid reviews found in CSV.", "warning")

                except Exception as e:
                    logger.error(f"Error processing file: {e}", exc_info=True) 
                    flash(f"Error processing file: {e}", "danger")
            else:
                flash("Please select a valid CSV file.", "danger")

        elif "raw_text" in request.form:
            raw_text_content = request.form.get("raw_text")
            if raw_text_content.strip():
                # Process overall sentiment
                overall_sentiment_result = nlp_processor_instance.analyze_sentiment(raw_text_content) 
                logger.info(f"Raw Text Overall Sentiment: {overall_sentiment_result['label']}, Score: {overall_sentiment_result['score']}")

                new_raw_text = RawText(
                    content=raw_text_content,
                    user_id=user.id,
                    sentiment=overall_sentiment_result["label"],
                    score=overall_sentiment_result["score"]
                )
                db.session.add(new_raw_text)
                db.session.flush() # Flush to get new_raw_text.id

                # Process aspects
                extracted_aspects_raw = nlp_processor_instance.extract_aspects(raw_text_content) 
                # Store fully analyzed aspects to save to DB
                for aspect_data_raw in extracted_aspects_raw:
                    aspect_sentiment_result = nlp_processor_instance.analyze_aspect_sentiment(
                        sentence=aspect_data_raw['sentence'],
                        aspect_keyword=aspect_data_raw['keyword_found'],
                        aspect_start=aspect_data_raw['start_char'],
                        aspect_end=aspect_data_raw['end_char']
                    )
                    
                    # Create and save AspectSentiment entry
                    new_aspect_sentiment = AspectSentiment(
                        raw_text_id=new_raw_text.id,
                        raw_extracted_aspect=aspect_data_raw['raw_extracted_aspect'], 
                        keyword_found=aspect_data_raw['keyword_found'],
                        sentence=aspect_data_raw['sentence'],
                        sentiment=aspect_sentiment_result['label'], 
                        score=aspect_sentiment_result['score'], 
                        aspect_id=aspect_data_raw['aspect_category_id'],
                        start_char=aspect_data_raw['start_char'],
                        end_char=aspect_data_raw['end_char']
                    )
                    db.session.add(new_aspect_sentiment)
                    logger.debug(f"Created AspectSentiment for '{new_aspect_sentiment.raw_extracted_aspect}'. Aspect ID: {new_aspect_sentiment.aspect_id}, Keyword: '{new_aspect_sentiment.keyword_found}', Sentiment: {new_aspect_sentiment.sentiment}")

                db.session.commit() # Commit changes for this review and its aspects
                flash("Raw text saved & analyzed successfully!", "success")
            else:
                flash("Please enter some text before saving.", "danger")
        return redirect(url_for("my_reviews"))

    # Build query with filters
    query = RawText.query.filter_by(user_id=user.id).options(db.joinedload(RawText.aspect_sentiments))
    
    # Apply filters from request args
    category_filter = request.args.get('category')
    sentiment_filter = request.args.get('sentiment')
    min_confidence = request.args.get('min_confidence')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sort_by = request.args.get('sort', 'date')
    
    # Category filter - filter reviews that have aspects from the selected category
    if category_filter:
        try:
            category_id = int(category_filter)
            # Get all aspect IDs for this category
            from models import Aspect
            aspect_ids = [a.id for a in Aspect.query.filter_by(category_id=category_id).all()]
            if aspect_ids:
                # Filter reviews that have at least one aspect from this category
                # AspectSentiment is already imported at top of file
                review_ids = db.session.query(AspectSentiment.raw_text_id).filter(
                    AspectSentiment.aspect_id.in_(aspect_ids)
                ).distinct().all()
                review_ids = [r[0] for r in review_ids]
                if review_ids:
                    query = query.filter(RawText.id.in_(review_ids))
                else:
                    # No reviews found for this category
                    query = query.filter(RawText.id == -1)  # Return empty result
        except ValueError:
            pass
    
    if sentiment_filter:
        query = query.filter(RawText.sentiment == sentiment_filter)
    
    if min_confidence:
        try:
            min_conf_val = float(min_confidence)
            query = query.filter(RawText.score >= min_conf_val)
        except ValueError:
            pass
    
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
    if sort_by == 'confidence':
        query = query.order_by(RawText.score.desc())
    elif sort_by == 'sentiment':
        query = query.order_by(RawText.sentiment.asc())
    else:  # date (default)
        query = query.order_by(RawText.timestamp.desc())
    
    raw_texts = query.all()

    for text in raw_texts:
        logger.info(f"\n--- Review ID: {text.id} ---")
        logger.info(f"Overall Review Content: {text.content}")
        logger.info(f"Overall Review Sentiment: {text.sentiment}, Stored Score: {text.score}")
        for aspect_obj in text.aspect_sentiments:
            logger.info(f"  Aspect: '{aspect_obj.keyword_found}' (Sentence: '{aspect_obj.sentence}') -> Sentiment: {aspect_obj.sentiment}, Score: {aspect_obj.score}")
        logger.info("--------------------")

        text.highlighted_content = _highlight_aspects_in_text(text.content, text.aspect_sentiments)

    # Calculate summary statistics
    total_aspects = 0
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    total_confidence = 0
    confidence_count = 0
    
    for text in raw_texts:
        # Count aspects
        total_aspects += len(text.aspect_sentiments)
        
        # Count sentiments from aspects
        for aspect in text.aspect_sentiments:
            if aspect.sentiment:
                sentiment_upper = aspect.sentiment.upper()
                if sentiment_upper == 'POSITIVE':
                    positive_count += 1
                elif sentiment_upper == 'NEGATIVE':
                    negative_count += 1
                else:
                    neutral_count += 1
                
                # Sum confidence scores
                if aspect.score is not None:
                    total_confidence += aspect.score
                    confidence_count += 1
    
    # Calculate average confidence
    avg_confidence = round((total_confidence / confidence_count * 100)) if confidence_count > 0 else 0

    return render_template("my_reviews.html", 
                         raw_texts=raw_texts, 
                         categories=categories,
                         total_aspects=total_aspects,
                         positive_count=positive_count,
                         negative_count=negative_count,
                         neutral_count=neutral_count,
                         avg_confidence=avg_confidence)


@app.route('/delete_raw_text/<int:text_id>', methods=['POST'])
def delete_raw_text(text_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    text_to_delete = RawText.query.get_or_404(text_id)
    if text_to_delete.user_id == session['user_id']:
        db.session.delete(text_to_delete)
        db.session.commit()
        flash("Raw text deleted successfully!", "success")
    else:
        flash("You do not have permission to delete this text.", "danger")
    return redirect(url_for('my_reviews'))

@app.route('/login-page')
def login_page():
    return render_template('login.html', flashed_messages=get_flashed_messages(with_categories=True))

@app.route('/auth/register', methods=['POST'])
def register():
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')

    if not email or not username or not password:
        flash("All fields (Email, Username, Password) are required.", "danger")
        return redirect(url_for('register_page'))

    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for('register_page'))

    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('register_page'))

    if User.query.filter_by(email=email).first():
        flash("An account with this email address already exists.", "danger")
        return redirect(url_for('register_page'))

    if User.query.filter_by(username=username).first():
        flash("This username is already taken. Please choose another.", "danger")
        return redirect(url_for('register_page'))

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(email=email, username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    flash("Registration successful! Please log in.", "success")
    return redirect(url_for('login_page'))

@app.route('/auth/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect(url_for('login_page'))

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for('login_page'))

    session['user_id'] = user.id
    session['username'] = user.username
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login_page'))

@app.cli.command("create-admin")
def create_admin():
    """Creates a new admin user."""
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")

    if Admin.query.filter_by(admin_username=username).first():
        logger.error(f"Error: Admin with username {username} already exists.")
        return

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_admin = Admin(admin_username=username, password=hashed_password)
    db.session.add(new_admin)
    db.session.commit()
    logger.info(f"Admin {username} created successfully!")


# ------------------------
# Run App
# ------------------------
with app.app_context():
    # It is crucial that 'global nlp_processor_instance' is the FIRST statement
    # if you intend to ASSIGN to it within this block.

    # db.create_all()  # Disabled to prevent schema conflicts with Alembic
    logger.info("Database tables checked/created.")

    # NOW initialize NLP models within the app context using the global instance
    nlp_processor_instance = NLPProcessor() # Get (or create if first time) the singleton
    if not nlp_processor_instance.init_nlp():
        logger.error("NLP models failed to initialize. Application may not function correctly.")
    else:
        logger.info("NLP models initialized successfully.")

# Only run app directly if this script is executed, not when imported by Gunicorn
if __name__ == '__main__':
    app.run(debug=True)