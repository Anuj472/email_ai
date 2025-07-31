from flask import Blueprint, request, jsonify, current_app
from services.ollama_service import OllamaService
import logging

logger = logging.getLogger(__name__)
chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/message', methods=['POST'])
def send_message():
    """Handle single message and generate AI response"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        user_message = data['message'].strip()
        context = data.get('context', {})
        
        if not user_message:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400
        
        # Generate AI response
        ollama_service = OllamaService()
        result = ollama_service.generate_email_reply(user_message, context)
        
        if result['success']:
            return jsonify({
                'success': True,
                'response': result['response'],
                'model': result.get('model', 'llama3')
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error'],
                'fallback_response': result.get('fallback', '')
            }), 503
        
    except Exception as e:
        logger.error(f"Error in message processing: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@chat_bp.route('/conversation', methods=['POST'])
def handle_conversation():
    """Handle multi-turn conversation"""
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        
        if not messages:
            return jsonify({'success': False, 'error': 'Messages are required'}), 400
        
        ollama_service = OllamaService()
        result = ollama_service.generate_conversation_response(messages)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in conversation handling: {str(e)}")
        return jsonify({'success': False, 'error': 'Conversation error'}), 500

@chat_bp.route('/health', methods=['GET'])
def health_check():
    """Check AI service health"""
    try:
        ollama_service = OllamaService()
        health_status = ollama_service.check_health()
        
        return jsonify({
            'service': 'chat',
            'ollama_health': health_status,
            'config': {
                'model': current_app.config['OLLAMA_MODEL'],
                'base_url': current_app.config['OLLAMA_BASE_URL']
            }
        })
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'service': 'chat',
            'ollama_health': {'healthy': False, 'error': str(e)}
        }), 500
