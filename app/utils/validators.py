# app/utils/validators.py
import json
from pathlib import Path
from google.oauth2 import service_account
from google.cloud import texttospeech

def validate_google_credentials():
    """Validate Google Cloud credentials and TTS API access."""
    try:
        # Get credentials path from environment
        creds_path = Path(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')).expanduser()
        
        if not creds_path.exists():
            raise FileNotFoundError(f"Credentials file not found at {creds_path}")
            
        # Load and validate JSON structure
        with open(creds_path) as f:
            creds_data = json.load(f)
            
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        
        missing_fields = [field for field in required_fields 
                         if field not in creds_data]
                         
        if missing_fields:
            raise ValueError(f"Missing required fields in credentials: {missing_fields}")
            
        # Verify credentials work with TTS API
        credentials = service_account.Credentials.from_service_account_file(
            str(creds_path),
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Try to create a client and make a simple request
        client = texttospeech.TextToSpeechClient(credentials=credentials)
        voices = client.list_voices()
        
        return True, "Credentials validated successfully"
        
    except Exception as e:
        return False, f"Credential validation failed: {str(e)}"

# Add to app/main.py initialization
def create_app():
    app = Flask(__name__)
    
    # Validate credentials during startup
    is_valid, message = validate_google_credentials()
    if not is_valid:
        app.logger.error(message)
        raise RuntimeError(message)
    
    return app