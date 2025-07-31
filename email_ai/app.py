from flask import Flask
from flask_cors import CORS
import os
import logging
from config import config

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Enable CORS
    CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
    
    # Create upload directory
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from routes.chat_routes import chat_bp
    from routes.file_routes import file_bp
    
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(file_bp, url_prefix='/api/files')
    
    @app.route('/')
    def index():
        return {
            'message': 'AI Email System API',
            'status': 'running',
            'version': '1.0.0'
        }
    
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'ai-email-system'}
    
    return app
