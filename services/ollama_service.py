import requests
import json
import logging
from typing import Dict, List, Optional
from flask import current_app

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self):
        self.base_url = current_app.config['OLLAMA_BASE_URL']
        self.model = current_app.config['OLLAMA_MODEL']
        self.timeout = current_app.config.get('OLLAMA_TIMEOUT', 60)
    
    def generate_email_reply(self, email_content: str, context: Dict = None) -> Dict:
        """Generate an email reply using Ollama API"""
        try:
            prompt = self._create_email_prompt(email_content, context)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": current_app.config.get('DEFAULT_TEMPERATURE', 0.7),
                    "num_predict": current_app.config.get('DEFAULT_MAX_TOKENS', 500)
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'response': result.get('response', '').strip(),
                    'model': self.model
                }
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {
                    'success': False,
                    'error': 'AI service unavailable',
                    'fallback': self._get_fallback_response()
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {str(e)}")
            return {
                'success': False,
                'error': 'Network error',
                'fallback': self._get_fallback_response()
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                'success': False,
                'error': 'Service error',
                'fallback': self._get_fallback_response()
            }
    
    def generate_conversation_response(self, messages: List[Dict]) -> Dict:
        """Generate a conversation response using Ollama chat API"""
        try:
            # Format messages for Ollama
            formatted_messages = [
                {
                    'role': 'system',
                    'content': 'You are a professional email assistant. Generate helpful, professional email responses.'
                }
            ]
            
            # Add conversation history
            for msg in messages[-10:]:  # Keep last 10 messages for context
                role = 'user' if msg.get('isUser', True) else 'assistant'
                formatted_messages.append({
                    'role': role,
                    'content': msg.get('text', '')
                })
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "num_predict": 300
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'response': result.get('message', {}).get('content', '').strip()
                }
            else:
                return {
                    'success': False,
                    'error': 'Chat service unavailable',
                    'fallback': "I'm having trouble generating a response right now."
                }
                
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return {
                'success': False,
                'error': 'Chat error',
                'fallback': "I encountered an error. Please try again."
            }
    
    def analyze_document(self, document_content: str) -> Dict:
        """Analyze document content for email insights"""
        try:
            prompt = f"""Analyze this document for email communication opportunities:

Document Content:
{document_content[:2000]}...

Provide:
1. Key points requiring email responses
2. Suggested email templates
3. Priority levels
4. Recommended timelines

Analysis:"""
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.6,
                    "num_predict": 800
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'analysis': result.get('response', '').strip()
                }
            else:
                return {
                    'success': False,
                    'error': 'Document analysis unavailable'
                }
                
        except Exception as e:
            logger.error(f"Document analysis error: {str(e)}")
            return {
                'success': False,
                'error': 'Analysis failed'
            }
    
    def _create_email_prompt(self, email_content: str, context: Dict = None) -> str:
        """Create a structured prompt for email reply generation"""
        prompt = f"""You are a professional document analyzer and email assistant. Generate a polite, professional email reply, whenever your are told to do so otherwise provide a summary of the content.

Guidelines:
- Be professional and courteous
- Keep responses concise but complete
- Match the tone of the original email
- Include relevant details
- Use proper email etiquette

Email to reply to:
{email_content}

"""
        
        if context:
            prompt += f"""Additional context:
- Urgency: {context.get('urgency', 'normal')}
- Tone: {context.get('tone', 'professional')}
- Additional info: {context.get('additional_info', '')}

"""
        
        prompt += "Generate a professional email reply:"
        return prompt
    
    def _get_fallback_response(self) -> str:
        """Return a fallback response when AI generation fails"""
        return "Thank you for your message. I'm reviewing your request and will respond shortly."
    
    def check_health(self) -> Dict:
        """Check if Ollama service is healthy"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_available = any(
                    model.get('name', '').startswith(self.model) 
                    for model in models
                )
                return {
                    'healthy': True,
                    'model_available': model_available,
                    'models': [m.get('name') for m in models]
                }
            return {'healthy': False, 'error': 'Service unavailable'}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}
