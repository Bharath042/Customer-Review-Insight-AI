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


# NEW MODEL: Category (e.g., Electronics, Vehicles)
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)

    aspects = db.relationship("Aspect", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Category {self.name}>'

# Aspect (e.g., Battery, Camera) belongs to Category
class Aspect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    weightage = db.Column(db.Float, nullable=False, default=1.0)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship("Category", back_populates="aspects")

    keywords = db.relationship("AspectKeyword", back_populates="aspect", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Aspect {self.name} (Category: {self.category.name})>'

# AspectKeyword links to Aspect
class AspectKeyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), nullable=False)

    aspect_id = db.Column(db.Integer, db.ForeignKey('aspect.id'), nullable=False)
    aspect = db.relationship("Aspect", back_populates="keywords")

# AspectSentiment links to Aspect
class AspectSentiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raw_text_id = db.Column(db.Integer, db.ForeignKey('raw_text.id'), nullable=False)
    raw_extracted_aspect = db.Column(db.String(500), nullable=True)

    aspect_id = db.Column(db.Integer, db.ForeignKey('aspect.id'), nullable=True)
    aspect = db.relationship('Aspect', backref='aspect_sentiments')

    keyword_found = db.Column(db.String(1000), nullable=False)
    sentence = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Float, nullable=False)
    start_char = db.Column(db.Integer, nullable=True)
    end_char = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        aspect_name = self.aspect.name if self.aspect else "Unmapped"
        return f'<AspectSentiment {self.id} - Aspect: {aspect_name}, Raw: {self.raw_extracted_aspect}, Sentiment: {self.sentiment}>'