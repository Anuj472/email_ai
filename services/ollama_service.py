import requests
import json
import logging
import re
from typing import Dict, List, Optional
from flask import current_app

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self):
        self.base_url = current_app.config['OLLAMA_BASE_URL']
        self.model = current_app.config['OLLAMA_MODEL']
        self.timeout = current_app.config.get('OLLAMA_TIMEOUT', 120)

    def generate_professional_response(self, user_message: str, document_content: str, context: Dict = None) -> Dict:
        """Generate professional response with enhanced prompts and word count control"""
        try:
            if not context:
                context = {}

            # ✅ NEW: Professional system prompt
            system_prompt = self._build_professional_system_prompt(context)
            
            # ✅ NEW: Enhanced user prompt with word count control
            enhanced_prompt = self._build_enhanced_user_prompt(user_message, document_content, context)
            
            # ✅ NEW: Determine response length based on context
            word_count_params = self._determine_response_length(user_message, context)

            payload = {
                "model": self.model,
                "system": system_prompt,
                "prompt": enhanced_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": word_count_params['max_tokens'],
                    "num_ctx": 4096
                }
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                generated_text = result.get('response', '').strip()
                
                # ✅ NEW: Count words and validate length
                word_count = len(generated_text.split())
                
                # ✅ NEW: Ensure minimum length requirement
                if word_count < word_count_params['min_words']:
                    generated_text = self._expand_response(generated_text, word_count_params['min_words'])
                    word_count = len(generated_text.split())

                return {
                    'success': True,
                    'response': generated_text,
                    'word_count': word_count,
                    'response_type': self._classify_response_type(user_message),
                    'professional_mode': True,
                    'model': self.model
                }
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f'Ollama service error: {response.status_code}',
                    'fallback': self._get_professional_fallback()
                }

        except requests.exceptions.Timeout:
            logger.error("Ollama request timeout")
            return {
                'success': False,
                'error': 'Request timeout - response may be too long',
                'fallback': self._get_professional_fallback()
            }
        except Exception as e:
            logger.error(f"Error in professional response generation: {str(e)}")
            return {
                'success': False,
                'error': f'Professional response error: {str(e)}',
                'fallback': self._get_professional_fallback()
            }

    def _build_professional_system_prompt(self, context: Dict) -> str:
        """Build enhanced system prompt for professional responses"""
        
        domains = context.get('professional_domains', [])
        
        system_prompt = """You are a Professional Technical AI Assistant specializing in:

🔧 SOFTWARE DEVELOPMENT & PROGRAMMING
- Code review, optimization, and best practices
- Architecture design and system scalability
- Debugging, testing, and deployment strategies
- Multiple programming languages and frameworks

⚡ ELECTRONICS & HARDWARE ENGINEERING  
- Circuit design and component selection
- PCB layout and signal integrity
- Embedded systems and microcontroller programming
- Power management and thermal analysis

🏗️ SYSTEMS ARCHITECTURE & DESIGN
- Distributed systems and cloud architecture
- Database design and optimization
- API design and integration patterns
- Performance tuning and scalability

📋 TECHNICAL DOCUMENTATION & COMMUNICATION
- Professional technical writing
- Requirements analysis and specification
- User guides and API documentation
- Project management and team communication

RESPONSE GUIDELINES:
✅ Provide detailed, technical explanations
✅ Include practical examples and code snippets when relevant
✅ Suggest best practices and industry standards
✅ Consider scalability, security, and maintainability
✅ Use professional language and clear structure
✅ Adapt response length based on complexity and user request

WORD COUNT CONTROL:
- Short responses (50-200 words): Quick answers, confirmations, simple explanations
- Medium responses (200-800 words): Standard technical explanations, code reviews
- Long responses (800-3000 words): Comprehensive analysis, detailed documentation, complex solutions
- Custom word count: When user specifies, aim for that target ±10%

Always prioritize accuracy, professionalism, and practical value in your responses."""

        return system_prompt

    def _build_enhanced_user_prompt(self, user_message: str, document_content: str, context: Dict) -> str:
        """Build enhanced user prompt with document context"""
        
        prompt_parts = []
        
        # Document context
        if document_content:
            prompt_parts.append(f"""
DOCUMENT CONTEXT:
Subject: {context.get('document_subject', 'Technical Document')}
Content: {document_content[:3000]}...

""")

        # Chat history context
        chat_history = context.get('chat_history', [])
        if chat_history:
            recent_history = chat_history[-3:]  # Last 3 messages for context
            prompt_parts.append("CONVERSATION CONTEXT:\n")
            for msg in recent_history:
                role = "User" if msg.get('isUser') else "Assistant"
                prompt_parts.append(f"{role}: {msg.get('text', '')[:200]}...\n")
            prompt_parts.append("\n")

        # Word count instruction
        requested_words = context.get('requested_word_count')
        if requested_words:
            prompt_parts.append(f"SPECIFIC INSTRUCTION: Provide your response in approximately {requested_words} words.\n\n")

        # User request
        prompt_parts.append(f"USER REQUEST: {user_message}")

        return "".join(prompt_parts)

    def _determine_response_length(self, user_message: str, context: Dict) -> Dict:
        """Determine appropriate response length based on user request and context"""
        
        # Check for explicit word count request
        word_count_match = re.search(r'(?:in|about|around|approximately)\s+(\d+)\s+words?', user_message, re.IGNORECASE)
        if word_count_match:
            requested_words = int(word_count_match.group(1))
            # Clamp to allowed range
            requested_words = max(50, min(3000, requested_words))
            return {
                'min_words': max(50, requested_words - 50),
                'target_words': requested_words,
                'max_tokens': min(4000, requested_words * 2)
            }

        # Analyze request complexity
        complexity_indicators = [
            'explain', 'analyze', 'detailed', 'comprehensive', 'thorough',
            'architecture', 'design', 'implementation', 'documentation',
            'review', 'optimization', 'best practices'
        ]
        
        short_indicators = [
            'quick', 'brief', 'summary', 'simple', 'what is', 'define'
        ]

        message_lower = user_message.lower()
        
        if any(indicator in message_lower for indicator in short_indicators):
            return {'min_words': 50, 'target_words': 150, 'max_tokens': 300}
        elif any(indicator in message_lower for indicator in complexity_indicators):
            return {'min_words': 300, 'target_words': 800, 'max_tokens': 1600}
        else:
            return {'min_words': 100, 'target_words': 400, 'max_tokens': 800}

    def _expand_response(self, response: str, min_words: int) -> str:
        """Expand response if it's too short"""
        current_words = len(response.split())
        if current_words >= min_words:
            return response
            
        # Add professional expansion
        expansion = "\n\nAdditional considerations and best practices to keep in mind for this topic include proper documentation, testing methodologies, and scalability planning for future requirements."
        
        return response + expansion

    def _classify_response_type(self, user_message: str) -> str:
        """Classify the type of response being generated"""
        message_lower = user_message.lower()
        
        if any(keyword in message_lower for keyword in ['code', 'programming', 'function', 'algorithm']):
            return 'code_analysis'
        elif any(keyword in message_lower for keyword in ['circuit', 'electronics', 'hardware']):
            return 'electronics_design'
        elif any(keyword in message_lower for keyword in ['architecture', 'system', 'design']):
            return 'system_architecture'
        elif any(keyword in message_lower for keyword in ['documentation', 'document', 'write']):
            return 'technical_documentation'
        else:
            return 'general_technical'

    def _get_professional_fallback(self) -> str:
        """Provide professional fallback response"""
        return """I apologize, but I'm experiencing technical difficulties generating a comprehensive response at the moment. 

However, I'm here to help with:
• Software development and code optimization
• Electronics design and circuit analysis  
• System architecture and scalability planning
• Technical documentation and best practices

Please try rephrasing your question or specify if you'd like a response in a particular word count range (50-3000 words). I'll do my best to provide you with detailed, professional assistance."""

    def generate_email_reply_with_enhanced_context(self, document_content: str, user_request: str, context: Dict = None) -> Dict:
        """Generate enhanced email reply with professional formatting"""
        try:
            system_prompt = """You are a Professional Email Assistant. Generate formal, well-structured email replies for technical and business communications.

EMAIL FORMATTING GUIDELINES:
- Use proper email structure (Subject, Greeting, Body, Closing)
- Maintain professional tone throughout
- Include relevant technical details when appropriate
- Keep emails concise but comprehensive
- Use proper business email etiquette

TECHNICAL EMAIL SPECIALIZATION:
- Software development project updates
- Technical requirement discussions
- System architecture proposals  
- Code review feedback
- Documentation and specification reviews"""

            enhanced_prompt = f"""
DOCUMENT CONTEXT:
{document_content[:2000]}

EMAIL REQUEST: {user_request}

Generate a professional email reply that addresses the request while referencing the document content appropriately. Use formal business email structure and technical terminology where suitable.
"""

            payload = {
                "model": self.model,
                "system": system_prompt,
                "prompt": enhanced_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.6,
                    "top_p": 0.8,
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
                email_content = result.get('response', '').strip()
                
                return {
                    'success': True,
                    'response': email_content,
                    'word_count': len(email_content.split()),
                    'response_type': 'professional_email',
                    'model': self.model
                }
            else:
                return {'success': False, 'error': f'Email generation error: {response.status_code}'}

        except Exception as e:
            logger.error(f"Error in enhanced email generation: {str(e)}")
            return {'success': False, 'error': f'Enhanced email error: {str(e)}'}

    def check_health(self) -> Dict:
        """Enhanced health check with professional capabilities"""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=5)
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'service': 'Enhanced Professional AI',
                    'capabilities': [
                        'Software Development Expertise',
                        'Electronics Engineering',
                        'System Architecture',
                        'Technical Documentation',
                        'Word Count Control (50-3000)',
                        'Professional Email Generation'
                    ],
                    'version': response.json().get('version', 'unknown')
                }
            else:
                return {'healthy': False, 'error': f'Service unavailable: {response.status_code}'}
        except Exception as e:
            return {'healthy': False, 'error': f'Health check failed: {str(e)}'}
