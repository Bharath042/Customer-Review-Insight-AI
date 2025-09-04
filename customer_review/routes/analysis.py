from flask import Blueprint, render_template
from nlp_processor import clean_text, analyze_sentiment

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/test-nlp')
def test_nlp_page():
    """A test page to demonstrate the NLP pipeline on multiple reviews."""
    
    sample_reviews = [
        "The build quality is exceptional and it feels very premium. I am incredibly impressed!",
        "This was a fantastic purchase! The product exceeded all my expectations and works perfectly.",
        "Absolutely brilliant customer support. They were so helpful and resolved my issue in minutes.",
        "I'm so happy with the battery life. It lasts for days on a single charge. Highly recommended!",
        "The user interface is intuitive and beautifully designed. It's a joy to use every day.",
        "The product was delivered on the expected date and the packaging was standard.",
        "This is the third time I have purchased this item. The model is the 2024 version.",
        "The device requires three AA batteries, which are not included in the box.",
        "The user manual is available for download on the company's official website.",
        "The color of the product is listed as 'charcoal grey' on the specification sheet.",
        "The connection constantly drops and the software is full of bugs. A complete waste of money.",
        "I am extremely disappointed. The item arrived damaged and doesn't work at all.",
        "Their customer service was unhelpful and rude. I was on hold for over an hour.",
        "This is the worst product I have ever bought. It broke after only two uses.",
        "The battery life is a joke. It barely lasts a few hours before needing a recharge."
    ]
    
    results = []
    for review in sample_reviews:
        cleaned = clean_text(review)
        sentiment = analyze_sentiment(cleaned)
        results.append({
            'original': review,
            'cleaned': cleaned,
            'sentiment_label': sentiment['label'],
            'sentiment_score': sentiment['score']
        })
    
    return render_template('test_nlp.html', results=results)