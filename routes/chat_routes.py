from flask import Blueprint, request, jsonify, current_app
from services.ollama_service import OllamaService
from services.file_service import FileService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create the blueprint first
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

@chat_bp.route('/thread', methods=['POST'])
def handle_chat_thread():
    """Handle chat thread with enhanced context memory and conversation understanding"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        filename = data.get('filename', '')

        if not user_message:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

        if not filename:
            return jsonify({'success': False, 'error': 'Filename is required'}), 400

        # Get file service and thread info
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Save user message to thread FIRST to include in context
        user_msg = {
            'text': user_message,
            'isUser': True,
            'type': 'user_message',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        file_service.save_chat_message(filename, user_msg)

        # Get COMPLETE and UPDATED chat history for full context
        chat_history = file_service.get_chat_history(filename)
        document_content = thread_info.get('full_content', '')

        # Build enhanced context with full conversation memory
        context = {
            'document_subject': thread_info.get('subject', ''),
            'document_content': document_content,
            'user_request': user_message,
            'chat_history': chat_history,  # Full history INCLUDING current message
            'thread_id': thread_info.get('thread_id', ''),
            'conversation_summary': _get_conversation_summary(chat_history),
            'accumulated_info': _extract_accumulated_information(chat_history)
        }

        ollama_service = OllamaService()

        # Check if user is asking for email generation
        email_keywords = [
            'generate reply', 'create reply', 'write reply', 'email reply',
            'respond to', 'draft reply', 'compose reply', 'reply to this',
            'generate email', 'create email', 'write email', 'draft email',
            'make email', 'create an email', 'write an email', 'send email',
            'professional reply', 'formal reply', 'write a response'
        ]

        is_email_request = any(keyword in user_message.lower() for keyword in email_keywords)

        if is_email_request:
            # Generate email reply with FULL conversation context
            result = ollama_service.generate_email_reply_with_context(
                document_content,
                user_message,
                context
            )

            if result.get('success'):
                # Save AI response to thread
                ai_msg = {
                    'text': result['response'],
                    'isUser': False,
                    'type': 'email_reply',
                    'isReply': True,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'context_info': {
                        'messages_considered': len(chat_history),
                        'has_accumulated_info': len(context.get('accumulated_info', {})) > 0
                    }
                }

                file_service.save_chat_message(filename, ai_msg)

                # Mark as replied if this is an email generation
                file_service.mark_reply_generated(filename, result['response'])

                return jsonify({
                    'success': True,
                    'response': result['response'],
                    'is_email_reply': True,
                    'thread_id': thread_info.get('thread_id', ''),
                    'context_used': True,
                    'messages_in_context': len(chat_history)
                })

        # Handle general conversation with enhanced context memory
        result = ollama_service.generate_chat_response_with_context(
            user_message,
            document_content,
            thread_info,
            chat_history  # Pass full history for context
        )

        if result.get('success'):
            # Save AI response to thread
            ai_msg = {
                'text': result['response'],
                'isUser': False,
                'type': 'general_response',
                'isReply': False,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'context_info': {
                    'messages_considered': len(chat_history),
                    'conversation_flow': 'continued'
                }
            }

            file_service.save_chat_message(filename, ai_msg)

            return jsonify({
                'success': True,
                'response': result.get('response', 'I encountered an error. Please try again.'),
                'is_email_reply': False,
                'thread_id': thread_info.get('thread_id', ''),
                'context_used': True,
                'conversation_depth': len(chat_history)
            })

        else:
            # Fallback response
            fallback_msg = {
                'text': 'I encountered an error processing your request. Please try again.',
                'isUser': False,
                'type': 'error_response',
                'isReply': False,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            file_service.save_chat_message(filename, fallback_msg)
            
            return jsonify({
                'success': False,
                'response': fallback_msg['text'],
                'error': 'AI processing error'
            })

    except Exception as e:
        logger.error(f"Error in chat thread: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Chat thread error'
        }), 500

def _get_conversation_summary(chat_history):
    """Generate a summary of the conversation for better context"""
    if not chat_history:
        return "No previous conversation"
    
    user_messages = [msg for msg in chat_history if msg.get('isUser', False)]
    ai_responses = [msg for msg in chat_history if not msg.get('isUser', False)]
    email_replies = [msg for msg in chat_history if msg.get('isReply', False)]
    
    return {
        'total_exchanges': len(chat_history) // 2,
        'user_requests': len(user_messages),
        'ai_responses': len(ai_responses),
        'emails_generated': len(email_replies),
        'conversation_start': chat_history[0].get('timestamp') if chat_history else None,
        'latest_activity': chat_history[-1].get('timestamp') if chat_history else None,
        'conversation_active': True
    }

def _extract_accumulated_information(chat_history):
    """Extract and accumulate important information from entire conversation"""
    if not chat_history:
        return {}
    
    import re
    
    # Get all user messages text
    user_messages = [msg.get('text', '') for msg in chat_history if msg.get('isUser', False)]
    all_user_text = ' '.join(user_messages)
    
    accumulated_info = {}
    
    # Extract email addresses
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', all_user_text)
    if emails:
        accumulated_info['emails'] = list(set(emails))
    
    # Extract names (proper nouns that could be names)
    names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', all_user_text)
    if names:
        accumulated_info['names'] = list(set(names))
    
    # Extract dates
    dates = re.findall(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|January|February|March|April|May|June|July|August|September|October|November|December)\b', all_user_text, re.IGNORECASE)
    if dates:
        accumulated_info['dates'] = list(set(dates))
    
    # Extract monetary amounts
    amounts = re.findall(r'\$[\d,]+\.?\d*|\b\d+[\d,]*\.?\d*\s*(?:dollars|USD|EUR|pounds)\b', all_user_text, re.IGNORECASE)
    if amounts:
        accumulated_info['amounts'] = list(set(amounts))
    
    # Extract tone/style preferences
    tone_words = re.findall(r'\b(?:formal|informal|professional|casual|urgent|polite|friendly|brief|detailed|concise|comprehensive)\b', all_user_text, re.IGNORECASE)
    if tone_words:
        accumulated_info['tone_preferences'] = list(set([word.lower() for word in tone_words]))
    
    # Extract specific instructions/requirements
    instructions = []
    for msg in user_messages:
        # Look for instruction patterns
        instruction_patterns = [
            r'(?:include|mention|add|make sure|don\'t forget|remember to|please)\s+[^.!?]*',
            r'(?:also|additionally|furthermore|moreover)\s+[^.!?]*',
            r'(?:with|regarding|about|concerning)\s+[^.!?]*'
        ]
        
        for pattern in instruction_patterns:
            matches = re.findall(pattern, msg, re.IGNORECASE)
            instructions.extend(matches)
    
    if instructions:
        accumulated_info['instructions'] = instructions[:5]  # Keep latest 5 instructions
    
    # Extract topics/subjects mentioned
    topics = re.findall(r'\b(?:meeting|project|proposal|contract|budget|deadline|presentation|report|document|email|call|appointment)\b', all_user_text, re.IGNORECASE)
    if topics:
        accumulated_info['topics'] = list(set([topic.lower() for topic in topics]))
    
    # Track conversation intent evolution
    email_requests = [msg for msg in user_messages if any(keyword in msg.lower() for keyword in ['email', 'reply', 'respond', 'write', 'generate', 'draft', 'compose'])]
    if email_requests:
        accumulated_info['email_evolution'] = {
            'requests_count': len(email_requests),
            'latest_request': email_requests[-1] if email_requests else None,
            'evolving_requirements': len(email_requests) > 1
        }
    
    return accumulated_info

@chat_bp.route('/thread/<filename>/history', methods=['GET'])
def get_thread_history(filename):
    """Get chat history for a specific thread with conversation analysis"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        chat_history = thread_info.get('chat_history', [])
        
        # Enhanced response with conversation insights
        return jsonify({
            'success': True,
            'thread_id': thread_info.get('thread_id', ''),
            'subject': thread_info.get('subject', ''),
            'chat_history': chat_history,
            'final_reply': thread_info.get('final_reply', None),
            'has_reply': thread_info.get('has_reply', False),
            'conversation_summary': _get_conversation_summary(chat_history),
            'accumulated_info': _extract_accumulated_information(chat_history),
            'context_depth': len(chat_history)
        })

    except Exception as e:
        logger.error(f"Error getting thread history: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get thread history'}), 500

@chat_bp.route('/thread/<filename>/clear', methods=['POST'])
def clear_thread_history(filename):
    """Clear chat history for a specific thread"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        success = file_service.clear_chat_history(filename)

        if success:
            return jsonify({
                'success': True,
                'message': 'Chat history cleared successfully',
                'context_reset': True
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to clear chat history'}), 400

    except Exception as e:
        logger.error(f"Error clearing thread history: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to clear chat history'}), 500

@chat_bp.route('/thread/<filename>/context', methods=['GET'])
def get_thread_context(filename):
    """Get current conversation context and accumulated information"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        chat_history = thread_info.get('chat_history', [])
        
        return jsonify({
            'success': True,
            'thread_id': thread_info.get('thread_id', ''),
            'conversation_summary': _get_conversation_summary(chat_history),
            'accumulated_info': _extract_accumulated_information(chat_history),
            'context_strength': 'high' if len(chat_history) > 4 else 'medium' if len(chat_history) > 1 else 'low',
            'ready_for_email': len([msg for msg in chat_history if msg.get('isUser', False)]) > 0
        })

    except Exception as e:
        logger.error(f"Error getting thread context: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get thread context'}), 500

@chat_bp.route('/health', methods=['GET'])
def health_check():
    """Check AI service health with enhanced diagnostics"""
    try:
        ollama_service = OllamaService()
        health_status = ollama_service.check_health()

        return jsonify({
            'service': 'chat',
            'ollama_health': health_status,
            'config': {
                'model': current_app.config['OLLAMA_MODEL'],
                'base_url': current_app.config['OLLAMA_BASE_URL']
            },
            'features': {
                'context_memory': True,
                'conversation_tracking': True,
                'accumulated_info_extraction': True,
                'enhanced_email_generation': True
            }
        })

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'service': 'chat',
            'ollama_health': {'healthy': False, 'error': str(e)},
            'features': {'context_memory': False}
        }), 500

@chat_bp.route('/thread/<filename>/regenerate', methods=['POST'])
def regenerate_last_response(filename):
    """Regenerate the last AI response with current context"""
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        thread_info = file_service.get_thread_info(filename)

        if not thread_info:
            return jsonify({'success': False, 'error': 'Thread not found'}), 404

        chat_history = thread_info.get('chat_history', [])
        
        if not chat_history or not any(msg.get('isUser', False) for msg in chat_history):
            return jsonify({'success': False, 'error': 'No user messages to regenerate response for'}), 400

        # Get the last user message
        last_user_message = None
        for msg in reversed(chat_history):
            if msg.get('isUser', False):
                last_user_message = msg
                break

        if not last_user_message:
            return jsonify({'success': False, 'error': 'No user message found'}), 400

        # Remove the last AI response if it exists
        if chat_history and not chat_history[-1].get('isUser', False):
            chat_history = chat_history[:-1]
            # Update the thread with the modified history
            thread_info['chat_history'] = chat_history
            file_service._save_file_metadata(filename, thread_info)

        # Regenerate response using the existing thread handler logic
        context = {
            'document_subject': thread_info.get('subject', ''),
            'document_content': thread_info.get('full_content', ''),
            'user_request': last_user_message.get('text', ''),
            'chat_history': chat_history,
            'thread_id': thread_info.get('thread_id', ''),
            'regenerating': True
        }

        ollama_service = OllamaService()
        
        # Check if it was an email request
        email_keywords = [
            'generate reply', 'create reply', 'write reply', 'email reply',
            'respond to', 'draft reply', 'compose reply', 'reply to this',
            'generate email', 'create email', 'write email', 'draft email'
        ]
        
        is_email_request = any(keyword in last_user_message.get('text', '').lower() for keyword in email_keywords)

        if is_email_request:
            result = ollama_service.generate_email_reply_with_context(
                thread_info.get('full_content', ''),
                last_user_message.get('text', ''),
                context
            )
            is_reply = True
        else:
            result = ollama_service.generate_chat_response_with_context(
                last_user_message.get('text', ''),
                thread_info.get('full_content', ''),
                thread_info,
                chat_history
            )
            is_reply = False

        if result.get('success'):
            # Save the new AI response
            ai_msg = {
                'text': result['response'],
                'isUser': False,
                'type': 'email_reply' if is_reply else 'general_response',
                'isReply': is_reply,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'regenerated': True
            }

            file_service.save_chat_message(filename, ai_msg)

            return jsonify({
                'success': True,
                'response': result['response'],
                'is_email_reply': is_reply,
                'regenerated': True,
                'thread_id': thread_info.get('thread_id', '')
            })

        return jsonify({'success': False, 'error': 'Failed to regenerate response'}), 500

    except Exception as e:
        logger.error(f"Error regenerating response: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to regenerate response'}), 500
