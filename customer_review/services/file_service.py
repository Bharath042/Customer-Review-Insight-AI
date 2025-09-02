import os
from models.models import db, UploadedFile
from flask import flash

class FileService:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
    
    def upload_csv_file(self, file, user_id, username):
        """Upload a CSV file for a user"""
        if not file.filename.endswith('.csv'):
            return False, "Only CSV files are allowed."
        
        # Create user folder
        user_folder = os.path.join(self.upload_folder, username)
        os.makedirs(user_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(user_folder, file.filename)
        file.save(file_path)
        
        # Save metadata in DB
        new_file = UploadedFile(filename=file.filename, user_id=user_id)
        db.session.add(new_file)
        db.session.commit()
        
        return True, "CSV uploaded successfully!"
    
    def delete_file(self, file_id, user_id):
        """Delete a file"""
        file = UploadedFile.query.filter_by(id=file_id, user_id=user_id).first()
        if not file:
            return False, "File not found."
        
        db.session.delete(file)
        db.session.commit()
        return True, "File deleted successfully!"
    
    def edit_file(self, file_id, new_name, user_id):
        """Rename a file"""
        file = UploadedFile.query.filter_by(id=file_id, user_id=user_id).first()
        if not file:
            return False, "File not found."
        
        if not new_name.strip():
            return False, "Invalid filename!"
        
        file.filename = new_name
        db.session.commit()
        return True, "File renamed successfully!"
    
    def get_user_files(self, user_id):
        """Get all files for a user"""
        return UploadedFile.query.filter_by(user_id=user_id).all()
