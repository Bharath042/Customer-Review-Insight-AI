# nlp_processor.py
import spacy
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import re
from models import db, Category, Aspect, AspectKeyword
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
                categories = Category.query.options(db.joinedload(Category.aspects).joinedload(Aspect.keywords)).all()
                self.aspect_category_keywords = {}
                for category in categories:
                    for aspect in category.aspects:
                        aspect_keywords = [kw.keyword.lower() for kw in aspect.keywords]
                        # Store by aspect_id for direct lookup
                        self.aspect_category_keywords[aspect.id] = {
                            'aspect_id': aspect.id,
                            'aspect_name': aspect.name,
                            'category_id': category.id,
                            'category_name': category.name,
                            'weightage': aspect.weightage,
                            'keywords': aspect_keywords
                        }
                logger.info(f"Loaded {len(self.aspect_category_keywords)} aspects with keywords from database.")
                logger.debug(f"Aspect keywords mapping: {self.aspect_category_keywords}")
        except Exception as e:
            logger.error(f"Could not load aspect categories and keywords from DB. This might be normal if DB is not yet initialized or tables missing: {e}", exc_info=True)
            self.aspect_category_keywords = {}

    def _map_to_predefined_category(self, extracted_aspect_text):
        """Maps extracted aspect text to a predefined Aspect ID and matched keyword."""
        logger.debug(f"Attempting to map aspect: '{extracted_aspect_text}'")
        if not self.aspect_category_keywords:
            self._load_aspect_categories()
            if not self.aspect_category_keywords:
                logger.warning("No aspect categories or keywords loaded for mapping.")
                return None, None

        if not extracted_aspect_text:
            return None, None

        normalized_extracted_aspect = re.sub(r'[^a-z0-9\s]', ' ', extracted_aspect_text.lower()).strip()
        tokens = [t for t in normalized_extracted_aspect.split() if t]

        # First pass: Check if the extracted text matches the aspect name itself
        for aspect_id, aspect_info in self.aspect_category_keywords.items():
            aspect_name_normalized = aspect_info['aspect_name'].lower()
            if normalized_extracted_aspect == aspect_name_normalized or aspect_name_normalized in tokens:
                logger.debug(f"✓ Aspect name match: '{extracted_aspect_text}' → Aspect '{aspect_info['aspect_name']}' (ID: {aspect_id})")
                return aspect_id, aspect_info['aspect_name'].lower()
        
        # Second pass: Check keywords
        for aspect_id, aspect_info in self.aspect_category_keywords.items():
            for keyword in aspect_info['keywords']:
                # Exact match
                if normalized_extracted_aspect == keyword:
                    logger.debug(f"✓ Exact match: '{extracted_aspect_text}' → Aspect '{aspect_info['aspect_name']}' (ID: {aspect_id}), keyword: '{keyword}'")
                    return aspect_id, keyword
                
                # Substring match
                if keyword in normalized_extracted_aspect:
                    logger.debug(f"✓ Substring match: '{extracted_aspect_text}' contains '{keyword}' → Aspect '{aspect_info['aspect_name']}' (ID: {aspect_id})")
                    return aspect_id, keyword

                # Token match
                if keyword in tokens:
                    logger.debug(f"✓ Token match: '{extracted_aspect_text}' has token '{keyword}' → Aspect '{aspect_info['aspect_name']}' (ID: {aspect_id})")
                    return aspect_id, keyword
        
        # Fuzzy match against aspect names
        aspect_names = [info['aspect_name'].lower() for info in self.aspect_category_keywords.values()]
        close = get_close_matches(normalized_extracted_aspect, aspect_names, n=1, cutoff=0.8)
        if close:
            for aspect_id, aspect_info in self.aspect_category_keywords.items():
                if aspect_info['aspect_name'].lower() == close[0]:
                    logger.debug(f"✓ Fuzzy match: '{extracted_aspect_text}' → Aspect '{aspect_info['aspect_name']}' (ID: {aspect_id})")
                    return aspect_id, aspect_info['aspect_name']

        logger.debug(f"✗ No match found for aspect: '{extracted_aspect_text}'")
        return None, None

    def clean_text(self, text):
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        return text

    def _preprocess_text_for_spacy(self, text):
        text = re.sub(r'([.,!?;:])(?=\S)', r'\1 ', text)
        text = re.sub(r'(?<=\S)([.,!?;:])', r' \1', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def analyze_sentiment(self, text, aspect_keyword=None):
        logger.debug(f"analyze_sentiment called for text: '{text[:50]}...' (aspect: {aspect_keyword})")
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

        # Check for strong neutral phrases first (only exact matches)
        text_lower = text.lower()
        strong_neutral_phrases = [
            'neither good nor bad', 'neither cheap nor expensive', 
            'neither positive nor negative', 'neither great nor terrible'
        ]
        
        # Only override for very strong neutral indicators
        for phrase in strong_neutral_phrases:
            if phrase in text_lower:
                logger.debug(f"Strong neutral phrase '{phrase}' found in text. Returning NEUTRAL.")
                return {"label": "NEUTRAL", "score": 0.7}
        
        # Check for clearly negative price-related phrases
        negative_price_patterns = [
            ('high', ['price', 'cost', 'expensive']),
            ('expensive', ['price', 'cost', 'high']),
            ('overpriced', []),
            ('costly', []),
            ('pricey', [])
        ]
        
        # Check if analyzing a price-related aspect
        is_price_aspect = aspect_keyword and any(word in aspect_keyword.lower() for word in ['price', 'cost', 'pricing'])
        logger.debug(f"Price aspect check: aspect_keyword={aspect_keyword}, is_price_aspect={is_price_aspect}")
        
        # Check for softeners that make it neutral instead of negative
        softeners = ['a bit', 'a little', 'slightly', 'somewhat', 'kind of', 'sort of', 'fairly', 'rather']
        has_softener = any(softener in text_lower for softener in softeners)
        
        for neg_word, context_words in negative_price_patterns:
            if neg_word in text_lower:
                logger.debug(f"Found '{neg_word}' in text. Checking if price-related...")
                # Check if it's about price/cost (either in text OR analyzing price aspect)
                if is_price_aspect or not context_words or any(ctx in text_lower for ctx in context_words):
                    logger.debug(f"Price context confirmed. Checking negation and softeners...")
                    # Check for negation (e.g., "not high")
                    if 'not ' + neg_word in text_lower or "n't " + neg_word in text_lower:
                        logger.debug(f"Negation found, skipping.")
                        continue
                    # Check for softeners (e.g., "a bit high")
                    if has_softener:
                        logger.debug(f"Softener found ('{[s for s in softeners if s in text_lower]}'), treating as neutral, skipping negative override.")
                        continue
                    # Strong negative without softeners
                    logger.info(f"✓ NEGATIVE PRICE DETECTED: '{neg_word}' (aspect: {aspect_keyword}, text: '{text_lower}'). Returning NEGATIVE.")
                    return {"label": "NEGATIVE", "score": 0.75}
        
        # Check for single neutral keywords (but only if they're the main descriptor)
        neutral_keywords = ['average', 'okay', 'ok', 'standard', 'normal', 'typical', 'usual', 'regular', 'moderate']
        
        # Only apply if the keyword is prominent and not mixed with strong positive/negative words
        has_neutral_keyword = any(keyword in text_lower for keyword in neutral_keywords)
        has_strong_negative = any(word in text_lower for word in ['terrible', 'awful', 'horrible', 'worst', 'disappointing', 'poor', 'bad'])
        has_strong_positive = any(word in text_lower for word in ['excellent', 'amazing', 'great', 'awesome', 'fantastic', 'perfect', 'wonderful'])
        
        if has_neutral_keyword and not has_strong_negative and not has_strong_positive:
            logger.debug(f"Neutral keyword found without strong sentiment words. Returning NEUTRAL.")
            return {"label": "NEUTRAL", "score": 0.7}

        try:
            results = self.sentiment_analyzer(text)
            logger.debug(f"Sentiment Analyzer Raw Results: {results}")

            if not results or not results[0]:
                logger.warning("Sentiment analyzer returned empty or invalid results. Returning default (POSITIVE as fallback).")
                return {"label": "POSITIVE", "score": 0.0}
            
            scores = {item['label']: item['score'] for item in results[0]}
            logger.debug(f"Extracted Scores Dict: {scores}")

            neg_score = scores.get('negative', 0.0)
            neu_score = scores.get('neutral', 0.0)
            pos_score = scores.get('positive', 0.0)
            logger.debug(f"Individual Scores: Neg={neg_score}, Neu={neu_score}, Pos={pos_score}")

            # Determine sentiment based on highest score
            max_score = max(neg_score, neu_score, pos_score)
            
            # Only prefer neutral if it's clearly the highest OR if all scores are very close
            score_diff = max_score - min(neg_score, neu_score, pos_score)
            
            if max_score == neu_score and neu_score > max(neg_score, pos_score):
                # Neutral is clearly the highest
                final_label = 'NEUTRAL'
                final_score = neu_score
            elif score_diff < 0.1:
                # All scores are very close, prefer neutral
                final_label = 'NEUTRAL'
                final_score = neu_score
            elif max_score == pos_score:
                final_label = 'POSITIVE'
                final_score = pos_score
            elif max_score == neg_score:
                final_label = 'NEGATIVE'
                final_score = neg_score
            else:
                final_label = 'NEUTRAL'
                final_score = neu_score

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
                seen_aspects_in_sentence = set()  # Track which aspects we've already found in this sentence

                for chunk in sent.noun_chunks:
                    if len(chunk.text.strip()) <= 2 or chunk.root.pos_ in ["PRON"]:
                        continue

                    full_chunk_text = chunk.text.strip()
                    normalized_tokens = [token.lemma_.lower() for token in chunk if token.pos_ in ("NOUN", "PROPN")]
                    normalized_extracted_aspect = " ".join(normalized_tokens) if normalized_tokens else full_chunk_text.lower()

                    aspect_category_id, matched_keyword = self._map_to_predefined_category(normalized_extracted_aspect)
                    
                    # Skip if no aspect matched
                    if not aspect_category_id:
                        continue
                    
                    # Skip if we've already found this aspect in this sentence
                    if aspect_category_id in seen_aspects_in_sentence:
                        logger.debug(f"Skipping duplicate aspect '{matched_keyword}' (Aspect ID: {aspect_category_id}) in same sentence")
                        continue
                    
                    # Mark this aspect as seen in this sentence
                    seen_aspects_in_sentence.add(aspect_category_id)

                    chunk_start_in_sent = chunk.start_char - sent.start_char
                    chunk_end_in_sent = chunk.end_char - sent.start_char

                    context_start_char_in_sent = max(0, chunk_start_in_sent - 20)
                    context_end_char_in_sent = min(len(sentence_text), chunk_end_in_sent + 20)
                    
                    context_snippet = sentence_text[context_start_char_in_sent:context_end_char_in_sent].strip()

                    if not context_snippet or len(context_snippet) <= len(matched_keyword) + 5:
                        context_snippet = sentence_text

                    # Find the position of the matched keyword in the original text
                    # Search for the keyword within the sentence context
                    keyword_pattern = re.compile(re.escape(matched_keyword), re.IGNORECASE)
                    match = keyword_pattern.search(text)
                    start_char_original = -1
                    end_char_original = -1

                    if match:
                        start_char_original = match.start()
                        end_char_original = match.end()
                    else:
                        logger.warning(f"Could not find exact match for keyword '{matched_keyword}' in original text. Skipping.")
                        continue

                    aspects_data.append({
                        'raw_extracted_aspect': normalized_extracted_aspect,
                        'aspect_category_id': aspect_category_id,
                        'keyword_found': matched_keyword,
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

    def analyze_aspect_sentiment(self, sentence, aspect_keyword=None, aspect_start=None, aspect_end=None):
        """
        Analyzes sentiment for an aspect within a sentence.
        Extracts a context window around the aspect for more accurate sentiment.
        """
        if not aspect_keyword or aspect_start is None or aspect_end is None:
            # Fallback: analyze entire sentence
            logger.debug(f"Analyzing entire sentence (no aspect position): '{sentence[:50]}...'")
            return self.analyze_sentiment(sentence, aspect_keyword=aspect_keyword)
        
        # Extract context window: aspect + surrounding words (5 words before and after)
        words = sentence.split()
        aspect_words = aspect_keyword.split()
        
        # Find aspect position in words
        aspect_word_start = None
        for i in range(len(words) - len(aspect_words) + 1):
            if ' '.join(words[i:i+len(aspect_words)]).lower() == aspect_keyword.lower():
                aspect_word_start = i
                break
        
        if aspect_word_start is not None:
            # Extract 4 words before and 4 words after the aspect
            context_start = max(0, aspect_word_start - 4)
            context_end = min(len(words), aspect_word_start + len(aspect_words) + 4)
            
            # Stop at conjunctions like "but", "however", "although" to avoid mixing sentiments
            # BUT only check AFTER the aspect, not before
            conjunctions = ['but', 'however', 'although', 'though', 'yet', 'whereas']
            
            # Only check words AFTER aspect for conjunctions (to separate different sentiments)
            for i in range(aspect_word_start + len(aspect_words), context_end):
                if words[i].lower().rstrip(',') in conjunctions:
                    context_end = i
                    break
            
            context = ' '.join(words[context_start:context_end])
            logger.debug(f"Aspect '{aspect_keyword}' context window: '{context}'")
            return self.analyze_sentiment(context, aspect_keyword=aspect_keyword)
        else:
            # Fallback if aspect not found in sentence
            logger.debug(f"Aspect '{aspect_keyword}' not found in sentence, analyzing full sentence")
            return self.analyze_sentiment(sentence, aspect_keyword=aspect_keyword)


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
            
            # Add inline styles to match user page highlighting
            inline_style = ""
            if aspect_obj.sentiment == "POSITIVE":
                inline_style = "background-color: rgba(40, 167, 69, 0.2); color: #28a745; font-weight: bold;"
            elif aspect_obj.sentiment == "NEGATIVE":
                inline_style = "background-color: rgba(220, 53, 69, 0.2); color: #dc3545; font-weight: bold;"
            elif aspect_obj.sentiment == "NEUTRAL":
                inline_style = "background-color: rgba(108, 117, 125, 0.35); color: #adb5bd; font-weight: bold; border: 1px solid rgba(108, 117, 125, 0.4);"
            
            highlighted_text.append(f'<span class="highlight-aspect" style="{inline_style}">{actual_highlight_text}</span>')
            
            last_idx = aspect_obj.end_char
        
        highlighted_text.append(review_content[last_idx:])

        return "".join(highlighted_text)

nlp_processor = NLPProcessor()