# nlp_processor.py
import spacy
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import re
from models import db, AspectCategory, AspectKeyword # Ensure AspectKeyword is imported here
from difflib import get_close_matches
import logging
from flask import current_app # Ensure current_app is imported

logger = logging.getLogger(__name__)

class NLPProcessor:
    _instance = None

    def __new__(cls):
        logger.debug("NLPProcessor __new__ called.")
        if cls._instance is None:
            logger.debug("Creating new NLPProcessor instance.")
            cls._instance = super(NLPProcessor, cls).__new__(cls)
            cls._instance.nlp = None
            cls._instance.sentiment_analyzer = None
            cls._instance.initialized = False
            cls._instance.sentiment_model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
            cls._instance.aspect_category_keywords = {} 
        else:
            logger.debug("Returning existing NLPProcessor instance.")
        return cls._instance

    def init_nlp(self):
        logger.debug("init_nlp called.")
        # Re-evaluate initialization state more strictly
        # If sentiment_analyzer is None, or not initialized, always try to initialize fully.
        if self.initialized and self.nlp is not None and self.sentiment_analyzer is not None:
            logger.info("NLP models appear already initialized and ready, skipping full re-initialization.")
            # Still ensure categories are loaded if they might have been cleared
            if not self.aspect_category_keywords: 
                self._load_aspect_categories() 
            return True

        logger.info("Performing full NLP model initialization...")
        try:
            logger.info("Loading spaCy model 'en_core_web_sm'...")
            self.nlp = spacy.load("en_core_web_sm")
            if "sentencizer" not in self.nlp.pipe_names:
                logger.info("Adding 'sentencizer' to spaCy pipeline.")
                self.nlp.add_pipe("sentencizer") 
            logger.info("spaCy model loaded.")

            logger.info(f"Loading Hugging Face sentiment model '{self.sentiment_model_name}'...")
            tokenizer = AutoTokenizer.from_pretrained(self.sentiment_model_name)
            model = AutoModelForSequenceClassification.from_pretrained(self.sentiment_model_name)
            device = 0 if torch.cuda.is_available() else -1
            self.sentiment_analyzer = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer, return_all_scores=True, device=device)
            logger.info("Hugging Face sentiment model loaded.")

            self._load_aspect_categories() # This method will now load keywords too

            self.initialized = True
            logger.info("All NLP models initialized successfully.")
            return True
        except Exception as e:
            logger.critical(f"Failed to initialize NLP models: {e}", exc_info=True)
            # Crucially, reset everything to None/empty on failure
            self.nlp = None 
            self.sentiment_analyzer = None 
            self.initialized = False
            self.aspect_category_keywords = {} 
            return False

    def _load_aspect_categories(self):
        logger.info("Loading predefined aspect categories and keywords from database...")
        try:
            # Always acquire app context here
            with current_app.app_context():
                categories = AspectCategory.query.options(db.joinedload(AspectCategory.keywords)).all()
                
                self.aspect_category_keywords = {}
                for category in categories:
                    self.aspect_category_keywords[category.id] = {
                        'name': category.name.lower(),
                        'keywords': [kw.keyword.lower() for kw in category.keywords]
                    }
                logger.info(f"Loaded {len(self.aspect_category_keywords)} aspect categories with keywords.")
                logger.debug(f"Aspect categories with keywords: {self.aspect_category_keywords}")
        except Exception as e:
            logger.error(f"Could not load aspect categories and keywords from DB. This might be normal if DB is not yet initialized or tables missing: {e}", exc_info=True)
            self.aspect_category_keywords = {}

    def _map_to_predefined_category(self, extracted_aspect_text):
        logger.debug(f"Attempting to map aspect: '{extracted_aspect_text}'")
        if not self.aspect_category_keywords:
            self._load_aspect_categories()
            if not self.aspect_category_keywords:
                logger.warning("No aspect categories or keywords loaded for mapping.")
                return None

        if not extracted_aspect_text:
            return None

        normalized_extracted_aspect = re.sub(r'[^a-z0-9\s]', ' ', extracted_aspect_text.lower()).strip()
        tokens = [t for t in normalized_extracted_aspect.split() if t]

        for category_id, cat_info in self.aspect_category_keywords.items():
            for keyword in cat_info['keywords']:
                if normalized_extracted_aspect == keyword:
                    logger.debug(f"Exact match found for '{extracted_aspect_text}' with keyword '{keyword}' for category '{cat_info['name']}' (ID: {category_id})")
                    return category_id
                
                if keyword in normalized_extracted_aspect:
                    logger.debug(f"Substring match found for '{extracted_aspect_text}' with keyword '{keyword}' for category '{cat_info['name']}' (ID: {category_id})")
                    return category_id

                if keyword in tokens:
                    logger.debug(f"Token match found for '{extracted_aspect_text}' (token: '{keyword}') for category '{cat_info['name']}' (ID: {category_id})")
                    return category_id
        
        close = get_close_matches(normalized_extracted_aspect, [info['name'] for info in self.aspect_category_keywords.values()], n=1, cutoff=0.8)
        if close:
            for category_id, cat_info in self.aspect_category_keywords.items():
                if cat_info['name'] == close[0]:
                    logger.debug(f"Fuzzy match found for '{extracted_aspect_text}' with category name '{close[0]}' (ID: {category_id})")
                    return category_id

        logger.debug(f"No predefined category found for aspect: '{extracted_aspect_text}'")
        return None

    def clean_text(self, text):
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        return text

    def _preprocess_text_for_spacy(self, text):
        text = re.sub(r'([.,!?;:])(?=\S)', r'\1 ', text)
        text = re.sub(r'(?<=\S)([.,!?;:])', r' \1', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def analyze_sentiment(self, text):
        logger.debug(f"analyze_sentiment called for text: '{text[:50]}...'")
        # ADDED CRITICAL CHECK: Ensure sentiment_analyzer is initialized HERE
        if not self.sentiment_analyzer:
            logger.warning("Sentiment analyzer is not initialized. Attempting re-initialization.")
            if not self.init_nlp(): # Try to re-initialize
                logger.error("Failed to initialize sentiment analyzer during analyze_sentiment call. Returning default (POSITIVE as fallback).")
                return {"label": "POSITIVE", "score": 0.0}
        
        # After attempting re-initialization, check again
        if not self.sentiment_analyzer:
            logger.error("Sentiment analyzer is still not initialized after re-attempt. Returning default (POSITIVE as fallback).")
            return {"label": "POSITIVE", "score": 0.0}

        try:
            results = self.sentiment_analyzer(text)
            logger.debug(f"Sentiment Analyzer Raw Results: {results}")

            if not results or not results[0]:
                logger.warning("Sentiment analyzer returned empty or invalid results. Returning default (POSITIVE as fallback).")
                return {"label": "POSITIVE", "score": 0.0}
            
            scores = {item['label']: item['score'] for item in results[0]}
            logger.debug(f"Extracted Scores Dict: {scores}")

            neg_score = scores.get('negative', 0.0)
            pos_score = scores.get('positive', 0.0)
            logger.debug(f"Individual Scores: Neg={neg_score}, Pos={pos_score}")

            final_label = 'POSITIVE'
            final_score = pos_score

            if neg_score > pos_score:
                final_label = 'NEGATIVE'
                final_score = neg_score
            else:
                final_label = 'POSITIVE'
                final_score = pos_score

            logger.debug(f"Final Sentiment: Label={final_label}, Score={final_score}")
            return {"label": final_label, "score": final_score}

        except Exception as e:
            logger.critical(f"Exception during sentiment analysis: {e}", exc_info=True)
            return {"label": "POSITIVE", "score": 0.0}

    def extract_aspects(self, text):
        logger.debug(f"extract_aspects called for text: '{text[:50]}...'")
        # ADDED CRITICAL CHECK: Ensure nlp model is initialized HERE
        if not self.nlp:
            logger.warning("spaCy NLP model not initialized for aspect extraction. Attempting re-initialization.")
            if not self.init_nlp(): # Try to re-initialize
                logger.error("Failed to initialize spaCy NLP model during extract_aspects call. Returning empty list.")
                return []
        
        # After attempting re-initialization, check again
        if not self.nlp:
            logger.error("spaCy NLP model is still not initialized after re-attempt. Returning empty list.")
            return []

        try:
            preprocessed_text = self._preprocess_text_for_spacy(text)
            logger.debug(f"Preprocessed text for spaCy: '{preprocessed_text[:50]}...'")

            doc = self.nlp(preprocessed_text)
            aspects_data = []
            
            for sent_idx, sent in enumerate(doc.sents):
                sentence_text = sent.text

                for chunk in sent.noun_chunks:
                    if len(chunk.text.strip()) <= 2 or chunk.root.pos_ in ["PRON"]:
                        continue

                    full_chunk_text = chunk.text.strip()
                    normalized_tokens = [token.lemma_.lower() for token in chunk if token.pos_ in ("NOUN", "PROPN")]
                    normalized_extracted_aspect = " ".join(normalized_tokens) if normalized_tokens else full_chunk_text.lower()

                    aspect_category_id = self._map_to_predefined_category(normalized_extracted_aspect)

                    chunk_start_in_sent = chunk.start_char - sent.start_char
                    chunk_end_in_sent = chunk.end_char - sent.start_char

                    context_start_char_in_sent = max(0, chunk_start_in_sent - 20)
                    context_end_char_in_sent = min(len(sentence_text), chunk_end_in_sent + 20)
                    
                    context_snippet = sentence_text[context_start_char_in_sent:context_end_char_in_sent].strip()

                    if not context_snippet or len(context_snippet) <= len(full_chunk_text) + 5:
                        context_snippet = sentence_text

                    match = re.search(re.escape(full_chunk_text), text) 
                    start_char_original = -1
                    end_char_original = -1

                    if match:
                        start_char_original = match.start()
                        end_char_original = match.end()
                    else:
                        logger.warning(f"Could not find exact match for preprocessed chunk '{full_chunk_text}' in original text '{text}' for offset mapping. Using approximate offsets.")
                        pass

                    aspects_data.append({
                        'raw_extracted_aspect': normalized_extracted_aspect,
                        'aspect_category_id': aspect_category_id,
                        'keyword_found': full_chunk_text,
                        'sentence': sentence_text,
                        'context_snippet': context_snippet,
                        'start_char': start_char_original,
                        'end_char': end_char_original
                    })
            logger.debug(f"Extracted {len(aspects_data)} aspects.")
            return aspects_data
        except Exception as e:
            logger.critical(f"Exception during aspect extraction: {e}", exc_info=True)
            return []

    def analyze_aspect_sentiment(self, aspect_text_or_sentence):
        logger.debug(f"analyze_aspect_sentiment called for text: '{aspect_text_or_sentence[:50]}...'")
        return self.analyze_sentiment(aspect_text_or_sentence)


    def highlight_review_aspects(self, review_content, aspects_data):
        # ... (this method remains unchanged) ...
        sorted_aspects = sorted(aspects_data, key=lambda x: x.start_char)

        highlighted_text = []
        last_idx = 0

        for aspect_obj in sorted_aspects:
            if aspect_obj.start_char is None or aspect_obj.end_char is None or \
               aspect_obj.start_char >= len(review_content) or aspect_obj.end_char > len(review_content) or \
               aspect_obj.start_char < 0 or aspect_obj.end_char < 0:
                logger.warning(f"Invalid aspect indices for review. Skipping aspect. "
                               f"start={aspect_obj.start_char}, end={aspect_obj.end_char}, "
                               f"review_len={len(review_content)}. Aspect: {aspect_obj.keyword_found}")
                continue 
            
            highlighted_text.append(review_content[last_idx:aspect_obj.start_char])

            actual_highlight_text = review_content[aspect_obj.start_char:aspect_obj.end_char]
            
            sentiment_class = f"highlight-{aspect_obj.sentiment.lower()}"
            highlighted_text.append(f'<span class="{sentiment_class}">{actual_highlight_text}</span>')
            
            last_idx = aspect_obj.end_char
        
        highlighted_text.append(review_content[last_idx:])

        return "".join(highlighted_text)

nlp_processor = NLPProcessor()