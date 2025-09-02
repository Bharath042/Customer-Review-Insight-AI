import os

def ensure_user_folder_exists(upload_folder, username):
    """Ensure user's upload folder exists"""
    user_folder = os.path.join(upload_folder, username)
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def is_csv_file(filename):
    """Check if file is a CSV file"""
    return filename.lower().endswith('.csv')
