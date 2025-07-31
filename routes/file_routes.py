from flask import Blueprint, request, jsonify, current_app
from services.file_service import FileService
from services.ollama_service import OllamaService
import os
import logging

logger = logging.getLogger(__name__)
file_bp = Blueprint('files', __name__)

@file_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload with subject extraction"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        result = file_service.save_file(file)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'File uploaded successfully',
                'file_info': {
                    'filename': result['filename'],
                    'subject': result['subject'],
                    'upload_date': result['upload_date'],
                    'due_date': result['due_date'],
                    'size': result['size'],
                    'has_reply': result['has_reply']
                }
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500

@file_bp.route('/list', methods=['GET'])
def list_files():
    """List pending files (without replies) sorted by due date"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        files = file_service.get_file_list(include_replied=False)
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to list files'}), 500

@file_bp.route('/list/replied', methods=['GET'])
def list_replied_files():
    """List files that have replies generated"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        files = file_service.get_replied_files()
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        logger.error(f"Error listing replied files: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to list replied files'}), 500

@file_bp.route('/generate-reply/<filename>', methods=['POST'])
def generate_reply(filename):
    """Generate reply for a specific document"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Get file metadata
        file_info = file_service._get_file_metadata(filename)
        if not file_info:
            return jsonify({'success': False, 'error': 'File metadata not found'}), 404
        
        # Extract full text content
        if filename.lower().endswith('.pdf'):
            text_content = file_service.extract_pdf_text(filepath)
        else:
            return jsonify({'success': False, 'error': 'Unsupported file type'}), 400
        
        if not text_content:
            return jsonify({'success': False, 'error': 'Could not extract text'}), 400
        
        # Generate AI reply
        ollama_service = OllamaService()
        ai_result = ollama_service.generate_email_reply(text_content, {
            'subject': file_info.get('subject', ''),
            'urgency': 'normal',
            'tone': 'professional'
        })
        
        if ai_result.get('success'):
            reply_content = ai_result['response']
            return jsonify({
                'success': True,
                'filename': filename,
                'subject': file_info.get('subject', ''),
                'document_content': text_content,
                'generated_reply': reply_content,
                'file_info': file_info
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate reply',
                'fallback': ai_result.get('fallback', 'Could not generate reply')
            }), 500
        
    except Exception as e:
        logger.error(f"Error generating reply: {str(e)}")
        return jsonify({'success': False, 'error': 'Reply generation failed'}), 500

@file_bp.route('/mark-replied/<filename>', methods=['POST'])
def mark_replied(filename):
    """Mark a file as having reply generated"""
    try:
        data = request.get_json()
        reply_content = data.get('reply_content', '')
        
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        success = file_service.mark_reply_generated(filename, reply_content)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'File marked as replied successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to mark as replied'}), 400
            
    except Exception as e:
        logger.error(f"Error marking as replied: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to mark as replied'}), 500

@file_bp.route('/content/<filename>', methods=['GET'])
def get_file_content(filename):
    """Get full content of a file"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Get file metadata and content
        file_info = file_service._get_file_metadata(filename)
        text_content = file_service.extract_pdf_text(filepath) if filename.endswith('.pdf') else ""
        
        return jsonify({
            'success': True,
            'filename': filename,
            'content': text_content,
            'file_info': file_info
        })
        
    except Exception as e:
        logger.error(f"Error getting file content: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get file content'}), 500
