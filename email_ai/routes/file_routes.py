from flask import Blueprint, request, jsonify, current_app
from services.file_service import FileService
from services.ollama_service import OllamaService
import os
import logging

logger = logging.getLogger(__name__)
file_bp = Blueprint('files', __name__)

@file_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
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
                    'name': result['original_name'],
                    'filename': result['filename'],
                    'upload_date': result['upload_date'],
                    'due_date': result['due_date'],
                    'size': result['size']
                }
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500

@file_bp.route('/list', methods=['GET'])
def list_files():
    """List all uploaded files"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        files = file_service.get_file_list()
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to list files'}), 500

@file_bp.route('/analyze/<filename>', methods=['POST'])
def analyze_file(filename):
    """Analyze uploaded file content"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Extract text content
        if filename.lower().endswith('.pdf'):
            text_content = file_service.extract_pdf_text(filepath)
        else:
            return jsonify({'success': False, 'error': 'Unsupported file type'}), 400
        
        if not text_content:
            return jsonify({'success': False, 'error': 'Could not extract text'}), 400
        
        # Analyze with AI
        ollama_service = OllamaService()
        analysis_result = ollama_service.analyze_document(text_content)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'analysis': analysis_result.get('analysis', 'Analysis unavailable'),
            'text_preview': text_content[:500] + "..." if len(text_content) > 500 else text_content
        })
        
    except Exception as e:
        logger.error(f"Error analyzing file: {str(e)}")
        return jsonify({'success': False, 'error': 'Analysis failed'}), 500

@file_bp.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete uploaded file"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        success = file_service.delete_file(filename)
        
        if success:
            return jsonify({'success': True, 'message': 'File deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
            
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({'success': False, 'error': 'Deletion failed'}), 500
