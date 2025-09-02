from flask import Flask
from flask_cors import CORS
from config import Config
from models.models import db
from routes.auth import auth_bp
from routes.files import files_bp
from routes.main import main_bp

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(main_bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
