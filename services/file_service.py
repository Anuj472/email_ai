import os
import PyPDF2
import re
import json
import uuid
import random
import logging
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self.allowed_extensions = {'pdf', 'txt', 'docx'}

    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def extract_subject_from_text(self, text_content: str) -> str:
        """Extract subject/title from document content"""
        try:
            # Look for common email subject patterns
            subject_patterns = [
                r'Subject:\s*(.+?)(?:\n|$)',
                r'RE:\s*(.+?)(?:\n|$)',
                r'FW:\s*(.+?)(?:\n|$)',
                r'SUBJECT:\s*(.+?)(?:\n|$)'
            ]

            for pattern in subject_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    subject = match.group(1).strip()
                    return subject[:100] if len(subject) > 100 else subject

            # If no subject found, extract from first meaningful line
            lines = text_content.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 10 and not line.startswith(('Date:', 'From:', 'To:')):
                    return (line[:100] + '...') if len(line) > 100 else line

            return "Untitled Document"

        except Exception as e:
            logger.error(f"Error extracting subject: {str(e)}")
            return "Subject Extraction Failed"

    def save_file(self, file) -> Dict:
        """Save uploaded file and return file info with extracted subject"""
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

            # Extract text and subject
            text_content = self.extract_pdf_text(filepath) if filepath.endswith('.pdf') else ""
            subject = self.extract_subject_from_text(text_content)

            file_info = {
                'success': True,
                'filename': filename,
                'original_name': file.filename,
                'filepath': filepath,
                'upload_date': datetime.now().strftime('%Y-%m-%d'),
                'due_date': self._generate_due_date(),
                'size': os.path.getsize(filepath),
                'subject': subject,
                'content_preview': text_content[:200] + "..." if len(text_content) > 200 else text_content,
                'full_content': text_content,  # ✅ ADDED
                'has_reply': False,
                'reply_generated_date': None,
                'thread_id': uuid.uuid4().hex[:8],  # ✅ ADDED
                'chat_history': [],  # ✅ ADDED
                'final_reply': None  # ✅ ADDED
            }

            # Save metadata
            self._save_file_metadata(filename, file_info)
            return file_info

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

    def get_file_list(self, include_replied: bool = False) -> List[Dict]:
        """Get list of all uploaded files sorted by due date"""
        files = []
        try:
            for filename in os.listdir(self.upload_folder):
                if self.allowed_file(filename) and not filename.endswith('.meta'):
                    file_info = self._get_file_metadata(filename)
                    if file_info:
                        # Filter based on reply status
                        if include_replied or not file_info.get('has_reply', False):
                            files.append(file_info)
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")

        # Sort by due date (ascending - closest due date first)
        return sorted(files, key=lambda x: datetime.strptime(x['due_date'], '%Y-%m-%d'))

    def get_replied_files(self) -> List[Dict]:
        """Get list of files that have replies generated"""
        files = []
        try:
            for filename in os.listdir(self.upload_folder):
                if self.allowed_file(filename) and not filename.endswith('.meta'):
                    file_info = self._get_file_metadata(filename)
                    if file_info and file_info.get('has_reply', False):
                        files.append(file_info)
        except Exception as e:
            logger.error(f"Error listing replied files: {str(e)}")

        return sorted(files, key=lambda x: x.get('reply_generated_date', ''), reverse=True)

    # ✅ ADDED MISSING METHODS
    def get_thread_info(self, filename: str) -> Dict:
        """Get complete thread information for a file"""
        try:
            file_info = self._get_file_metadata(filename)
            if not file_info:
                return None

            # Ensure full content is available
            filepath = os.path.join(self.upload_folder, filename)
            if os.path.exists(filepath) and not file_info.get('full_content'):
                text_content = self.extract_pdf_text(filepath) if filename.endswith('.pdf') else ""
                file_info['full_content'] = text_content
                self._save_file_metadata(filename, file_info)

            return file_info
        except Exception as e:
            logger.error(f"Error getting thread info: {str(e)}")
            return None

    def save_chat_message(self, filename: str, message: Dict) -> bool:
        """Save a chat message to thread history"""
        try:
            file_info = self._get_file_metadata(filename)
            if not file_info:
                return False

            # Add timestamp to message
            message['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Initialize chat history if not exists
            if 'chat_history' not in file_info:
                file_info['chat_history'] = []

            file_info['chat_history'].append(message)
            self._save_file_metadata(filename, file_info)
            return True

        except Exception as e:
            logger.error(f"Error saving chat message: {str(e)}")
            return False

    def get_chat_history(self, filename: str) -> List[Dict]:
        """Get chat history for a thread"""
        try:
            file_info = self._get_file_metadata(filename)
            if file_info:
                return file_info.get('chat_history', [])
            return []
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            return []

    def clear_chat_history(self, filename: str) -> bool:
        """Clear chat history for a thread"""
        try:
            file_info = self._get_file_metadata(filename)
            if file_info:
                file_info['chat_history'] = []
                self._save_file_metadata(filename, file_info)
                return True
            return False
        except Exception as e:
            logger.error(f"Error clearing chat history: {str(e)}")
            return False

    def mark_reply_generated(self, filename: str, reply_content: str) -> bool:
        """Mark a file as having a reply generated"""
        try:
            file_info = self._get_file_metadata(filename)
            if file_info:
                file_info['has_reply'] = True
                file_info['reply_generated_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                file_info['final_reply'] = reply_content
                self._save_file_metadata(filename, file_info)
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking reply generated: {str(e)}")
            return False

    def _save_file_metadata(self, filename: str, metadata: Dict):
        """Save file metadata to a .meta file"""
        try:
            meta_filename = filename + '.meta'
            meta_filepath = os.path.join(self.upload_folder, meta_filename)
            with open(meta_filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {str(e)}")

    def _get_file_metadata(self, filename: str) -> Dict:
        """Get file metadata from .meta file"""
        try:
            meta_filename = filename + '.meta'
            meta_filepath = os.path.join(self.upload_folder, meta_filename)
            
            if os.path.exists(meta_filepath):
                with open(meta_filepath, 'r') as f:
                    return json.load(f)
            else:
                # Generate metadata for existing files
                filepath = os.path.join(self.upload_folder, filename)
                if os.path.exists(filepath):
                    text_content = self.extract_pdf_text(filepath) if filename.endswith('.pdf') else ""
                    subject = self.extract_subject_from_text(text_content)
                    
                    metadata = {
                        'filename': filename,
                        'original_name': filename.split('_', 2)[-1] if '_' in filename else filename,
                        'upload_date': datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d'),
                        'due_date': self._generate_due_date(),
                        'size': os.path.getsize(filepath),
                        'subject': subject,
                        'content_preview': text_content[:200] + "..." if len(text_content) > 200 else text_content,
                        'full_content': text_content,  # ✅ ADDED
                        'has_reply': False,
                        'reply_generated_date': None,
                        'thread_id': uuid.uuid4().hex[:8],  # ✅ ADDED
                        'chat_history': [],  # ✅ ADDED
                        'final_reply': None  # ✅ ADDED
                    }
                    
                    self._save_file_metadata(filename, metadata)
                    return metadata
            return None

        except Exception as e:
            logger.error(f"Error getting metadata: {str(e)}")
            return None

    def delete_file(self, filename: str) -> bool:
        """Delete an uploaded file and its metadata"""
        try:
            filepath = os.path.join(self.upload_folder, filename)
            meta_filepath = os.path.join(self.upload_folder, filename + '.meta')
            
            success = False
            if os.path.exists(filepath):
                os.remove(filepath)
                success = True
                
            if os.path.exists(meta_filepath):
                os.remove(meta_filepath)
                
            return success
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False

    def _generate_due_date(self) -> str:
        """Generate a mock due date for demonstration"""
        days_ahead = random.randint(1, 30)
        due_date = datetime.now() + timedelta(days=days_ahead)
        return due_date.strftime('%Y-%m-%d')
    # Add this method to your existing FileService class

def get_conversation_summary(self, filename: str) -> Dict:
    """Get a summary of the conversation context for better memory"""
    try:
        file_info = self._get_file_metadata(filename)
        if not file_info:
            return None
        
        chat_history = file_info.get('chat_history', [])
        
        # Build conversation summary
        user_messages = [msg for msg in chat_history if msg.get('isUser', False)]
        ai_responses = [msg for msg in chat_history if not msg.get('isUser', False)]
        email_replies = [msg for msg in chat_history if msg.get('isReply', False)]
        
        # Extract key information
        all_user_text = ' '.join([msg.get('text', '') for msg in user_messages])
        
        summary = {
            'total_messages': len(chat_history),
            'user_messages_count': len(user_messages),
            'ai_responses_count': len(ai_responses),
            'email_replies_count': len(email_replies),
            'latest_user_requests': [msg.get('text', '') for msg in user_messages[-3:]],
            'conversation_keywords': self._extract_keywords(all_user_text),
            'last_activity': chat_history[-1].get('timestamp') if chat_history else None
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting conversation summary: {str(e)}")
        return None

def _extract_keywords(self, text: str) -> List[str]:
    """Extract important keywords from conversation"""
    import re
    
    # Common important patterns
    patterns = [
        r'\b(?:urgent|important|asap|deadline|meeting|project|proposal|budget|contract)\b',
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # dates
        r'\$[\d,]+\.?\d*',  # money
        r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'  # names
    ]
    
    keywords = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        keywords.extend(matches)
    
    return list(set(keywords))[:10]  # Return top 10 unique keywords
