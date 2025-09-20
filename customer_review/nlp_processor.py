import spacy
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import re

class NLPProcessor:
    _instance = None

    def __new__(cls):
        print("DEBUG: NLPProcessor __new__ called.")
        if cls._instance is None:
            print("DEBUG: Creating new NLPProcessor instance.")
            cls._instance = super(NLPProcessor, cls).__new__(cls)
            cls._instance.nlp = None
            cls._instance.sentiment_analyzer = None
            cls._instance.initialized = False
            cls._instance.sentiment_model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
        else:
            print("DEBUG: Returning existing NLPProcessor instance.")
        return cls._instance

    def init_nlp(self):
        print("DEBUG: init_nlp called.")
        if self.initialized:
            print("INFO: NLP models already initialized, skipping re-initialization.")
            return True

        try:
            print("INFO: Initializing NLP models for the first time...")
            print("INFO: Loading spaCy model 'en_core_web_sm'...")
            self.nlp = spacy.load("en_core_web_sm")
            if "sentencizer" not in self.nlp.pipe_names:
                print("INFO: Adding 'sentencizer' to spaCy pipeline.")
                self.nlp.add_pipe("sentencizer") 
            print("INFO: spaCy model loaded.")

            print(f"INFO: Loading Hugging Face sentiment model '{self.sentiment_model_name}'...")
            tokenizer = AutoTokenizer.from_pretrained(self.sentiment_model_name)
            model = AutoModelForSequenceClassification.from_pretrained(self.sentiment_model_name)
            self.sentiment_analyzer = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer, return_all_scores=True)
            print("INFO: Hugging Face sentiment model loaded.")

            self.initialized = True
            print("INFO: All NLP models initialized successfully.")
            return True
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize NLP models: {e}")
            self.initialized = False
            self.sentiment_analyzer = None 
            return False

    def clean_text(self, text):
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        return text

    def analyze_sentiment(self, text):
        print(f"DEBUG: analyze_sentiment called for text: '{text[:50]}...'")
        if not self.sentiment_analyzer:
            print("ERROR: Sentiment analyzer is not initialized or is None. Returning default NEUTRAL.")
            return {"label": "NEUTRAL", "score": 0.0}

        try:
            results = self.sentiment_analyzer(text)
            print(f"DEBUG: Sentiment Analyzer Raw Results: {results}")

            if not results or not results[0]:
                print("WARNING: Sentiment analyzer returned empty or invalid results. Returning default NEUTRAL.")
                return {"label": "NEUTRAL", "score": 0.0}
            
            scores = {item['label']: item['score'] for item in results[0]}
            print(f"DEBUG: Extracted Scores Dict: {scores}")

            neg_score = scores.get('negative', 0.0)
            neu_score = scores.get('neutral', 0.0)
            pos_score = scores.get('positive', 0.0)
            print(f"DEBUG: Individual Scores: Neg={neg_score}, Neu={neu_score}, Pos={pos_score}")

            POSITIVE_THRESHOLD = 0.75
            NEGATIVE_THRESHOLD = 0.75
            
            if pos_score >= POSITIVE_THRESHOLD and pos_score > neg_score:
                final_label = 'POSITIVE'
                final_score = pos_score
            elif neg_score >= NEGATIVE_THRESHOLD and neg_score > pos_score:
                final_label = 'NEGATIVE'
                final_score = neg_score
            else:
                final_label = 'NEUTRAL'
                final_score = max(neg_score, neu_score, pos_score) 
            
            print(f"DEBUG: Final Sentiment: Label={final_label}, Score={final_score}")
            return {"label": final_label, "score": final_score}

        except Exception as e:
            print(f"CRITICAL ERROR: Exception during sentiment analysis: {e}")
            return {"label": "NEUTRAL", "score": 0.0}

    def extract_aspects(self, text):
        print(f"DEBUG: extract_aspects called for text: '{text[:50]}...'")
        if not self.nlp:
            print("ERROR: spaCy model not initialized for aspect extraction. Returning empty list.")
            return []

        try:
            doc = self.nlp(text)
            aspects = []
            for sent in doc.sents:
                for chunk in sent.noun_chunks:
                    # Filter for meaningful noun chunks that are not just pronouns or very short
                    # and ensure the root is a noun or proper noun.
                    if len(chunk.text.strip()) > 2 and chunk.root.pos_ in ["NOUN", "PROPN"]:
                        aspects.append({
                            'aspect': chunk.root.text.lower(), # Store root text as the canonical aspect
                            'keyword_found': chunk.text, # The actual phrase found
                            'sentence': sent.text,
                            'start_char': chunk.start_char,
                            'end_char': chunk.end_char
                        })
            print(f"DEBUG: Extracted {len(aspects)} aspects.")
            return aspects
        except Exception as e:
            print(f"CRITICAL ERROR: Exception during aspect extraction: {e}")
            return []

    def analyze_aspect_sentiment(self, aspect_text):
        print(f"DEBUG: analyze_aspect_sentiment called for aspect: '{aspect_text}'")
        return self.analyze_sentiment(aspect_text)

    def highlight_review_aspects(self, review_content, aspects_data):
        """
        Highlights aspects within a review's content using <span> tags.
        Aspects_data should be a list of AspectSentiment objects from the database.
        """
        sorted_aspects = sorted(aspects_data, key=lambda x: x.start_char)

        highlighted_text = []
        last_idx = 0

        for aspect_obj in sorted_aspects:
            # The keyword_found should be what we highlight
            # `aspect_obj.start_char` and `aspect_obj.end_char` must correspond to `aspect_obj.keyword_found`
            
            # Defensive check: ensure indices are within bounds
            if aspect_obj.start_char >= len(review_content) or aspect_obj.end_char > len(review_content):
                print(f"WARNING: Aspect indices out of bounds for review ID {aspect_obj.raw_text_id}: "
                      f"start={aspect_obj.start_char}, end={aspect_obj.end_char}, "
                      f"review_len={len(review_content)}")
                continue # Skip this aspect if its indices are invalid

            # Add text before the current aspect
            highlighted_text.append(review_content[last_idx:aspect_obj.start_char])

            # Add the highlighted aspect
            sentiment_class = f"highlight-{aspect_obj.sentiment.lower()}"
            highlighted_text.append(f'<span class="{sentiment_class}">{review_content[aspect_obj.start_char:aspect_obj.end_char]}</span>')
            
            last_idx = aspect_obj.end_char
        
        # Add any remaining text after the last aspect
        highlighted_text.append(review_content[last_idx:])

        return "".join(highlighted_text)


# Create a singleton instance
print("DEBUG: Initializing nlp_processor singleton at module level.")
nlp_processor = NLPProcessor()