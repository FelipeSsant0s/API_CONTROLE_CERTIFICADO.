import os
import sys
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def wait_for_db(max_attempts=30, delay=2):
    """Wait for database to become available"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not set, skipping check...")
        return True
    
    # Render.com uses postgres://, but SQLAlchemy requires postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    print(f"Checking database connection...")
    engine = create_engine(database_url)
    
    for attempt in range(max_attempts):
        try:
            # Try to connect to the database
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                print("Database is ready!")
                return True
        except OperationalError as e:
            if attempt + 1 < max_attempts:
                print(f"Database not ready (attempt {attempt + 1}/{max_attempts}). Waiting {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"Could not connect to database after {max_attempts} attempts: {str(e)}")
                return False
        except Exception as e:
            print(f"Unexpected error while checking database: {str(e)}")
            return False

if __name__ == '__main__':
    if not wait_for_db():
        sys.exit(1) 