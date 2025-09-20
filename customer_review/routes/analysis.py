from flask import Blueprint, render_template, session, redirect, url_for, flash
# MODIFIED: Removed direct imports of functions.
# Now importing the nlp_processor singleton instance.
from nlp_processor import nlp_processor # <--- CHANGE HERE
import pandas as pd
from models import db, User, RawText, AspectSentiment

analysis_bp = Blueprint('analysis', __name__)

def get_aspect_sentiment_summary(user_id):
    """
    Retrieves and aggregates aspect sentiment data for a given user.
    Calculates counts, an effective average sentiment strength score, dominant sentiment, and sentiment percentages.
    Returns a list of dictionaries, each representing an aggregated aspect.
    """
    # Query all AspectSentiment entries for the user
    aspect_data_raw = db.session.query(
        AspectSentiment.aspect,
        AspectSentiment.sentiment,
        AspectSentiment.score
    ).join(RawText).filter(RawText.user_id == user_id).all()

    if not aspect_data_raw:
        return []

    processed_aspect_data = []
    for aspect_item in aspect_data_raw:
        effective_score = 0.0
        # Transform the sentiment label and confidence score into a continuous sentiment strength from -1 to 1
        # This allows for meaningful averaging for a diverging chart.
        if aspect_item.sentiment.lower() == 'positive':
            # Map positive confidence (0-1) to 0 to 1 range (e.g., 0.5 to 1.0 for very confident positive)
            effective_score = 0.5 + (aspect_item.score * 0.5)
        elif aspect_item.sentiment.lower() == 'negative':
            # Map negative confidence (0-1) to -1 to 0 range (e.g., -1.0 to -0.5 for very confident negative)
            effective_score = -0.5 - (aspect_item.score * 0.5)
        # Neutral scores remain around 0 (or some small range if preferred)
        # We can also scale neutral confidence to a small range around 0, but for simplicity, 0 is fine.

        processed_aspect_data.append({
            'aspect': aspect_item.aspect,
            'sentiment': aspect_item.sentiment.lower(),
            'score': aspect_item.score, # Keep original confidence score for table if needed
            'effective_sentiment_score': effective_score # NEW: Our calculated diverging score
        })

    df = pd.DataFrame(processed_aspect_data)

    # Calculate counts for each sentiment label per aspect
    all_sentiments = ['positive', 'negative', 'neutral']
    sentiment_counts = df.groupby(['aspect', 'sentiment']).size().unstack(fill_value=0)
    sentiment_counts = sentiment_counts.reindex(columns=all_sentiments, fill_value=0)

    # Calculate average EFFECTIVE score per aspect for the chart
    avg_effective_scores = df.groupby('aspect')['effective_sentiment_score'].mean().round(2)

    # Calculate average ORIGINAL confidence score per aspect for the table
    avg_original_scores = df.groupby('aspect')['score'].mean().round(2)


    # Merge counts and average scores
    summary_df = sentiment_counts.join(avg_effective_scores)
    summary_df.rename(columns={'effective_sentiment_score': 'average_sentiment_strength'}, inplace=True) # NEW name

    # Also join the original average score for the table
    summary_df = summary_df.join(avg_original_scores)
    summary_df.rename(columns={'score': 'average_original_confidence_score'}, inplace=True) # NEW name for table


    # Calculate total mentions per aspect
    summary_df['total_mentions'] = summary_df[all_sentiments].sum(axis=1)

    # Calculate sentiment percentages
    for sentiment_type in all_sentiments:
        summary_df[f'{sentiment_type}_percentage'] = (
            (summary_df[sentiment_type] / summary_df['total_mentions']) * 100
        ).fillna(0).round(2)

    # Determine dominant sentiment (using counts, reverting to prior tie-breaker)
    def get_dominant_sentiment(row):
        sentiments = {s: row.get(s, 0) for s in all_sentiments}
        total = row['total_mentions']
        if total == 0:
            return 'N/A'

        max_sentiment_count = max(sentiments.values())

        dominant_list = [s for s, count in sentiments.items() if count == max_sentiment_count]

        # Original tie-breaker: Positive > Neutral > Negative
        if 'positive' in dominant_list: return 'Positive'
        if 'negative' in dominant_list: return 'Negative'
        if 'neutral' in dominant_list: return 'Neutral'
        return 'N/A'

    summary_df['dominant_sentiment'] = summary_df.apply(get_dominant_sentiment, axis=1)

    # Reset index to make 'aspect' a column again and convert to list of dicts for JSON compatibility
    summary_list = summary_df.reset_index().to_dict(orient='records')

    return summary_list


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
        # MODIFIED: Call methods on the nlp_processor instance
        extracted_aspects = nlp_processor.extract_aspects(review) # <--- CHANGE HERE

        # The analyze_aspect_sentiment method expects a single string for an aspect.
        # So, we need to iterate through the extracted_aspects and call it for each.
        analyzed_aspects_for_review = []
        for aspect_data_raw in extracted_aspects:
            aspect_sentiment_result = nlp_processor.analyze_aspect_sentiment(aspect_data_raw['keyword_found'])
            
            # Merge the sentiment results back into the aspect data
            aspect_data_raw['sentiment'] = aspect_sentiment_result['label']
            aspect_data_raw['score'] = aspect_sentiment_result['score']
            analyzed_aspects_for_review.append(aspect_data_raw)


        # MODIFIED: Call method on the nlp_processor instance
        overall_sentiment = nlp_processor.analyze_sentiment(review) # <--- CHANGE HERE

        results.append({
            'original': review,
            'overall_sentiment_label': overall_sentiment['label'],
            'overall_sentiment_score': overall_sentiment['score'],
            'aspect_sentiments': analyzed_aspects_for_review # Use the correctly analyzed list
        })

    return render_template('test_nlp.html', results=results)


@analysis_bp.route('/aspect-analysis')
def aspect_analysis_page():
    if "user_id" not in session:
        flash("Please log in to view aspect analysis.", "warning")
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    aspect_summary = get_aspect_sentiment_summary(user_id)

    # print("Aspect Summary for charts:", aspect_summary) # For debugging

    return render_template('aspect_analysis.html', aspect_summary=aspect_summary)