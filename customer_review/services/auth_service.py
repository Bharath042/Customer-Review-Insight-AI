from werkzeug.security import generate_password_hash, check_password_hash
from models.models import db, User
from flask import session, flash
import jwt
import datetime
from config import Config

class AuthService:
    @staticmethod
    def register_user(email, username, password):
        """Register a new user"""
        if not email or not username or not password:
            return False, "Email, username and password are required!"
        
        if User.query.filter_by(email=email).first():
            return False, "Email already exists!"
        
        if User.query.filter_by(username=username).first():
            return False, "Username already exists!"
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        return True, "Registration successful! Please log in."
    
    @staticmethod
    def login_user(email, password):
        """Login a user"""
        if not email or not password:
            return False, "Email and password are required!", None
        
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return False, "Invalid email or password!", None
        
        # Save identity in session
        session['user_id'] = user.id
        session['username'] = user.username
        
        # Generate JWT token
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            Config.SECRET_KEY,
            algorithm='HS256'
        )
        
        return True, "Login successful!", user
    
    @staticmethod
    def logout_user():
        """Logout a user"""
        session.clear()
        return True, "Logout successful!"
    
    @staticmethod
    def get_current_user():
        """Get current logged in user"""
        if 'user_id' not in session:
            return None
        return User.query.get(session['user_id'])
