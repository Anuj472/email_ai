from flask import Blueprint, request, jsonify, current_app, send_from_directory
from services.file_service import FileService
from services.ollama_service import OllamaService
import os
import requests
import logging

logger = logging.getLogger(__name__)

file_bp = Blueprint('files', __name__)

@file_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload with subject extraction"""
    try:
        print("📤 Upload request received")
        
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        print(f"📁 File received: {file.filename}")

        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        result = file_service.save_file(file)

        if result['success']:
            print("✅ File uploaded successfully")
            return jsonify({
                'success': True,
                'message': 'File uploaded successfully',
                'file_info': {
                    'filename': result['filename'],
                    'subject': result['subject'],
                    'upload_date': result['upload_date'],
                    'due_date': result['due_date'],
                    'size': result['size'],
                    'has_reply': result['has_reply'],
                    'thread_id': result['thread_id']
                }
            })
        else:
            print(f"❌ Upload failed: {result['error']}")
            return jsonify({'success': False, 'error': result['error']}), 400

    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        print(f"❌ Exception in upload: {str(e)}")
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

@file_bp.route('/content/<filename>', methods=['GET'])
def get_file_content(filename):
    """Get full content of a file"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

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

@file_bp.route('/summarize/<filename>', methods=['POST'])
def summarize_document(filename):
    """Generate document summary with specified word limit"""
    try:
        data = request.get_json()
        word_limit = data.get('word_limit', 500)
        
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        file_info = file_service._get_file_metadata(filename)
        if not file_info:
            return jsonify({'success': False, 'error': 'File metadata not found'}), 404

        if filename.lower().endswith('.pdf'):
            text_content = file_service.extract_pdf_text(filepath)
        else:
            return jsonify({'success': False, 'error': 'Unsupported file type for summarization'}), 400

        if not text_content:
            return jsonify({'success': False, 'error': 'Could not extract text for summarization'}), 400

        summary_prompt = f"""Please provide a comprehensive summary of the following document in exactly {word_limit} words. 
        
        Document Content:
        {text_content[:4000]}...
        
        Instructions:
        - Write a clear, concise summary that captures the main points
        - Use approximately {word_limit} words (can be slightly under or over)
        - Structure the summary with clear paragraphs
        - Focus on key information, decisions, and important details
        - Write in a professional tone
        
        Summary:"""

        payload = {
            "model": current_app.config['OLLAMA_MODEL'],
            "prompt": summary_prompt,
            "stream": False,
            "options": {
                "temperature": 0.6,
                "num_predict": min(word_limit * 2, 1000)
            }
        }

        response = requests.post(
            f"{current_app.config['OLLAMA_BASE_URL']}/api/generate",
            json=payload,
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            summary = result.get('response', '').strip()
            summary = summary.replace('\n\n\n', '\n\n')
            
            return jsonify({
                'success': True,
                'summary': summary,
                'word_limit': word_limit,
                'document_subject': file_info.get('subject', ''),
                'filename': filename
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate summary'
            }), 500

    except Exception as e:
        logger.error(f"Error summarizing document: {str(e)}")
        return jsonify({'success': False, 'error': 'Summarization failed'}), 500

@file_bp.route('/generate-reply/<filename>', methods=['POST'])
def generate_reply(filename):
    """Generate reply for a specific document (triggers dual-pane view)"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        file_info = file_service._get_file_metadata(filename)
        if not file_info:
            return jsonify({'success': False, 'error': 'File metadata not found'}), 404

        if filename.lower().endswith('.pdf'):
            text_content = file_service.extract_pdf_text(filepath)
        else:
            return jsonify({'success': False, 'error': 'Unsupported file type'}), 400

        if not text_content:
            return jsonify({'success': False, 'error': 'Could not extract text'}), 400

        return jsonify({
            'success': True,
            'filename': filename,
            'subject': file_info.get('subject', ''),
            'document_content': text_content,
            'file_info': file_info,
            'show_dual_pane': True
        })

    except Exception as e:
        logger.error(f"Error generating reply: {str(e)}")
        return jsonify({'success': False, 'error': 'Reply generation failed'}), 500

@file_bp.route('/mark-replied/<filename>', methods=['POST'])
def mark_replied(filename):
    """Mark a file as completed - only move to completed if manually marked"""
    try:
        data = request.get_json()
        reply_content = data.get('reply_content', '')
        manual_completion = data.get('manual_completion', False)  # ✅ NEW: Check if manually marked

        if not reply_content:
            return jsonify({'success': False, 'error': 'Reply content is required'}), 400

        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        
        # ✅ FIXED: Only mark as replied if manually completed
        if manual_completion:
            success = file_service.mark_reply_generated(filename, reply_content)
            if success:
                return jsonify({
                    'success': True,
                    'message': 'File marked as completed successfully'
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to mark as completed'}), 400
        else:
            # ✅ For automatic email generation, don't move to completed section
            # Just save the chat message, don't change completion status
            return jsonify({
                'success': True,
                'message': 'Reply generated but not marked as completed'
            })

    except Exception as e:
        logger.error(f"Error marking as replied: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to mark as replied'}), 500


@file_bp.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete uploaded file and its metadata"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        success = file_service.delete_file(filename)

        if success:
            return jsonify({
                'success': True,
                'message': 'File deleted successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404

    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to delete file'}), 500

@file_bp.route('/stats', methods=['GET'])
def get_file_statistics():
    """Get overall file and thread statistics"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])

        all_files = []
        try:
            for filename in os.listdir(current_app.config['UPLOAD_FOLDER']):
                if file_service.allowed_file(filename) and not filename.endswith('.meta'):
                    file_info = file_service._get_file_metadata(filename)
                    if file_info:
                        all_files.append(file_info)
        except Exception as e:
            logger.error(f"Error reading files: {str(e)}")

        total_files = len(all_files)
        pending_files = len([f for f in all_files if not f.get('has_reply', False)])
        completed_files = len([f for f in all_files if f.get('has_reply', False)])

        total_messages = 0
        active_threads = 0

        for file_info in all_files:
            chat_history = file_info.get('chat_history', [])
            total_messages += len(chat_history)
            if len(chat_history) > 0:
                active_threads += 1

        return jsonify({
            'success': True,
            'statistics': {
                'total_files': total_files,
                'pending_files': pending_files,
                'completed_files': completed_files,
                'active_threads': active_threads,
                'total_chat_messages': total_messages,
                'completion_rate': round((completed_files / total_files * 100) if total_files > 0 else 0, 2)
            }
        })

    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get statistics'}), 500
    
@file_bp.route('/view/<filename>', methods=['GET'])
def view_pdf_file(filename):
    """Serve PDF file for viewing in browser"""
    try:
        from flask import send_from_directory
        
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
            
        if not filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Not a PDF file'}), 400
        
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'], 
            filename,
            mimetype='application/pdf',
            as_attachment=False
        )
        
    except Exception as e:
        logger.error(f"Error serving PDF: {str(e)}")
        return jsonify({'error': 'Failed to serve PDF'}), 500
