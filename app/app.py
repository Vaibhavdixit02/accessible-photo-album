import streamlit as st
import requests
import json
import base64
import speech_recognition as sr
from bokeh.models.widgets import Button
from bokeh.models import CustomJS
from streamlit_bokeh_events import streamlit_bokeh_events

# Set the Flask API URL
FLASK_API_URL = "http://127.0.0.1:5000"

# Streamlit app title
st.title("Patronum \nBringing memories to life")

def listen_for_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("🎤 Listening... (speak now)")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            st.write("Processing speech...")
            text = recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            st.warning("No speech detected within timeout period")
            return None
        except sr.UnknownValueError:
            st.warning("Could not understand audio")
            return None
        except sr.RequestError as e:
            st.error(f"Could not request results; {e}")
            return None

def display_photo_details(photo_info):
    """Helper function to display photo details consistently"""
    st.write("---")
    if photo_info.get('image'):
        st.image(base64.b64decode(photo_info['image']), caption=photo_info['title'])
    st.write(f"**Title:** {photo_info['title']}")
    st.write(f"**Caption:** {photo_info['caption']}")
    st.write(f"**Uploaded on:** {photo_info['timestamp']}")
    if photo_info.get('audio'):
        st.audio(base64.b64decode(photo_info['audio']), format="audio/mp3")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["Upload", "Search", "View All"])

with tab1:
    # Initialize session state for text input
    if 'text_input' not in st.session_state:
        st.session_state.text_input = ""

    # Create the text input field
    text_input = st.text_input(
        "Enter or speak text:",
        value=st.session_state.text_input,
        key="text_field"
    )

    # Create columns for buttons
    col1, col2 = st.columns([1, 4])

    with col1:
        if st.button("🎤 Record", type="primary"):
            result = listen_for_speech()
            if result:
                current_text = st.session_state.text_input
                new_text = f"{current_text} {result}".strip()
                st.session_state.text_input = new_text
                st.rerun()

    with col2:
        if st.button("Clear Text", type="secondary"):
            st.session_state.text_input = ""
            st.rerun()

    if st.session_state.text_input:
        st.markdown("### Current text:")
        st.markdown(f"_{st.session_state.text_input}_")

    uploaded_file = st.file_uploader("Upload a photo", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)
        
        if st.button("Generate Caption and Audio"):
            files = {
                'photo': uploaded_file.getvalue()
            }
            data = {
                'title': st.session_state.text_input
            }

            with st.spinner('Processing...'):
                try:
                    response = requests.post(f"{FLASK_API_URL}/upload", files=files, data=data)
                    response_data = response.json()

                    if response.status_code == 200 and response_data.get('status') == 'success':
                        st.success("Caption and audio generated successfully!")
                        caption = response_data['details']['caption']
                        st.subheader("Generated Caption:")
                        st.write(caption)
                        
                        if response_data['details']['audio']:
                            st.subheader("Audio Description:")
                            audio_bytes = base64.b64decode(response_data['details']['audio'])
                            st.audio(audio_bytes, format="audio/mp3")
                        else:
                            st.error("Failed to generate audio.")
                    else:
                        st.error("Failed to process photo.")
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("Search Photos")
    
    # Initialize search session state
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""

    # Create columns for search input
    search_col1, search_col2, search_col3 = st.columns([3, 1, 1])

    with search_col1:
        search_input = st.text_input(
            "Search photos:",
            value=st.session_state.search_query,
            key="search_field",
            placeholder="Enter text or use voice to search..."
        )

    with search_col2:
        if st.button("🎤 Voice Search", type="primary"):
            result = listen_for_speech()
            if result:
                st.session_state.search_query = result
                st.rerun()

    with search_col3:
        if st.button("Search", type="primary"):
            st.session_state.search_query = search_input

    # Perform search if there's a query
    if st.session_state.search_query:
        with st.spinner('Searching...'):
            try:
                response = requests.get(
                    f"{FLASK_API_URL}/search",
                    params={'query': st.session_state.search_query}
                )
                search_results = response.json()

                if response.status_code == 200:
                    if search_results.get('photos'):
                        st.write(f"Found {len(search_results['photos'])} matching photos:")
                        for photo_id, photo_info in search_results['photos'].items():
                            display_photo_details(photo_info)
                    else:
                        st.info("No photos found matching your search.")
                else:
                    st.error("Failed to perform search.")
            except Exception as e:
                st.error(f"Error during search: {e}")

with tab3:
    st.header("All Photos")
    if st.button("Refresh Photos"):
        with st.spinner('Loading photos...'):
            try:
                response = requests.get(f"{FLASK_API_URL}/photos")
                photos_data = response.json()

                if response.status_code == 200:
                    total_photos = photos_data.get('total_photos', 0)
                    st.write(f"Total Photos: {total_photos}")

                    for photo_id, photo_info in photos_data['photos'].items():
                        display_photo_details(photo_info)
                else:
                    st.error("Failed to load photos.")
            except Exception as e:
                st.error(f"Error: {e}")