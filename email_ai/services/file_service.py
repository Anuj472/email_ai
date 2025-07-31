import os
import PyPDF2
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import random
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self.allowed_extensions = {'pdf', 'txt', 'docx'}
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def save_file(self, file) -> Dict:
        """Save uploaded file and return file info"""
        try:
            if not file or not self.allowed_file(file.filename):
                return {
                    'success': False,
                    'error': 'Invalid file type. Only PDF, TXT, and DOCX files are allowed.'
                }
            
            # Generate secure filename
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
            filename = timestamp + filename
            
            filepath = os.path.join(self.upload_folder, filename)
            file.save(filepath)
            
            return {
                'success': True,
                'filename': filename,
                'original_name': file.filename,
                'filepath': filepath,
                'upload_date': datetime.now().strftime('%Y-%m-%d'),
                'due_date': self._generate_due_date(),
                'size': os.path.getsize(filepath)
            }
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to save file'
            }
    
    def extract_pdf_text(self, filepath: str) -> str:
        """Extract text content from PDF file"""
        try:
            text_content = ""
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
            return text_content.strip()
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return ""
    
    def get_file_list(self) -> List[Dict]:
        """Get list of all uploaded files"""
        files = []
        try:
            for filename in os.listdir(self.upload_folder):
                if self.allowed_file(filename):
                    filepath = os.path.join(self.upload_folder, filename)
                    if os.path.isfile(filepath):
                        files.append({
                            'name': filename,
                            'original_name': filename.split('_', 2)[-1] if '_' in filename else filename,
                            'upload_date': datetime.fromtimestamp(
                                os.path.getctime(filepath)
                            ).strftime('%Y-%m-%d'),
                            'due_date': self._generate_due_date(),
                            'size': os.path.getsize(filepath)
                        })
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
        
        return sorted(files, key=lambda x: x['upload_date'], reverse=True)
    
    def delete_file(self, filename: str) -> bool:
        """Delete an uploaded file"""
        try:
            filepath = os.path.join(self.upload_folder, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False
    
    def _generate_due_date(self) -> str:
        """Generate a mock due date for demonstration"""
        days_ahead = random.randint(1, 30)
        due_date = datetime.now() + timedelta(days=days_ahead)
        return due_date.strftime('%Y-%m-%d')
