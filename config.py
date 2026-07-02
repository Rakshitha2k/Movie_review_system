import os
from urllib.parse import quote_plus

class Config:
        """Application configuration.

        Behavior:
        - For local development, we use SQLite by default (app.db in project root)
        - To use MySQL, set DATABASE_URL environment variable to full MySQL URL:
          DATABASE_URL="mysql+mysqlconnector://user:pass@host/dbname"
        """
        SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-secret'

        # Use SQLite by default, unless DATABASE_URL points to MySQL
        _database_url = os.environ.get('DATABASE_URL')

        # Default to SQLite if no DATABASE_URL provided or if it's empty
        if not _database_url:
            _database_url = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'app.db')}"

        SQLALCHEMY_DATABASE_URI = _database_url or f"sqlite:///{os.path.join(os.path.dirname(__file__), 'app.db')}"

        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'posters')
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
