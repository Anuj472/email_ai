from app import create_app
import os

if __name__ == '__main__':
    config_name = os.environ.get('FLASK_ENV', 'development')
    app = create_app(config_name)
    app.run(host='0.0.0.0', port=5000, debug=True)
