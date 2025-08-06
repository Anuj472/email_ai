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

    def generate_email_reply_with_context(self, document_content: str, user_request: str, context: Dict = None) -> Dict:
        """Generate email reply with full conversation context and memory"""
        try:
            # Build comprehensive context from chat history
            chat_history = context.get('chat_history', []) if context else []
            
            # Extract all user requests and information from chat history
            conversation_context = self._build_conversation_context(chat_history, user_request)
            
            prompt = f"""You are a professional email assistant with perfect memory. You remember ALL previous conversations and requests from the user in this session.

DOCUMENT CONTENT:
{document_content[:2000]}...

CONVERSATION HISTORY AND CONTEXT:
{conversation_context}

CURRENT USER REQUEST:
{user_request}

DOCUMENT SUBJECT: {context.get('document_subject', 'N/A') if context else 'N/A'}

IMPORTANT INSTRUCTIONS:
1. Remember and consider ALL previous information the user has provided in this conversation
2. Build upon previous requests and information - don't ignore or forget anything
3. If the user is adding more information, incorporate it with previously provided details
4. Generate a comprehensive email reply that considers the ENTIRE conversation context
5. Use proper email formatting with clear structure

Please generate a professional email reply that incorporates ALL the information from our entire conversation:"""

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 800,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                formatted_email = self._format_email_reply(result.get('response', '').strip())
                
                return {
                    'success': True,
                    'response': formatted_email
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to generate email reply'
                }

        except Exception as e:
            logger.error(f"Error in contextual email generation: {str(e)}")
            return {
                'success': False,
                'error': 'Email generation failed'
            }

    def generate_chat_response_with_context(self, user_message: str, document_content: str, selected_file: Dict, chat_history: List) -> Dict:
        """Generate conversational response with full conversation memory"""
        try:
            # Check if user is asking for email generation
            email_keywords = [
                'generate reply', 'create reply', 'write reply', 'email reply',
                'respond to', 'draft reply', 'compose reply', 'reply to this',
                'generate email', 'create email', 'write email', 'draft email',
                'professional reply', 'formal reply', 'make email', 'write an email'
            ]
            
            is_email_request = any(keyword in user_message.lower() for keyword in email_keywords)
            
            if is_email_request:
                # Use the email generation method with full context
                context = {
                    'document_subject': selected_file.get('subject', 'Unknown'),
                    'chat_history': chat_history,
                    'document_content': document_content,
                    'thread_id': selected_file.get('thread_id', '')
                }
                return self.generate_email_reply_with_context(
                    document_content, 
                    user_message, 
                    context
                )
            
            # Regular chat response with conversation memory
            conversation_context = self._build_conversation_context(chat_history, user_message)
            
            context_prompt = f"""You are an AI assistant with perfect memory helping with document analysis and email generation. You remember ALL previous conversations in this session.

DOCUMENT SUMMARY:
Subject: "{selected_file.get('subject', 'Unknown')}"
Content: {document_content[:1000]}...

COMPLETE CONVERSATION CONTEXT:
{conversation_context}

CURRENT USER MESSAGE: {user_message}

IMPORTANT: 
- Remember ALL previous information the user has shared
- Build upon previous requests and conversations
- If user is adding more details, combine them with previous information
- Provide helpful responses that acknowledge the full conversation history

You can help with:
- Analyzing the document and answering questions
- Generating different types of email replies
- Modifying tone and style based on accumulated preferences
- Including specific information from our entire conversation
- General guidance based on our discussion history

Please provide a helpful response that considers our ENTIRE conversation:"""

            payload = {
                "model": self.model,
                "prompt": context_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "num_predict": 500,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
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
                    'response': result.get('response', '').strip()
                }
            else:
                return {
                    'success': False,
                    'response': 'I encountered an error. Please try again.'
                }

        except Exception as e:
            logger.error(f"Error in contextual chat: {str(e)}")
            return {
                'success': False,
                'response': 'I encountered an error. Please try again.'
            }

    def _build_conversation_context(self, chat_history: List, current_message: str) -> str:
        """Build comprehensive conversation context from chat history"""
        if not chat_history:
            return f"This is the first message in our conversation: {current_message}"
        
        context_parts = []
        context_parts.append("=== COMPLETE CONVERSATION HISTORY ===")
        
        # Group related information
        user_requests = []
        ai_responses = []
        email_replies = []
        
        for i, msg in enumerate(chat_history, 1):
            timestamp = msg.get('timestamp', 'Unknown time')
            
            if msg.get('isUser', False):
                user_requests.append(f"User Request {i} ({timestamp}): {msg.get('text', '')}")
            elif msg.get('isReply', False):
                email_replies.append(f"Generated Email {i} ({timestamp}): {msg.get('text', '')}")
            else:
                ai_responses.append(f"AI Response {i} ({timestamp}): {msg.get('text', '')}")
        
        # Add all user requests
        if user_requests:
            context_parts.append("\n=== ALL USER REQUESTS AND INFORMATION ===")
            context_parts.extend(user_requests)
        
        # Add AI responses for context
        if ai_responses:
            context_parts.append("\n=== PREVIOUS AI RESPONSES ===")
            context_parts.extend(ai_responses[-3:])  # Last 3 responses
        
        # Add generated emails
        if email_replies:
            context_parts.append("\n=== PREVIOUSLY GENERATED EMAILS ===")
            context_parts.extend(email_replies[-2:])  # Last 2 emails
        
        # Extract key information patterns
        all_user_text = " ".join([msg.get('text', '') for msg in chat_history if msg.get('isUser', False)])
        all_user_text += " " + current_message
        
        # Look for important information patterns
        important_info = self._extract_important_information(all_user_text)
        if important_info:
            context_parts.append(f"\n=== KEY INFORMATION TO REMEMBER ===")
            context_parts.append(important_info)
        
        context_parts.append(f"\n=== CURRENT REQUEST ===")
        context_parts.append(f"Current message: {current_message}")
        
        return "\n".join(context_parts)

    def _extract_important_information(self, all_text: str) -> str:
        """Extract important information patterns from all user messages"""
        important_patterns = []
        
        # Email addresses
        import re
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', all_text)
        if emails:
            important_patterns.append(f"Email addresses mentioned: {', '.join(set(emails))}")
        
        # Names (capitalized words that might be names)
        names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', all_text)
        if names:
            important_patterns.append(f"Names mentioned: {', '.join(set(names))}")
        
        # Dates
        dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b', all_text)
        if dates:
            important_patterns.append(f"Dates mentioned: {', '.join(set(dates))}")
        
        # Numbers and amounts
        amounts = re.findall(r'\$[\d,]+\.?\d*|\b\d+[\d,]*\.?\d*\b(?:\s*(?:dollars|USD|EUR|pounds))?', all_text)
        if amounts:
            important_patterns.append(f"Amounts/Numbers: {', '.join(set(amounts))}")
        
        # Keywords indicating tone or style preferences
        tone_keywords = re.findall(r'\b(?:formal|informal|professional|casual|urgent|polite|friendly|brief|detailed)\b', all_text.lower())
        if tone_keywords:
            important_patterns.append(f"Tone preferences: {', '.join(set(tone_keywords))}")
        
        # Specific requirements or instructions
        requirements = re.findall(r'(?:include|mention|add|make sure|don\'t forget|remember to|please)\s+[^.!?]*', all_text.lower())
        if requirements:
            important_patterns.append(f"Specific requirements: {'; '.join(requirements[:3])}")
        
        return "\n".join(important_patterns) if important_patterns else ""

    def _format_email_reply(self, raw_email: str) -> str:
        """Format raw email text into properly structured email with line breaks and sections"""
        lines = [line.strip() for line in raw_email.split('\n') if line.strip()]
        
        formatted_sections = []
        current_section = []
        
        subject_line = ""
        greeting = ""
        body_paragraphs = []
        closing = ""
        signature = ""
        
        # Process lines to identify sections
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Detect subject line
            if line.lower().startswith(('subject:', 're:', 'fw:')):
                subject_line = line
            
            # Detect greeting
            elif line.lower().startswith(('dear ', 'hello ', 'hi ', 'greetings')):
                greeting = line
            
            # Detect closing phrases
            elif line.lower().startswith(('best regards', 'sincerely', 'thank you', 'thanks', 'kind regards', 'yours truly')):
                closing = line
                if i + 1 < len(lines):
                    signature = lines[i + 1]
                    i += 1
            
            # Everything else goes to body
            else:
                if line and not line.lower().startswith(('please note', 'note:')):
                    body_paragraphs.append(line)
            
            i += 1
        
        # Build the formatted email
        formatted_email = ""
        
        if subject_line:
            formatted_email += f"{subject_line}\n\n"
        
        if greeting:
            formatted_email += f"{greeting}\n\n"
        
        # Process body paragraphs
        if body_paragraphs:
            current_paragraph = []
            
            for line in body_paragraphs:
                if line.startswith(('* ', '• ', '- ', '1. ', '2. ', '3. ', '4. ', '5. ')):
                    if current_paragraph:
                        formatted_email += ' '.join(current_paragraph) + "\n\n"
                        current_paragraph = []
                    formatted_email += f"{line}\n"
                
                elif line.endswith(('.', '!', '?', ':')):
                    current_paragraph.append(line)
                    if len(' '.join(current_paragraph)) > 100:
                        formatted_email += ' '.join(current_paragraph) + "\n\n"
                        current_paragraph = []
                else:
                    current_paragraph.append(line)
            
            if current_paragraph:
                formatted_email += ' '.join(current_paragraph) + "\n\n"
        
        if closing:
            formatted_email += f"{closing}\n"
        
        if signature:
            formatted_email += f"{signature}\n"
        
        return formatted_email.strip()

    # ... (keep other existing methods like check_health, etc.)
    
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
