from models.models import db, RawText

class TextService:
    @staticmethod
    def save_raw_text(content, user_id):
        """Save raw text for a user"""
        if not content.strip():
            return False, "Please enter some text before saving."
        
        new_text = RawText(content=content, user_id=user_id)
        db.session.add(new_text)
        db.session.commit()
        
        return True, "Raw text saved successfully!"
    
    @staticmethod
    def delete_raw_text(text_id, user_id):
        """Delete raw text"""
        text = RawText.query.filter_by(id=text_id, user_id=user_id).first()
        if not text:
            return False, "Text not found."
        
        db.session.delete(text)
        db.session.commit()
        return True, "Raw text deleted successfully!"
    
    @staticmethod
    def edit_raw_text(text_id, new_content, user_id):
        """Edit raw text"""
        text = RawText.query.filter_by(id=text_id, user_id=user_id).first()
        if not text:
            return False, "Text not found."
        
        text.content = new_content
        db.session.commit()
        return True, "Raw text updated successfully!"
    
    @staticmethod
    def get_raw_text(text_id, user_id):
        """Get raw text by ID"""
        return RawText.query.filter_by(id=text_id, user_id=user_id).first()
    
    @staticmethod
    def get_user_texts(user_id):
        """Get all texts for a user"""
        return RawText.query.filter_by(user_id=user_id).all()
