from flask import Blueprint, render_template, session, redirect, url_for, flash, current_app, request, jsonify, send_file, make_response
from nlp_processor import nlp_processor
import pandas as pd
from models import db, User, RawText, AspectSentiment, Category, Aspect
from sqlalchemy.orm import joinedload # To efficiently load related category data
from datetime import datetime, timedelta
import io
import csv
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend

# Optional: matplotlib for sentiment trends graph in PDF
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-GUI backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. PDF will not include sentiment trends graph.")

analysis_bp = Blueprint('analysis', __name__)


def get_aspect_sentiment_summary(user_id, start_date=None, end_date=None):
    """
    Retrieves and aggregates aspect sentiment data for a given user.
    Separates aggregated predefined categories from aggregated individual uncategorized aspects.
    Returns two lists of dictionaries: categorized_summary and uncategorized_summary.
    """
    query = db.session.query(
        AspectSentiment.raw_extracted_aspect,
        AspectSentiment.sentiment,
        AspectSentiment.score,
        Aspect.name.label('aspect_name'),
        Aspect.id.label('aspect_id')
    ).join(RawText).outerjoin(Aspect, AspectSentiment.aspect_id == Aspect.id)\
    .filter(RawText.user_id == user_id)
    
    # Apply date filters if provided
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RawText.timestamp >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RawText.timestamp < end_dt)
        except ValueError:
            pass
    
    aspect_data_raw_query = query.all()

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


def get_category_summary(user_id, start_date=None, end_date=None):
    """
    Get aggregated sentiment data grouped by category.
    Returns list of dictionaries with category-wise statistics.
    """
    # Query to get all aspects with their categories and sentiments
    query = db.session.query(
        Category.id.label('category_id'),
        Category.name.label('category_name'),
        AspectSentiment.sentiment,
        AspectSentiment.score
    ).join(Aspect, Category.id == Aspect.category_id)\
     .join(AspectSentiment, Aspect.id == AspectSentiment.aspect_id)\
     .join(RawText, AspectSentiment.raw_text_id == RawText.id)\
     .filter(RawText.user_id == user_id)
    
    # Apply date filters
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RawText.timestamp >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RawText.timestamp < end_dt)
        except ValueError:
            pass
    
    results = query.all()
    
    # Aggregate by category
    category_data = {}
    for row in results:
        cat_id = row.category_id
        if cat_id not in category_data:
            category_data[cat_id] = {
                'category_id': cat_id,
                'category_name': row.category_name,
                'total_mentions': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'avg_score': 0,
                'scores': []
            }
        
        category_data[cat_id]['total_mentions'] += 1
        category_data[cat_id]['scores'].append(row.score)
        
        sentiment = row.sentiment.upper()
        if sentiment == 'POSITIVE':
            category_data[cat_id]['positive'] += 1
        elif sentiment == 'NEGATIVE':
            category_data[cat_id]['negative'] += 1
        elif sentiment == 'NEUTRAL':
            category_data[cat_id]['neutral'] += 1
    
    # Calculate percentages and averages
    category_summary = []
    for cat_id, data in category_data.items():
        total = data['total_mentions']
        if total > 0:
            data['positive_percentage'] = round((data['positive'] / total) * 100, 1)
            data['negative_percentage'] = round((data['negative'] / total) * 100, 1)
            data['neutral_percentage'] = round((data['neutral'] / total) * 100, 1)
            data['avg_score'] = round(sum(data['scores']) / len(data['scores']), 2)
            
            # Determine dominant sentiment
            if data['positive'] > data['negative'] and data['positive'] > data['neutral']:
                data['dominant_sentiment'] = 'Positive'
            elif data['negative'] > data['positive'] and data['negative'] > data['neutral']:
                data['dominant_sentiment'] = 'Negative'
            else:
                data['dominant_sentiment'] = 'Neutral'
        
        del data['scores']  # Remove raw scores list
        category_summary.append(data)
    
    # Sort by total mentions descending
    category_summary.sort(key=lambda x: x['total_mentions'], reverse=True)
    
    return category_summary


def get_category_trends(user_id, start_date=None, end_date=None):
    """
    Get sentiment trends over time grouped by category.
    Returns time-series data for category-wise sentiment analysis.
    """
    # Query to get category sentiments over time
    query = db.session.query(
        RawText.timestamp,
        Category.id.label('category_id'),
        Category.name.label('category_name'),
        AspectSentiment.sentiment,
        AspectSentiment.score
    ).join(AspectSentiment, RawText.id == AspectSentiment.raw_text_id)\
     .join(Aspect, AspectSentiment.aspect_id == Aspect.id)\
     .join(Category, Aspect.category_id == Category.id)\
     .filter(RawText.user_id == user_id)
    
    # Apply date filters
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RawText.timestamp >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RawText.timestamp < end_dt)
        except ValueError:
            pass
    
    query = query.order_by(RawText.timestamp.asc())
    results = query.all()
    
    # Group by date and category
    trends_data = {}
    for row in results:
        date_key = row.timestamp.strftime('%Y-%m-%d')
        cat_name = row.category_name
        
        if date_key not in trends_data:
            trends_data[date_key] = {}
        
        if cat_name not in trends_data[date_key]:
            trends_data[date_key][cat_name] = {
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'total': 0,
                'avg_sentiment': 0
            }
        
        trends_data[date_key][cat_name]['total'] += 1
        sentiment = row.sentiment.upper()
        if sentiment == 'POSITIVE':
            trends_data[date_key][cat_name]['positive'] += 1
        elif sentiment == 'NEGATIVE':
            trends_data[date_key][cat_name]['negative'] += 1
        elif sentiment == 'NEUTRAL':
            trends_data[date_key][cat_name]['neutral'] += 1
    
    # Calculate average sentiment score for each date/category
    for date_key in trends_data:
        for cat_name in trends_data[date_key]:
            data = trends_data[date_key][cat_name]
            total = data['total']
            if total > 0:
                # Calculate sentiment score: positive=1, neutral=0, negative=-1
                score = (data['positive'] - data['negative']) / total
                data['avg_sentiment'] = round(score, 2)
    
    return trends_data


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
    if "user_id" not in session:
        flash("Please log in to view aspect analysis.", "warning")
        return redirect(url_for('login'))

    user_id = session["user_id"]
    
    # Get date range from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    with current_app.app_context():
        categorized_aspect_summary, uncategorized_aspect_summary = get_aspect_sentiment_summary(user_id, start_date, end_date)
        category_summary = get_category_summary(user_id, start_date, end_date)
        category_trends = get_category_trends(user_id, start_date, end_date)

    return render_template(
        'aspect_analysis.html',
        categorized_aspect_summary=categorized_aspect_summary,
        uncategorized_aspect_summary=uncategorized_aspect_summary,
        category_summary=category_summary,
        category_trends=category_trends,
        start_date=start_date,
        end_date=end_date
    )


def get_sentiment_trends(user_id, start_date=None, end_date=None):
    """
    Get sentiment trends over time for aspects.
    Returns time-series data grouped by date and aspect.
    """
    # Base query
    query = db.session.query(
        RawText.timestamp,
        AspectSentiment.sentiment,
        AspectSentiment.score,
        Aspect.name.label('aspect_name'),
        Aspect.id.label('aspect_id')
    ).join(AspectSentiment, RawText.id == AspectSentiment.raw_text_id)\
     .outerjoin(Aspect, AspectSentiment.aspect_id == Aspect.id)\
     .filter(RawText.user_id == user_id)
    
    # Apply date filters if provided
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RawText.timestamp >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RawText.timestamp < end_dt)
        except ValueError:
            pass
    
    results = query.all()
    
    if not results:
        return {}
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame([{
        'date': r.timestamp.date(),
        'aspect': r.aspect_name if r.aspect_name else 'Uncategorized',
        'sentiment': r.sentiment.lower(),
        'score': r.score
    } for r in results])
    
    # Calculate effective sentiment score
    def calc_effective_score(row):
        if row['sentiment'] == 'positive':
            return 0.5 + (row['score'] * 0.5)
        elif row['sentiment'] == 'negative':
            return -0.5 - (row['score'] * 0.5)
        return 0.0
    
    df['effective_score'] = df.apply(calc_effective_score, axis=1)
    
    # Group by date and aspect, calculate average sentiment
    trends = df.groupby(['date', 'aspect'])['effective_score'].mean().reset_index()
    
    # Pivot to get aspects as columns
    trends_pivot = trends.pivot(index='date', columns='aspect', values='effective_score').fillna(0)
    
    # Convert to format suitable for Chart.js
    trends_data = {
        'dates': [d.strftime('%Y-%m-%d') for d in sorted(trends_pivot.index)],
        'aspects': {}
    }
    
    for aspect in trends_pivot.columns:
        trends_data['aspects'][aspect] = trends_pivot[aspect].tolist()
    
    return trends_data


@analysis_bp.route('/sentiment-trends')
def sentiment_trends_page():
    """Display sentiment trends over time"""
    if "user_id" not in session:
        flash("Please log in to view sentiment trends.", "warning")
        return redirect(url_for('login'))
    
    user_id = session["user_id"]
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    trends_data = get_sentiment_trends(user_id, start_date, end_date)
    
    return render_template(
        'sentiment_trends.html',
        trends_data=trends_data,
        start_date=start_date,
        end_date=end_date
    )


@analysis_bp.route('/sentiment-trends-embed')
def sentiment_trends_embed():
    """Display sentiment trends chart only (for embedding in tabs)"""
    if "user_id" not in session:
        return "Please log in", 401
    
    user_id = session["user_id"]
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    trends_data = get_sentiment_trends(user_id, start_date, end_date)
    
    return render_template(
        'sentiment_trends_embed.html',
        trends_data=trends_data,
        start_date=start_date,
        end_date=end_date
    )


@analysis_bp.route('/export-csv')
def export_csv():
    """Export aspect analysis to CSV"""
    if "user_id" not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session["user_id"]
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    categorized_summary, uncategorized_summary = get_aspect_sentiment_summary(user_id, start_date, end_date)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Aspect', 'Positive', 'Negative', 'Neutral', 'Total Mentions', 
                     'Positive %', 'Negative %', 'Neutral %', 'Dominant Sentiment', 'Avg Sentiment Score'])
    
    # Write categorized aspects
    if categorized_summary:
        writer.writerow(['=== CATEGORIZED ASPECTS ==='])
        for item in categorized_summary:
            writer.writerow([
                item['aspect'],
                item['positive'],
                item['negative'],
                item['neutral'],
                item['total_mentions'],
                f"{item['positive_percentage']}%",
                f"{item['negative_percentage']}%",
                f"{item['neutral_percentage']}%",
                item['dominant_sentiment'],
                item['average_sentiment_strength']
            ])
    
    # Write uncategorized aspects
    if uncategorized_summary:
        writer.writerow([])
        writer.writerow(['=== UNCATEGORIZED ASPECTS ==='])
        for item in uncategorized_summary:
            writer.writerow([
                item['aspect'],
                item['positive'],
                item['negative'],
                item['neutral'],
                item['total_mentions'],
                f"{item['positive_percentage']}%",
                f"{item['negative_percentage']}%",
                f"{item['neutral_percentage']}%",
                item['dominant_sentiment'],
                item['average_sentiment_strength']
            ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=aspect_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response


@analysis_bp.route('/export-pdf')
def export_pdf():
    """Export comprehensive aspect analysis to PDF with sentiment trends and detailed reviews"""
    if "user_id" not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session["user_id"]
    username = User.query.get(user_id).username
    
    # Get user preferences for what to include
    include_aspects = request.args.get('include_aspects') == '1'
    include_reviews = request.args.get('include_reviews') == '1'
    
    # Get date ranges for aspects
    aspects_all_time = request.args.get('aspects_all_time') == '1'
    aspects_start_date = None if aspects_all_time else request.args.get('start_date')
    aspects_end_date = None if aspects_all_time else request.args.get('end_date')
    
    # Review count
    review_count_param = request.args.get('review_count', '20')
    review_count = None if review_count_param == 'all' else int(review_count_param)
    
    # Get aspect summary with appropriate date range
    categorized_summary, uncategorized_summary = get_aspect_sentiment_summary(user_id, aspects_start_date, aspects_end_date)
    
    # Get category summary for new section
    category_summary = get_category_summary(user_id, aspects_start_date, aspects_end_date)
    
    # Get reviews with aspects for detailed section
    query = RawText.query.filter_by(user_id=user_id).options(joinedload(RawText.aspect_sentiments))
    reviews = query.order_by(RawText.timestamp.desc()).all()
    
    print(f"DEBUG: include_aspects={include_aspects}, include_reviews={include_reviews}, reviews count={len(reviews)}")
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=1  # Center
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=12
    )
    review_style = ParagraphStyle(
        'ReviewStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8
    )
    
    # Title
    elements.append(Paragraph("Customer Review Insight AI", title_style))
    elements.append(Paragraph(f"Comprehensive Analysis Report", styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    # Metadata
    elements.append(Paragraph(f"<b>User:</b> {username}", styles['Normal']))
    elements.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    
    # Show date ranges if applicable
    if include_aspects and (aspects_start_date or aspects_end_date):
        date_range = f"{aspects_start_date or 'Start'} to {aspects_end_date or 'Now'}"
        elements.append(Paragraph(f"<b>Aspects Date Range:</b> {date_range}", styles['Normal']))
    
    elements.append(Paragraph(f"<b>Total Reviews:</b> {len(reviews)}", styles['Normal']))
    if include_reviews:
        count_text = "All" if review_count is None else str(review_count)
    elements.append(Spacer(1, 30))
    
    # === CATEGORY PERFORMANCE SUMMARY ===
    if include_aspects and category_summary:
        elements.append(Paragraph("Category Performance Overview", heading_style))
        elements.append(Spacer(1, 12))
        
        # Create category summary table
        cat_table_data = [['Category', 'Total', 'Positive', 'Negative', 'Neutral', 'Avg Score', 'Dominant']]
        
        for cat in category_summary:
            cat_table_data.append([
                cat['category_name'],
                str(cat['total_mentions']),
                f"{cat['positive']} ({cat['positive_percentage']}%)",
                f"{cat['negative']} ({cat['negative_percentage']}%)",
                f"{cat['neutral']} ({cat['neutral_percentage']}%)",
                f"{cat['avg_score']:.2f}",
                cat['dominant_sentiment']
            ])
        
        cat_table = Table(cat_table_data, colWidths=[1.5*inch, 0.7*inch, 1*inch, 1*inch, 1*inch, 0.8*inch, 0.9*inch])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(cat_table)
        elements.append(Spacer(1, 15))
        
        # Add category insights
        elements.append(Paragraph("<b>Category Insights:</b>", styles['Heading3']))
        elements.append(Spacer(1, 6))
        
        # Find best and worst categories
        if len(category_summary) > 0:
            best_cat = max(category_summary, key=lambda x: x['positive_percentage'])
            worst_cat = max(category_summary, key=lambda x: x['negative_percentage'])
            
            elements.append(Paragraph(
                f"• <b>Best Performing:</b> {best_cat['category_name']} ({best_cat['positive_percentage']}% positive)",
                styles['Normal']
            ))
            elements.append(Paragraph(
                f"• <b>Needs Attention:</b> {worst_cat['category_name']} ({worst_cat['negative_percentage']}% negative)",
                styles['Normal']
            ))
            elements.append(Spacer(1, 20))
    
    # Generate Overall Aspect Sentiment Scores Chart (if aspects exist and matplotlib available)
    if include_aspects and MATPLOTLIB_AVAILABLE and (categorized_summary or uncategorized_summary):
        try:
            # Combine both categorized and uncategorized aspects
            all_aspects = categorized_summary + uncategorized_summary
            
            if all_aspects:
                # Extract aspect names and scores
                aspect_names = [item['aspect'].replace('_', ' ').title() for item in all_aspects]
                scores = [item.get('average_sentiment_strength', 0) for item in all_aspects]
                
                # Create color array based on sentiment
                bar_colors = []
                for score in scores:
                    if score > 0:
                        bar_colors.append('#28a745')  # Green for positive
                    elif score < 0:
                        bar_colors.append('#dc3545')  # Red for negative
                    else:
                        bar_colors.append('#6c757d')  # Gray for neutral
                
                # Create VERTICAL bar chart to match web page (reduced size for PDF)
                fig, ax = plt.subplots(figsize=(7, 3.5))
                x_pos = range(len(aspect_names))
                
                # Create vertical bars
                bars = ax.bar(x_pos, scores, color=bar_colors, edgecolor='black', linewidth=1, width=0.6)
                
                # Set labels and title
                ax.set_xticks(x_pos)
                ax.set_xticklabels(aspect_names, rotation=45, ha='right', fontsize=9)
                ax.set_ylabel('Average Sentiment Score', fontsize=11, fontweight='bold')
                ax.set_title('Overall Aspect Sentiment Scores', fontsize=13, fontweight='bold', pad=15)
                
                # Zero line
                ax.axhline(y=0, color='black', linewidth=1.5, linestyle='-', alpha=0.7)
                
                # Set limits
                ax.set_ylim(-1, 1)
                
                # Grid
                ax.grid(True, axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
                ax.set_facecolor('#f8f9fa')
                
                # Add value labels on top of bars
                for i, (bar, score) in enumerate(zip(bars, scores)):
                    height = bar.get_height()
                    label_y = height + (0.05 if height >= 0 else -0.08)
                    va = 'bottom' if height >= 0 else 'top'
                    ax.text(bar.get_x() + bar.get_width()/2, label_y, f'{score:.2f}', 
                           ha='center', va=va, fontsize=9, fontweight='bold')
                
                plt.tight_layout()
                
                # Save to buffer
                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
                img_buffer.seek(0)
                plt.close()
                
                # Add to PDF
                elements.append(Paragraph("Overall Aspect Sentiment Scores", heading_style))
                img = Image(img_buffer, width=6.5*inch, height=max(3*inch, len(all_aspects) * 0.3*inch))
                elements.append(img)
                elements.append(Spacer(1, 20))
        except Exception as e:
            print(f"Error generating aspect sentiment scores chart: {e}")
    
    # Sentiment Trends chart removed - only Aspect Analysis and Reviews in PDF
    
    # Categorized Aspects Table (if user selected)
    if include_aspects and categorized_summary:
        elements.append(Paragraph("Categorized Aspects", heading_style))
        
        table_data = [['Aspect', 'Positive', 'Negative', 'Neutral', 'Total', 'Dominant']]
        for item in categorized_summary:
            table_data.append([
                item['aspect'],
                str(item['positive']),
                str(item['negative']),
                str(item.get('neutral', 0)),
                str(item['total_mentions']),
                item['dominant_sentiment']
            ])
        
        table = Table(table_data, colWidths=[2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    # Uncategorized Aspects Table (if user selected)
    if include_aspects and uncategorized_summary:
        elements.append(Paragraph("Uncategorized Aspects (Top 10)", heading_style))
        
        table_data = [['Aspect', 'Positive', 'Negative', 'Neutral', 'Total', 'Dominant']]
        for item in uncategorized_summary[:10]:
            table_data.append([
                item['aspect'],
                str(item['positive']),
                str(item['negative']),
                str(item.get('neutral', 0)),
                str(item['total_mentions']),
                item['dominant_sentiment']
            ])
        
        table = Table(table_data, colWidths=[2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    # Detailed Reviews Section (if user selected)
    if include_reviews and reviews:
        # Page Break before detailed reviews
        elements.append(PageBreak())
        
        elements.append(Paragraph("Detailed Reviews with Aspect Highlights", heading_style))
        elements.append(Spacer(1, 10))
        
        # Use review_count parameter (None means all reviews)
        reviews_to_show = reviews if review_count is None else reviews[:review_count]
        
        for idx, review in enumerate(reviews_to_show, 1):
            # Review header
            date_str = review.timestamp.strftime('%Y-%m-%d %H:%M') if review.timestamp else 'N/A'
            sentiment_color = '#28a745' if review.sentiment.upper() == 'POSITIVE' else '#dc3545' if review.sentiment.upper() == 'NEGATIVE' else '#6c757d'
            
            elements.append(Paragraph(
                f"<b>Review #{idx}</b> | Date: {date_str} | Sentiment: <font color='{sentiment_color}'><b>{review.sentiment}</b></font>",
                review_style
            ))
            
            # Review content
            elements.append(Paragraph(f"{review.content[:300]}{'...' if len(review.content) > 300 else ''}", review_style))
            
            # Aspects found
            if review.aspect_sentiments:
                aspects_text = "<b>Aspects:</b> "
                aspect_parts = []
                for asp in review.aspect_sentiments[:5]:  # Limit to 5 aspects
                    asp_color = '#28a745' if asp.sentiment.upper() == 'POSITIVE' else '#dc3545' if asp.sentiment.upper() == 'NEGATIVE' else '#6c757d'
                    aspect_parts.append(f"<font color='{asp_color}'>{asp.keyword_found}</font>")
                aspects_text += ", ".join(aspect_parts)
                elements.append(Paragraph(aspects_text, review_style))
            
            elements.append(Spacer(1, 12))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'comprehensive_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
        mimetype='application/pdf'
    )