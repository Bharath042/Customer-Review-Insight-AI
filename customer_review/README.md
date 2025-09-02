# Customer Review Insight AI - Milestone 1

## Project Overview
A Flask-based web application for managing customer reviews with user authentication, file uploads, and text management.

## Features
- ✅ User registration and login with email authentication
- ✅ CSV file upload and management
- ✅ Raw text input and management
- ✅ User profile management
- ✅ Secure session handling
- ✅ JWT token generation

## Project Structure
```
customer_review/
├── app.py                 # Main application entry point
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (create this)
├── .gitignore           # Git ignore rules
├── models/              # Database models
│   ├── __init__.py
│   └── models.py        # User, UploadedFile, RawText models
├── routes/              # Route handlers
│   ├── __init__.py
│   ├── auth.py          # Authentication routes
│   ├── files.py         # File management routes
│   └── main.py          # Main page routes
├── services/            # Business logic
│   ├── __init__.py
│   ├── auth_service.py  # Authentication logic
│   ├── file_service.py  # File handling logic
│   └── text_service.py  # Text handling logic
├── utils/               # Helper functions
│   ├── __init__.py
│   └── helpers.py       # Utility functions
├── templates/           # HTML templates
├── static/              # CSS and static files
└── uploads/             # User uploaded files
```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Environment File
Create a `.env` file in the project root:
```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/database_name
SECRET_KEY=your_secret_key_here
```

### 3. Database Setup
- Create MySQL database
- Update `.env` file with your database credentials

### 4. Run the Application
```bash
python app.py
```

### 5. Access the Application
Open your browser and go to: `http://127.0.0.1:5000/`

## Code Architecture

### Models
- **User**: Stores user authentication information
- **UploadedFile**: Manages uploaded CSV files
- **RawText**: Stores user input text

### Services
- **AuthService**: Handles user registration, login, and session management
- **FileService**: Manages file uploads, deletions, and renames
- **TextService**: Handles text creation, editing, and deletion

### Routes
- **auth.py**: Authentication endpoints (register, login, logout)
- **files.py**: File and text management endpoints
- **main.py**: Main page routes (home, profile)

## Security Features
- Password hashing with Werkzeug
- Session-based authentication
- JWT token generation
- User ownership validation
- File type validation

## Future Milestones
- **Milestone 2**: Text preprocessing and sentiment analysis
- **Milestone 3**: Aspect-based sentiment analysis
- **Milestone 4**: Visualization dashboards and admin panel

## Development Notes
- Uses Flask Blueprint pattern for modular routing
- Application factory pattern for clean initialization
- Service layer separates business logic from routes
- Environment-based configuration management
