from flask import Blueprint, render_template, session, redirect, url_for, flash, current_app
from nlp_processor import nlp_processor
import pandas as pd
from models import db, User, RawText, AspectSentiment, Category, Aspect
from sqlalchemy.orm import joinedload # To efficiently load related category data

analysis_bp = Blueprint('analysis', __name__)


def get_aspect_sentiment_summary(user_id):
    """
    Retrieves and aggregates aspect sentiment data for a given user.
    Separates aggregated predefined categories from aggregated individual uncategorized aspects.
    Returns two lists of dictionaries: categorized_summary and uncategorized_summary.
    """
    aspect_data_raw_query = db.session.query(
        AspectSentiment.raw_extracted_aspect,
        AspectSentiment.sentiment,
        AspectSentiment.score,
        Aspect.name.label('aspect_name'),
        Aspect.id.label('aspect_id')
    ).join(RawText).outerjoin(Aspect, AspectSentiment.aspect_id == Aspect.id)\
    .filter(RawText.user_id == user_id).all()

    print(f"DEBUG: aspect_data_raw_query for user {user_id}: {aspect_data_raw_query}") # Keep debug print for now

    if not aspect_data_raw_query:
        print(f"DEBUG: No raw aspect data found for user {user_id}.") # Keep debug print for now
        return [], []

    categorized_items = []
    uncategorized_items = []

    for aspect_item in aspect_data_raw_query:
        effective_score = 0.0
        if aspect_item.sentiment.lower() == 'positive':
            effective_score = 0.5 + (aspect_item.score * 0.5)
        elif aspect_item.sentiment.lower() == 'negative':
            effective_score = -0.5 - (aspect_item.score * 0.5)

        # Ensure raw_extracted_aspect is a string, even if None from DB
        current_raw_aspect = aspect_item.raw_extracted_aspect if aspect_item.raw_extracted_aspect else "Unknown Aspect"

        processed_item = {
            'raw_extracted_aspect': current_raw_aspect, # Use the cleaned raw aspect name
            'sentiment': aspect_item.sentiment.lower(),
            'score': aspect_item.score,
            'effective_sentiment_score': effective_score
        }

        if aspect_item.aspect_id:
            processed_item['aspect_group_name'] = aspect_item.aspect_name
            categorized_items.append(processed_item)
        else:
            processed_item['aspect_group_name'] = current_raw_aspect # Group by its raw name (now guaranteed non-None)
            uncategorized_items.append(processed_item)

    # Helper function to process a list of items (no change here)
    def _process_sentiment_data(items, is_categorized=False):
        # ... (rest of _process_sentiment_data function remains the same as before) ...
        if not items:
            return []

        df = pd.DataFrame(items)
        
        if df.empty:
            return []

        all_sentiments = ['positive', 'negative', 'neutral'] # Ensure all possible sentiments are considered

        # Group by the 'aspect_group_name'
        sentiment_counts = df.groupby(['aspect_group_name', 'sentiment']).size().unstack(fill_value=0)
        sentiment_counts = sentiment_counts.reindex(columns=all_sentiments, fill_value=0)

        avg_effective_scores = df.groupby('aspect_group_name')['effective_sentiment_score'].mean().round(2)
        avg_original_scores = df.groupby('aspect_group_name')['score'].mean().round(2)

        summary_df = sentiment_counts.join(avg_effective_scores)
        summary_df.rename(columns={'effective_sentiment_score': 'average_sentiment_strength'}, inplace=True)

        summary_df = summary_df.join(avg_original_scores)
        summary_df.rename(columns={'score': 'average_original_confidence_score'}, inplace=True)

        summary_df['total_mentions'] = summary_df[all_sentiments].sum(axis=1)

        for sentiment_type in all_sentiments:
            summary_df[f'{sentiment_type}_percentage'] = (
                (summary_df[sentiment_type] / summary_df['total_mentions']) * 100
            ).fillna(0).round(2)

        def get_dominant_sentiment(row):
            sentiments = {s: row.get(s, 0) for s in all_sentiments}
            total = row['total_mentions']
            if total == 0:
                return 'N/A'

            max_sentiment_count = max(sentiments.values())
            dominant_list = [s for s, count in sentiments.items() if count == max_sentiment_count]

            if 'positive' in dominant_list: return 'Positive'
            if 'negative' in dominant_list: return 'Negative'
            if 'neutral' in dominant_list: return 'Neutral'
            return 'N/A'

        summary_df['dominant_sentiment'] = summary_df.apply(get_dominant_sentiment, axis=1)

        summary_df = summary_df.rename_axis('aspect').reset_index()

        summary_list = summary_df.to_dict(orient='records')
        return summary_list

    categorized_summary = _process_sentiment_data(categorized_items, is_categorized=True)
    uncategorized_summary = _process_sentiment_data(uncategorized_items, is_categorized=False)
    print(f"DEBUG: Final Categorized Summary for user {user_id}: {categorized_summary}")
    print(f"DEBUG: Final Uncategorized Summary for user {user_id}: {uncategorized_summary}")


    return categorized_summary, uncategorized_summary


@analysis_bp.route('/test-nlp')
def test_nlp_page():
    # ... (sample_reviews and results initialization) ...

    with current_app.app_context():
        nlp_processor.init_nlp()

    for review in sample_reviews:
        extracted_aspects = nlp_processor.extract_aspects(review) 

        analyzed_aspects_for_review = []
        for aspect_data_raw in extracted_aspects:
            # *** THIS IS THE CORRECTED LINE ***
            aspect_sentiment_result = nlp_processor.analyze_aspect_sentiment(aspect_data_raw['context_snippet'])

            # Prepare data for storage (or display in test_nlp_page)
            analyzed_aspects_for_review.append({
                'raw_extracted_aspect': aspect_data_raw['raw_extracted_aspect'],
                'aspect_category_id': aspect_data_raw['aspect_category_id'],
                'keyword_found': aspect_data_raw['keyword_found'],
                'sentence': aspect_data_raw['sentence'],
                'context_snippet': aspect_data_raw['context_snippet'], # <--- ADD THIS LINE
                'sentiment': aspect_sentiment_result['label'],
                'score': aspect_sentiment_result['score'],
                'start_char': aspect_data_raw['start_char'],
                'end_char': aspect_data_raw['end_char']
            })
        # ... (overall_sentiment and results.append) ...
    return render_template('test_nlp.html', results=results)


@analysis_bp.route('/aspect-analysis')
def aspect_analysis_page():
    # ... (keep existing login check) ...

    user_id = session["user_id"]
    with current_app.app_context():
        # UNCOMMENT THIS:
        categorized_aspect_summary, uncategorized_aspect_summary = get_aspect_sentiment_summary(user_id)

    # Modify the render_template call
    return render_template(
        'aspect_analysis.html',
        categorized_aspect_summary=categorized_aspect_summary,
        uncategorized_aspect_summary=uncategorized_aspect_summary
    )