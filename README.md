# 🎯 Customer Review Insight AI

An intelligent web application that performs **Aspect-Based Sentiment Analysis (ABSA)** on customer reviews using advanced NLP techniques. The system automatically extracts aspects from reviews, analyzes sentiment for each aspect, and provides comprehensive insights through interactive dashboards.

---

## 📋 Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Screenshots](#screenshots)
- [Contributing](#contributing)
- [License](#license)

---

## ✨ Features

### 👤 User Features
- **Review Submission**: Submit reviews via text input or CSV file upload
- **Aspect-Based Analysis**: Automatic extraction and sentiment analysis of product/service aspects
- **Interactive Dashboard**: 
  - Overview with key metrics and statistics
  - My Reviews page with filtering and sorting
  - Aspect Analysis with tabbed interface (Overview, Categories, Aspects, Trends)
- **Advanced Filtering**: Filter reviews by category, sentiment, confidence, and date range
- **Visualizations**: 
  - Category performance cards
  - Sentiment comparison charts
  - Trend analysis over time
  - Aspect sentiment scores
- **Export Options**: Download analysis as CSV or comprehensive PDF reports

### 👨‍💼 Admin Features
- **User Management**: View and manage all registered users
- **Category Management**: Create and organize aspect categories
- **Aspect Management**: Define aspects and keywords for each category
- **System Analytics**: View overall system statistics and user activity
- **Bulk Operations**: Manage multiple aspects and keywords efficiently

### 🤖 AI/ML Capabilities
- **Aspect Extraction**: 
  - Rule-based keyword matching with fuzzy matching
  - Dependency parsing using spaCy (POS tagging, noun phrases)
  - Custom aspect categories with admin-defined keywords
- **Sentiment Analysis**:
  - Hugging Face DistilBERT transformer model
  - Aspect-level sentiment scoring (Positive/Negative/Neutral)
  - Confidence metrics (0-1 scale)
  - Softener detection (e.g., "a bit", "slightly")
- **Text Preprocessing**:
  - Tokenization and cleaning
  - Stop-word removal
  - Sentence segmentation
  - Lemmatization

---

## 🛠️ Technology Stack

### Backend & AI
- **Framework**: Flask (Python)
- **NLP Engine**: spaCy + Hugging Face Transformers (DistilBERT)
- **Database**: SQLAlchemy with SQLite
- **Authentication**: Session-based with Werkzeug Password Hashing

### Frontend & UI
- **Templates**: Jinja2 with Bootstrap 5
- **Visualization**: Chart.js for interactive charts
- **Styling**: Custom CSS with dark theme
- **File Processing**: Pandas for CSV handling

### Additional Libraries
- **PDF Generation**: ReportLab
- **Data Visualization**: Matplotlib (for PDF charts)
- **Security**: Flask-CORS, Werkzeug

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client (Browser)                      │
│              User Dashboard | Admin Panel                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                   Flask Server                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Routes     │  │  Templates   │  │   Static     │  │
│  │   (Views)    │  │   (Jinja2)   │  │  (CSS/JS)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────┬────────────────────────────────┬───────────┘
             │                                │
             ↓                                ↓
┌────────────────────────┐      ┌────────────────────────┐
│   Database (SQLite)    │      │     NLP Engine         │
│  ┌──────────────────┐  │      │  ┌──────────────────┐  │
│  │ User             │  │      │  │ spaCy (Aspect    │  │
│  │ RawText          │  │      │  │  Extraction)     │  │
│  │ AspectSentiment  │  │      │  ├──────────────────┤  │
│  │ Category         │  │      │  │ Transformers     │  │
│  │ Aspect           │  │      │  │ (Sentiment       │  │
│  │ AspectKeyword    │  │      │  │  Analysis)       │  │
│  │ Admin            │  │      │  └──────────────────┘  │
│  └──────────────────┘  │      └────────────────────────┘
└────────────────────────┘
```

---

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/Customer-Review-Insight-AI.git
cd Customer-Review-Insight-AI/customer_review
```

2. **Create virtual environment**
```bash
python -m venv .venv
```

3. **Activate virtual environment**
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Download spaCy language model**
```bash
python -m spacy download en_core_web_sm
```

6. **Initialize the database**
```bash
python
>>> from app import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

7. **Create admin account (optional)**
```bash
python
>>> from app import app, db
>>> from models import Admin
>>> from werkzeug.security import generate_password_hash
>>> with app.app_context():
...     admin = Admin(username='admin', password_hash=generate_password_hash('admin123'))
...     db.session.add(admin)
...     db.session.commit()
>>> exit()
```

8. **Run the application**
```bash
python app.py
```

9. **Access the application**
- User Interface: `http://localhost:5000`
- Admin Panel: `http://localhost:5000/admin/login`

---

## 🚀 Usage

### For Users

1. **Register/Login**: Create an account or login
2. **Submit Reviews**: 
   - Enter text directly
   - Upload CSV file with reviews
3. **View Analysis**:
   - Navigate to "My Reviews" to see all your reviews with sentiment
   - Go to "Aspect Analysis" for detailed aspect-based insights
4. **Filter & Sort**: Use filters to find specific reviews or aspects
5. **Export Reports**: Download CSV or PDF reports

### For Admins

1. **Login**: Access admin panel at `/admin/login`
2. **Manage Categories**: Create categories (e.g., Electronics, Food)
3. **Define Aspects**: Add aspects to categories with keywords
4. **Monitor Users**: View user activity and statistics
5. **System Analytics**: Track overall system performance

---

## 📁 Project Structure

```
customer_review/
├── app.py                      # Main Flask application
├── models.py                   # Database models (SQLAlchemy)
├── nlp_processor.py            # NLP processing logic
├── requirements.txt            # Python dependencies
│
├── routes/
│   ├── admin_dashboard.py      # Admin routes
│   └── analysis.py             # Analysis & export routes
│
├── templates/
│   ├── base_user_dashboard.html    # User base template
│   ├── base_admin.html             # Admin base template
│   ├── home.html                   # User dashboard
│   ├── my_reviews.html             # Reviews listing
│   ├── aspect_analysis.html        # Aspect analysis (tabbed)
│   ├── sentiment_trends.html       # Trends visualization
│   ├── admin_home.html             # Admin dashboard
│   ├── admin_user_management.html  # User management
│   └── admin_aspect_categories.html # Category management
│
├── static/
│   ├── styles.css              # Global styles
│   ├── my_reviews.css          # Review page styles
│   └── dashboard_theme.css     # Dashboard theme
│
└── instance/
    └── reviews.db              # SQLite database
```

---

## 🔌 API Endpoints

### User Routes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home/Dashboard |
| GET/POST | `/register` | User registration |
| GET/POST | `/login` | User login |
| GET | `/logout` | User logout |
| GET/POST | `/my_reviews` | View and submit reviews |
| POST | `/delete_raw_text/<id>` | Delete a review |
| GET/POST | `/upload_csv` | Upload CSV file |

### Analysis Routes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/aspect-analysis` | Aspect analysis dashboard |
| GET | `/sentiment-trends` | Sentiment trends page |
| GET | `/sentiment-trends-embed` | Embedded trends chart |
| GET | `/export-csv` | Export analysis as CSV |
| GET | `/export-pdf` | Export analysis as PDF |

### Admin Routes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/admin/login` | Admin login |
| GET | `/admin/logout` | Admin logout |
| GET | `/admin/home` | Admin dashboard |
| GET | `/admin/users` | User management |
| GET | `/admin/analysis` | System analytics |
| GET/POST | `/admin/aspect_categories` | Manage categories & aspects |
| POST | `/admin/categories/<id>/add_aspect` | Add aspect to category |
| POST | `/admin/aspect/<id>/delete` | Delete aspect |
| POST | `/admin/aspect_categories/delete/<id>` | Delete category |

---

## 🗄️ Database Schema

### Core Tables

**User**
- Stores user account information
- Relationships: Has many RawText (reviews)

**RawText**
- Stores customer reviews
- Relationships: Belongs to User, has many AspectSentiment

**Category**
- Organizes aspects into logical groups (e.g., Electronics, Food)
- Relationships: Has many Aspect

**Aspect**
- Predefined aspects within categories (e.g., Battery, Camera)
- Relationships: Belongs to Category, has many AspectKeyword and AspectSentiment

**AspectKeyword**
- Keywords for matching aspects in reviews
- Relationships: Belongs to Aspect

**AspectSentiment**
- Extracted aspect sentiments from reviews
- Relationships: Belongs to RawText and Aspect (optional)

**Admin**
- Admin user accounts for system management
- Independent authentication table

---

## 📊 Key Features Explained

### 1. Aspect Extraction
The system uses a hybrid approach:
- **Keyword Matching**: Matches predefined keywords to aspects
- **Fuzzy Matching**: Handles variations and typos
- **Dependency Parsing**: Extracts noun phrases and adjectives
- **Context-Aware**: Considers sentence structure

### 2. Sentiment Analysis
- **Model**: DistilBERT fine-tuned for sentiment analysis
- **Granularity**: Aspect-level (not just overall review)
- **Output**: Label (Positive/Negative/Neutral) + Confidence Score
- **Softener Detection**: Handles phrases like "a bit expensive"

### 3. Category-Based Analytics
- **Performance Overview**: Cards showing category statistics
- **Comparison Charts**: Stacked bar charts for sentiment distribution
- **Trend Analysis**: Line charts showing sentiment changes over time
- **Filtering**: Filter reviews by category

### 4. Export & Reporting
- **CSV Export**: Tabular data for further analysis
- **PDF Reports**: Comprehensive reports with:
  - Category performance summary
  - Aspect sentiment charts
  - Detailed review listings
  - Insights and recommendations

---

## 🎨 Screenshots

### User Dashboard
![User Dashboard](screenshots/user_dashboard.png)

### Aspect Analysis (Tabbed Interface)
![Aspect Analysis](screenshots/aspect_analysis.png)

### Admin Panel
![Admin Panel](screenshots/admin_panel.png)

---

## 🧪 Testing

### Sample Reviews for Testing

**Electronics:**
```
The battery life is excellent and the camera quality is amazing, but the price is too high.
```

**Food & Restaurants:**
```
The food was delicious and the ambiance was beautiful, but the service was slow.
```

**Uncategorized Aspects:**
```
The packaging was excellent and the delivery was super fast.
```

---

## 🔧 Configuration

### Environment Variables
Create a `.env` file (optional):
```env
SECRET_KEY=your-secret-key-here
DATABASE_URI=sqlite:///instance/reviews.db
FLASK_ENV=development
```

### Database Configuration
Edit `app.py` to change database settings:
```python
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/reviews.db"
```

---

## 📈 Future Enhancements

- [ ] Multi-language support
- [ ] Real-time sentiment analysis
- [ ] Email notifications for negative reviews
- [ ] API for third-party integrations
- [ ] Advanced ML models (BERT, RoBERTa)
- [ ] Sentiment comparison across competitors
- [ ] Automated aspect discovery (unsupervised)

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---


## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Infosys Springboard** for the Virtual Internship opportunity
- **Hugging Face** for transformer models
- **spaCy** for NLP processing
- **Flask** community for excellent documentation

---

## 📞 Contact

For questions or support, please contact:
- Email: your.email@example.com
- GitHub: [@yourusername](https://github.com/yourusername)

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/yourusername/Customer-Review-Insight-AI.git
cd Customer-Review-Insight-AI/customer_review

# Install and run
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python app.py

# Access at http://localhost:5000
```

---

**Made with ❤️ for Infosys Springboard Virtual Internship 6.0**
