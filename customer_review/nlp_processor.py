import re
import string
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from transformers import pipeline

# --- Global variable to hold our pipeline ---
# We start with None. We will load the model only when it's first needed.
sentiment_pipeline = None

def clean_text(text):
    """
    An enhanced text cleaning function.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word not in stop_words]
    text = " ".join(filtered_tokens)
    return text

def analyze_sentiment(text):
    """
    Analyzes the sentiment of a given text using a pre-trained model.
    Loads the model on the first run (lazy loading).
    """
    global sentiment_pipeline
    
    # --- LAZY LOADING ---
    # If the model hasn't been loaded yet, load it now.
    if sentiment_pipeline is None:
        print("Loading sentiment analysis model for the first time...")
        model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
        sentiment_pipeline = pipeline("sentiment-analysis", model=model_name)
        print("Model loaded successfully.")

    if not isinstance(text, str) or not text.strip():
        return {'label': 'NEUTRAL', 'score': 0.5}

    result = sentiment_pipeline(text)[0]
    
    return {
        'label': result['label'],
        'score': round(result['score'], 2)
    }