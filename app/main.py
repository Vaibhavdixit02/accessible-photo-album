from flask import Flask, request, jsonify
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from google.cloud import texttospeech
from PIL import Image
import io
import os
import base64
import logging
from datetime import datetime
from dotenv import load_dotenv
import boto3
import time
import autogen
from autogen import Agent, AssistantAgent, ConversableAgent, UserProxyAgent
from autogen.agentchat.contrib.capabilities.vision_capability import VisionCapability
from autogen.agentchat.contrib.img_utils import get_pil_image, pil_to_data_uri
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
from autogen.code_utils import content_str

# Configuration for GPT-4 Vision
config_list_4v = [
    {
        "model": "gpt-4o",
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }
]

# Initialize agents
image_agent = MultimodalConversableAgent(
    name="image-summarizer",
    system_message="""
    You are a helpful assistant that recounts personal photographs for visually impaired persons. Talk in first person, as someone who is a part of the photo.
    You take care of it being a human and emotional summary. Give names to people, describe the situation by making up some back story
    for the picture and use that, it should be like a story rather than a description.""",
    max_consecutive_auto_reply=10,
    llm_config={"config_list": config_list_4v, "temperature": 0.95, "max_tokens": 300},
)

user_proxy = autogen.UserProxyAgent(
    name="User_proxy",
    system_message="Please summarize the image for me, and explain it in detail.",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=0,
    code_execution_config={"use_docker": False},
)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Cloud Text-to-Speech client
tts_client = texttospeech.TextToSpeechClient()

# S3 configuration
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ID'),
    aws_secret_access_key=os.getenv('AWS_KEY'),
    region_name='ap-south-1'
)
BUCKET_NAME = 'accessible-photo-album'

class PhotoDatabase:
    def __init__(self):
        self.photos_db = {}
        
    def add_photo(self, photo_id, photo_data, image_url, title, caption, audio):
        """Add a photo to the database with all its associated data."""
        # Convert image data to base64 for storage and display
        if isinstance(photo_data, bytes):
            image_base64 = base64.b64encode(photo_data).decode()
        else:
            image_base64 = photo_data

        self.photos_db[photo_id] = {
            'title': title or photo_id,
            'image_url': image_url,
            'image_data': image_base64,
            'caption': caption,
            'audio': audio,
            'timestamp': datetime.now().isoformat(),
            'display_url': f"data:image/jpeg;base64,{image_base64}"  # Add direct display URL
        }
        return photo_id
        
    def get_photo(self, photo_id):
        """Retrieve a photo from the database."""
        photo = self.photos_db.get(photo_id)
        if photo:
            # Ensure the photo has a display URL
            if 'display_url' not in photo and 'image_data' in photo:
                photo['display_url'] = f"data:image/jpeg;base64,{photo['image_data']}"
        return photo
        
    def list_photos(self):
        """List all photos in the database."""
        # Ensure all photos have display URLs
        for photo_id, photo in self.photos_db.items():
            if 'display_url' not in photo and 'image_data' in photo:
                photo['display_url'] = f"data:image/jpeg;base64,{photo['image_data']}"
        return self.photos_db
        
    def search_photos(self, query):
        """Search photos by title or caption."""
        query = query.lower()
        matching_photos = {}
        for photo_id, photo_info in self.photos_db.items():
            if (query in photo_info['title'].lower() or 
                query in photo_info.get('caption', '').lower()):
                # Ensure the photo has a display URL
                if 'display_url' not in photo_info and 'image_data' in photo_info:
                    photo_info['display_url'] = f"data:image/jpeg;base64,{photo_info['image_data']}"
                matching_photos[photo_id] = photo_info
        return matching_photos

class PhotoAlbum:
    def __init__(self):
        self.photo_db = PhotoDatabase()
        
    def generate_image_caption(self, image, title):
        """Generate detailed caption for the image using OpenAI's model."""
        try:
            # Create a copy of the image for processing
            image_copy = image.copy()
            
            # Resize the image
            max_size = (800, 800)
            image_copy.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Compress image
            buffered = io.BytesIO()
            image_copy.save(buffered, format="JPEG", quality=70)
            
            # Upload to S3
            file_name = f"photos/{int(time.time())}.jpg"
            s3_client.upload_fileobj(
                io.BytesIO(buffered.getvalue()),
                BUCKET_NAME,
                file_name,
                ExtraArgs={'ACL': 'public-read'}
            )

            # Generate S3 URL
            url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"

            # Generate caption using image agent
            if title:
                result = user_proxy.initiate_chat(
                    image_agent,
                    message=f"""This is the image
                    <img {url}>. {title}""",
                )
            else:
                result = user_proxy.initiate_chat(
                    image_agent,
                    message=f"""This is the image
                    <img {url}>.""",
                )
            
            return result.summary, url

        except Exception as e:
            logger.error(f"Error generating caption: {str(e)}")
            return None, None

    def text_to_speech(self, text):
        """Convert text to speech using Google's TTS API."""
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                ssml_gender=texttospeech.SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED,
                name="en-US-Neural2-C"
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.9,
                pitch=0.0
            )
            response = tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            return base64.b64encode(response.audio_content).decode()
        except Exception as e:
            logger.error(f"Error converting text to speech: {str(e)}")
            return None

    def add_photo(self, image_data, title=None):
        """Add a new photo to the album with caption and audio description."""
        try:
            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Generate caption and get S3 URL
            caption, image_url = self.generate_image_caption(image, title)
            
            if not caption or not image_url:
                return None
            
            # Generate audio description
            audio = self.text_to_speech(caption)
            
            # Create unique ID for the photo
            photo_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Store in database
            return self.photo_db.add_photo(
                photo_id=photo_id,
                photo_data=image_data,
                image_url=image_url,
                title=title,
                caption=caption,
                audio=audio
            )
            
        except Exception as e:
            logger.error(f"Error adding photo: {str(e)}")
            return None

# Initialize photo album
photo_album = PhotoAlbum()

@app.route('/upload', methods=['POST'])
def upload_photo():
    """Handle photo upload and processing."""
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'No photo provided'}), 400
            
        photo = request.files['photo']
        title = request.form.get('title')
        
        # Read image data
        image_data = photo.read()
        
        # Add photo to album
        photo_id = photo_album.add_photo(image_data, title)
        
        if photo_id:
            return jsonify({
                'status': 'success',
                'photo_id': photo_id,
                'details': photo_album.photo_db.get_photo(photo_id)
            })
        else:
            return jsonify({'error': 'Failed to process photo'}), 500
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/photos/<photo_id>', methods=['GET'])
def get_photo_details(photo_id):
    """Retrieve photo details including caption and audio description."""
    try:
        photo_info = photo_album.photo_db.get_photo(photo_id)
        if not photo_info:
            return jsonify({'error': 'Photo not found'}), 404
            
        return jsonify(photo_info)
        
    except Exception as e:
        logger.error(f"Error retrieving photo details: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/photos', methods=['GET'])
def list_photos():
    """List all photos in the album."""
    try:
        return jsonify({
            'total_photos': len(photo_album.photo_db.photos_db),
            'photos': photo_album.photo_db.list_photos()
        })
        
    except Exception as e:
        logger.error(f"Error listing photos: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/search', methods=['GET'])
def search_photos():
    """Search photos by title or caption."""
    try:
        query = request.args.get('query', '').lower()
        matching_photos = photo_album.photo_db.search_photos(query)
        
        return jsonify({
            'status': 'success',
            'total_results': len(matching_photos),
            'photos': matching_photos
        })
        
    except Exception as e:
        logger.error(f"Error searching photos: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/photos/<photo_id>/image', methods=['GET'])
def get_photo_image(photo_id):
    """Retrieve the actual image data for a photo."""
    try:
        photo_info = photo_album.photo_db.get_photo(photo_id)
        if not photo_info or 'image_data' not in photo_info:
            return jsonify({'error': 'Photo not found'}), 404
            
        # Decode base64 image data
        image_data = base64.b64decode(photo_info['image_data'])
        
        # Create file-like object
        image_io = io.BytesIO(image_data)
        
        return send_file(
            image_io,
            mimetype='image/jpeg',
            as_attachment=False
        )
        
    except Exception as e:
        logger.error(f"Error retrieving photo image: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

if __name__ == '__main__':
    app.run(debug=True)