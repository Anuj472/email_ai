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

# ✅ FIXED: Changed from /thread/ to /thread/<filename>
@file_bp.route('/thread/<filename>', methods=['GET'])
def get_thread_info(filename):
    """Get complete thread information for a file"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        return jsonify({
            'success': True,
            'thread_info': thread_info
        })

    except Exception as e:
        logger.error(f"Error getting thread info: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get thread info'}), 500

# ✅ FIXED: Changed from /content/ to /content/<filename>
@file_bp.route('/content/<filename>', methods=['GET'])
def get_file_content(filename):
    """Get full content of a file"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Get file metadata and full content
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

# ✅ FIXED: All other routes with similar pattern corrections...
@file_bp.route('/generate-reply/<filename>', methods=['POST'])
def generate_reply(filename):
    """Generate reply for a specific document with enhanced PDF support"""
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

        return jsonify({
            'success': True,
            'filename': filename,
            'subject': file_info.get('subject', ''),
            'document_content': text_content,
            'file_info': file_info,
            'show_dual_pane': True  # ✅ ADDED: Triggers dual-pane view
        })

    except Exception as e:
        logger.error(f"Error generating reply: {str(e)}")
        return jsonify({'success': False, 'error': 'Reply generation failed'}), 500


# Continue with other corrected routes...
@file_bp.route('/mark-replied/<filename>', methods=['POST'])
def mark_replied(filename):
    """Mark a file as having reply generated with final reply content"""
    try:
        data = request.get_json()
        reply_content = data.get('reply_content', '')

        if not reply_content:
            return jsonify({'success': False, 'error': 'Reply content is required'}), 400

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

# ✅ FIXED: All remaining routes with parameter corrections
@file_bp.route('/thread/<filename>/summary', methods=['GET'])
def get_thread_summary(filename):
    """Get a summary of the chat thread for a specific file"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        chat_history = thread_info.get('chat_history', [])

        # Calculate thread statistics
        total_messages = len(chat_history)
        user_messages = len([msg for msg in chat_history if msg.get('isUser', False)])
        ai_messages = len([msg for msg in chat_history if not msg.get('isUser', False)])
        email_replies = len([msg for msg in chat_history if msg.get('isReply', False)])

        # Get the latest activity timestamp
        latest_activity = None
        if chat_history:
            latest_message = max(chat_history, key=lambda x: x.get('timestamp', ''))
            latest_activity = latest_message.get('timestamp')

        return jsonify({
            'success': True,
            'thread_summary': {
                'filename': filename,
                'subject': thread_info.get('subject', ''),
                'thread_id': thread_info.get('thread_id', ''),
                'total_messages': total_messages,
                'user_messages': user_messages,
                'ai_messages': ai_messages,
                'email_replies_generated': email_replies,
                'has_final_reply': thread_info.get('has_reply', False),
                'latest_activity': latest_activity,
                'upload_date': thread_info.get('upload_date', ''),
                'due_date': thread_info.get('due_date', ''),
                'status': 'completed' if thread_info.get('has_reply', False) else 'active' if total_messages > 0 else 'pending'
            }
        })

    except Exception as e:
        logger.error(f"Error getting thread summary: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get thread summary'}), 500

@file_bp.route('/stats', methods=['GET'])
def get_file_statistics():
    """Get overall file and thread statistics"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])

        # Get all files
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

        # Calculate chat statistics
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
