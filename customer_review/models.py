from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Hashed password
    raw_texts = db.relationship('RawText', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Admin {self.admin_username}>'

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<UploadedFile {self.filename}>'

class RawText(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sentiment = db.Column(db.String(20), nullable=True) # Overall sentiment (POSITIVE, NEGATIVE, NEUTRAL)
    score = db.Column(db.Float, nullable=True) # Overall sentiment score
    
    # Relationship to AspectSentiment
    aspect_sentiments = db.relationship('AspectSentiment', backref='raw_text', lazy=True, cascade="all, delete-orphan") 
    def __repr__(self):
        return f'<RawText {self.id}>'

# NEW MODEL: AspectCategory
class AspectCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)

    keywords = db.relationship("AspectKeyword", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<AspectCategory {self.name}>'
    
class AspectKeyword(db.Model):
    __tablename__ = 'aspect_keyword'
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey('aspect_category.id'), nullable=False)
    category = db.relationship("AspectCategory", back_populates="keywords")

class AspectSentiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raw_text_id = db.Column(db.Integer, db.ForeignKey('raw_text.id'), nullable=False)
    # The 'aspect' column now stores the raw extracted text, useful for auditing or unmapped aspects
    raw_extracted_aspect = db.Column(db.String(500), nullable=True) 

    # NEW FOREIGN KEY: Link to AspectCategory
    aspect_category_id = db.Column(db.Integer, db.ForeignKey('aspect_category.id'), nullable=True)
    # Relationship to the AspectCategory model
    category = db.relationship('AspectCategory', backref='aspect_sentiments') # One AspectCategory to many AspectSentiments

    keyword_found = db.Column(db.String(1000), nullable=False) # The exact keyword or phrase found
    sentence = db.Column(db.Text, nullable=False) # The sentence from which the aspect was extracted
    sentiment = db.Column(db.String(20), nullable=False) # Sentiment for this specific aspect (POSITIVE, NEGATIVE, NEUTRAL)
    score = db.Column(db.Float, nullable=False) # Sentiment score for this aspect
    start_char = db.Column(db.Integer, nullable=True) # Start character index of keyword_found within the sentence
    end_char = db.Column(db.Integer, nullable=True) # End character index of keyword_found within the sentence

    def __repr__(self):
        # Updated repr to show category if available
        category_name = self.category.name if self.category else "Uncategorized"
        return f'<AspectSentiment {self.id} - Category: {category_name}, Raw: {self.raw_extracted_aspect}, Sentiment: {self.sentiment}>'