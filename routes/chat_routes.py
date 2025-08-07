from flask import Blueprint, request, jsonify, current_app
from services.ollama_service import OllamaService
from services.file_service import FileService
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/thread', methods=['POST'])
def handle_chat_thread():
    """Enhanced chat thread with professional prompts and word count control"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        filename = data.get('filename', '')
        enhanced_prompts = data.get('enhanced_prompts', False)

        if not user_message:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

        if not filename:
            return jsonify({'success': False, 'error': 'Filename is required'}), 400

        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Save user message
        user_msg = {
            'text': user_message,
            'isUser': True,
            'type': 'user_message',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        file_service.save_chat_message(filename, user_msg)

        chat_history = file_service.get_chat_history(filename)
        document_content = thread_info.get('full_content', '')

        # ✅ NEW: Detect word count requirements
        word_count_match = re.search(r'(?:in|about|around|approximately)\s+(\d+)\s+words?', user_message, re.IGNORECASE)
        requested_words = int(word_count_match.group(1)) if word_count_match else None

        # ✅ NEW: Enhanced context with professional prompts
        context = {
            'document_subject': thread_info.get('subject', ''),
            'document_content': document_content,
            'user_request': user_message,
            'chat_history': chat_history,
            'thread_id': thread_info.get('thread_id', ''),
            'enhanced_prompts': enhanced_prompts,
            'requested_word_count': requested_words,
            'professional_domains': [
                'software_development',
                'electronics_engineering', 
                'systems_architecture',
                'technical_documentation',
                'coding_best_practices'
            ]
        }

        ollama_service = OllamaService()

        # Check for email request
        email_keywords = [
            'generate reply', 'create reply', 'write reply', 'email reply',
            'respond to', 'draft reply', 'compose reply', 'reply to this',
            'generate email', 'create email', 'write email', 'draft email',
            'professional reply', 'formal reply'
        ]
        
        is_email_request = any(keyword in user_message.lower() for keyword in email_keywords)

        if is_email_request:
            result = ollama_service.generate_email_reply_with_enhanced_context(
                document_content,
                user_message,
                context
            )
        else:
            # ✅ NEW: Enhanced general chat with professional prompts
            result = ollama_service.generate_professional_response(
                user_message,
                document_content,
                context
            )

        if result.get('success'):
            ai_msg = {
                'text': result['response'],
                'isUser': False,
                'type': 'ai_response',
                'isReply': is_email_request,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'word_count': result.get('word_count', 0),
                'response_type': result.get('response_type', 'general')
            }

            file_service.save_chat_message(filename, ai_msg)

            return jsonify({
                'success': True,
                'response': result['response'],
                'is_email_reply': is_email_request,
                'word_count': result.get('word_count', 0),
                'response_type': result.get('response_type', 'general'),
                'thread_id': thread_info.get('thread_id', ''),
                'enhanced_mode': enhanced_prompts
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to generate response')
            }), 500

    except Exception as e:
        logger.error(f"Error in enhanced chat thread: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Enhanced chat processing error'
        }), 500

# Keep other existing routes...
@chat_bp.route('/thread/<filename>/history', methods=['GET'])
def get_thread_history(filename):
    """Get chat history with enhanced metadata"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        chat_history = thread_info.get('chat_history', [])
        
        # Calculate conversation statistics
        total_words = sum(msg.get('word_count', 0) for msg in chat_history if not msg.get('isUser'))
        avg_response_length = total_words // len([msg for msg in chat_history if not msg.get('isUser')]) if chat_history else 0
        
        return jsonify({
            'success': True,
            'thread_id': thread_info.get('thread_id', ''),
            'subject': thread_info.get('subject', ''),
            'chat_history': chat_history,
            'conversation_stats': {
                'total_messages': len(chat_history),
                'total_words_generated': total_words,
                'average_response_length': avg_response_length,
                'professional_mode': True
            },
            'context_depth': len(chat_history)
        })

    except Exception as e:
        logger.error(f"Error getting enhanced thread history: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get thread history'}), 500

@chat_bp.route('/health', methods=['GET'])
def health_check():
    """Enhanced health check with professional capabilities"""
    try:
        ollama_service = OllamaService()
        health_status = ollama_service.check_health()

        return jsonify({
            'service': 'enhanced_chat',
            'ollama_health': health_status,
            'config': {
                'model': current_app.config['OLLAMA_MODEL'],
                'base_url': current_app.config['OLLAMA_BASE_URL']
            },
            'features': {
                'professional_prompts': True,
                'word_count_control': True,
                'technical_expertise': True,
                'enhanced_context': True,
                'response_range': '50-3000 words'
            },
            'supported_domains': [
                'Software Development',
                'Electronics Engineering',
                'Systems Architecture', 
                'Technical Documentation',
                'Code Review & Optimization'
            ]
        })

    except Exception as e:
        logger.error(f"Enhanced health check error: {str(e)}")
        return jsonify({
            'service': 'enhanced_chat',
            'ollama_health': {'healthy': False, 'error': str(e)},
            'features': {'professional_prompts': False}
        }), 500
