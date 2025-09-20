from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages
import re
from routes.admin_auth import admin_auth_bp
from routes.admin_dashboard import admin_dashboard_bp
from werkzeug.security import generate_password_hash, check_password_hash
from nlp_processor import nlp_processor  # Correctly importing the singleton instance
from models import User, RawText, db, AspectSentiment, Admin
from flask_cors import CORS
import jwt
import datetime
import os
from dotenv import load_dotenv
from routes.analysis import analysis_bp
from sqlalchemy.orm import joinedload
import pandas as pd # Import pandas for CSV processing

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:Geethasri%402005@localhost:3306/reviewdb')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'

db.init_app(app)

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

    if nlp_processor.nlp is None:
        print("WARNING: spaCy NLP model not initialized in _highlight_aspects_in_text. Aspect highlighting skipped.")
        return review_content

    doc = nlp_processor.nlp(review_content)

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
        last_idx = 0 # This will be the index within the *current sentence_text*

        for aspect_obj in sorted_aspects:
            # Only highlight POSITIVE and NEGATIVE aspects, NOT NEUTRAL.
            if aspect_obj.sentiment == "POSITIVE" or aspect_obj.sentiment == "NEGATIVE":

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

    raw_texts = RawText.query.filter_by(user_id=user.id).order_by(RawText.id.desc()).all()

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
        flashed_messages=get_flashed_messages(with_categories=True)
    )

@app.route("/my_reviews", methods=["GET", "POST"])
def my_reviews():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user = User.query.get(session["user_id"])

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
                        overall_sentiment_result = nlp_processor.analyze_sentiment(review_str)
                        print(f"DEBUG: CSV Review Overall Sentiment: {overall_sentiment_result['label']}, Score: {overall_sentiment_result['score']}")

                        new_raw_text = RawText(
                            content=review_str,
                            user_id=user.id,
                            sentiment=overall_sentiment_result["label"],
                            score=overall_sentiment_result["score"]
                        )
                        db.session.add(new_raw_text)
                        db.session.flush() # Flush to get new_raw_text.id

                        # Process aspects
                        extracted_aspects_raw = nlp_processor.extract_aspects(review_str)

                        # Store fully analyzed aspects to save to DB
                        fully_analyzed_aspects = []
                        for aspect_data_raw in extracted_aspects_raw:
                            aspect_sentiment_result = nlp_processor.analyze_aspect_sentiment(aspect_data_raw['sentence'])
                            
                            # Add sentiment and score to the aspect_data_raw dictionary
                            aspect_data_raw['sentiment'] = aspect_sentiment_result['label']
                            aspect_data_raw['score'] = aspect_sentiment_result['score']
                            
                            fully_analyzed_aspects.append(aspect_data_raw)


                        for aspect_data in fully_analyzed_aspects:
                            new_aspect_sentiment = AspectSentiment(
                                raw_text_id=new_raw_text.id,
                                aspect=aspect_data['aspect'],
                                keyword_found=aspect_data['keyword_found'],
                                sentence=aspect_data['sentence'],
                                sentiment=aspect_data['sentiment'],
                                score=aspect_data['score'],
                                start_char=aspect_data['start_char'],
                                end_char=aspect_data['end_char']
                            )
                            db.session.add(new_aspect_sentiment)

                        db.session.commit() # Commit changes for this review and its aspects
                        reviews_processed_count += 1

                    if reviews_processed_count > 0:
                        flash(f"{reviews_processed_count} reviews from '{file.filename}' uploaded & analyzed successfully!", "success")
                    else:
                        flash("No valid reviews found in CSV.", "warning")

                except Exception as e:
                    flash(f"Error processing file: {e}", "danger")
            else:
                flash("Please select a valid CSV file.", "danger")

        elif "raw_text" in request.form:
            raw_text_content = request.form.get("raw_text")
            if raw_text_content.strip():
                # Process overall sentiment
                overall_sentiment_result = nlp_processor.analyze_sentiment(raw_text_content)
                print(f"DEBUG: Raw Text Overall Sentiment: {overall_sentiment_result['label']}, Score: {overall_sentiment_result['score']}")

                new_raw_text = RawText(
                    content=raw_text_content,
                    user_id=user.id,
                    sentiment=overall_sentiment_result["label"],
                    score=overall_sentiment_result["score"]
                )
                db.session.add(new_raw_text)
                db.session.flush() # Flush to get new_raw_text.id

                # Process aspects
                extracted_aspects_raw = nlp_processor.extract_aspects(raw_text_content)

                # Store fully analyzed aspects to save to DB
                fully_analyzed_aspects = []
                for aspect_data_raw in extracted_aspects_raw:
                    aspect_sentiment_result = nlp_processor.analyze_aspect_sentiment(aspect_data_raw['sentence'])
                    
                    # Add sentiment and score to the aspect_data_raw dictionary
                    aspect_data_raw['sentiment'] = aspect_sentiment_result['label']
                    aspect_data_raw['score'] = aspect_sentiment_result['score']
                    
                    fully_analyzed_aspects.append(aspect_data_raw)


                for aspect_data in fully_analyzed_aspects:
                    new_aspect_sentiment = AspectSentiment(
                        raw_text_id=new_raw_text.id,
                        aspect=aspect_data['aspect'],
                        keyword_found=aspect_data['keyword_found'],
                        sentence=aspect_data['sentence'],
                        sentiment=aspect_data['sentiment'],
                        score=aspect_data['score'],
                        start_char=aspect_data['start_char'],
                        end_char=aspect_data['end_char']
                    )
                    db.session.add(new_aspect_sentiment)

                db.session.commit() # Commit changes for this review and its aspects
                flash("Raw text saved & analyzed successfully!", "success")
            else:
                flash("Please enter some text before saving.", "danger")

        return redirect(url_for("my_reviews"))

    raw_texts = RawText.query.filter_by(user_id=user.id).options(db.joinedload(RawText.aspect_sentiments)).order_by(RawText.id.desc()).all()

    for text in raw_texts:
        print(f"\n--- Review ID: {text.id} ---")
        print(f"Overall Review Content: {text.content}")
        print(f"Overall Review Sentiment: {text.sentiment}, Stored Score: {text.score}")
        for aspect_obj in text.aspect_sentiments:
            print(f"  Aspect: '{aspect_obj.keyword_found}' (Sentence: '{aspect_obj.sentence}') -> Sentiment: {aspect_obj.sentiment}, Score: {aspect_obj.score}")
        print("--------------------")

        text.highlighted_content = _highlight_aspects_in_text(text.content, text.aspect_sentiments)

    return render_template("my_reviews.html", raw_texts=raw_texts)


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
        print(f"Error: Admin with username {username} already exists.")
        return

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_admin = Admin(admin_username=username, password=hashed_password)
    db.session.add(new_admin)
    db.session.commit()
    print(f"Admin {username} created successfully!")


# ------------------------
# Run App
# ------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    if not nlp_processor.init_nlp():
        print("ERROR: NLP models failed to initialize. Application may not function correctly.")
    app.run(debug=True)