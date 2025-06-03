from flask import Flask, send_from_directory, request, jsonify
import os
import sys
import uuid # For unique filenames
import logging # For better logging

# Configure basic logging for the app
logging.basicConfig(level=logging.INFO)

# Add the parent directory to Python path so we can import stt_tts_modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now import from stt_tts_modules package
try:
    from stt_tts_modules.speech_to_text_whispr import load_stt_model, transcribe_audio_file
except ImportError as e:
    logging.error(f"Error importing from speech_to_text_whispr: {e}", exc_info=True)
    # Define dummy functions if import fails, so app can still start and report errors via API
    def load_stt_model():
        raise ImportError("Failed to import STT module components. Check logs for details.")
    def transcribe_audio_file(filepath):
        return {"error": "STT module not loaded due to import error. Check server logs."}

# Import Gemini client functions
try:
    from stt_tts_modules.gemini_client import configure_gemini, get_gemini_response
except ImportError as e:
    logging.error(f"Error importing from gemini_client: {e}", exc_info=True)
    def configure_gemini():
        raise ImportError("Failed to import Gemini module components.")
    def get_gemini_response(text_prompt, conversation_history=None):
        return "Error: Gemini module not loaded due to import error."

# Import Resemble TTS client functions
try:
    from stt_tts_modules.resemble_tts_client import configure_resemble_tts, synthesize_speech_resemble
except ImportError as e:
    # Use app.logger if app is defined, otherwise global logging
    # Assuming app logger might not be available at this global level before app init
    logging.error(f"Error importing from resemble_tts_client: {e}", exc_info=True)
    # Define dummy functions if import fails
    def configure_resemble_tts():
        raise ImportError("Failed to import Resemble TTS module.")
    def synthesize_speech_resemble(text_to_speak):
        return {"error": "Resemble TTS module not loaded due to import error."}


app = Flask(__name__, static_folder='../frontend/static')

# Define the temporary directory for audio files within the backend directory
TEMP_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "temp_audio")

# Global flag to track initialization
_app_initialized = False

def initialize_app():
    """Initialize the application components"""
    global _app_initialized
    
    if _app_initialized:
        return
    
    # Create the temporary audio directory if it doesn't exist
    # exist_ok=True prevents an error if the directory already exists
    os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
    app.logger.info(f"Temporary audio directory is: {TEMP_AUDIO_DIR}")

    # Pre-load STT model
    try:
        app.logger.info("Attempting to pre-load STT model (openai/whisper-base.en)...")
        load_stt_model()
        app.logger.info("STT model pre-loading process initiated.")
    except Exception as e:
        # Log the full exception details
        app.logger.error(f"Failed to pre-load STT model: {e}", exc_info=True)
        # The app will still run; /transcribe will indicate errors if the model isn't available.

    # Initialize Gemini Client
    try:
        app.logger.info("Attempting to configure Gemini client...")
        configure_gemini()
        app.logger.info("Gemini client configuration process initiated.")
    except ValueError as ve: # Specifically for API key issues from configure_gemini
        app.logger.error(f"Gemini configuration failed: {ve}", exc_info=True)
    except Exception as e: # Catch broader exceptions for Gemini config
        app.logger.error(f"Failed to configure Gemini client: {e}", exc_info=True)

    # Initialize Resemble TTS Client
    try:
        app.logger.info("Attempting to configure Resemble TTS client...")
        configure_resemble_tts()
        app.logger.info("Resemble TTS client configuration process initiated.")
    except ValueError as ve: # Specifically for API key / UUID issues
        app.logger.error(f"Resemble TTS configuration failed: {ve}", exc_info=True)
    except Exception as e:
        app.logger.error(f"Failed to configure Resemble TTS client: {e}", exc_info=True)
    
    _app_initialized = True

@app.before_request
def ensure_initialized():
    """Ensure app is initialized before handling any request"""
    initialize_app()

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/hello')
def hello():
    return "Hello from Backend!"

@app.route('/transcribe', methods=['POST'])
def transcribe_endpoint():
    if 'audio_data' not in request.files:
        app.logger.warning("Transcription request failed: No 'audio_data' file part in the request.")
        return jsonify({"error": "No audio file part"}), 400

    file = request.files['audio_data']
    if file.filename == '':
        app.logger.warning("Transcription request failed: No file selected by the client.")
        return jsonify({"error": "No selected file"}), 400

    if file:
        # Sanitize filename and create a unique name to prevent issues
        original_filename = file.filename
        _, extension = os.path.splitext(original_filename)
        if not extension:
            app.logger.warning(f"Uploaded file '{original_filename}' has no extension. Defaulting to '.wav'.")
            extension = ".wav" # Whisper pipeline often expects a common audio extension

        unique_filename = str(uuid.uuid4()) + extension
        temp_filepath = os.path.join(TEMP_AUDIO_DIR, unique_filename)

        try:
            file.save(temp_filepath)
            app.logger.info(f"Audio file '{original_filename}' saved temporarily as {temp_filepath}")

            # Perform transcription using the STT module
            result = transcribe_audio_file(temp_filepath)

            if "error" in result:
                app.logger.error(f"Transcription failed for {temp_filepath} (original: {original_filename}): {result['error']}")
                if "STT model is not loaded" in result["error"]:
                    return jsonify(result), 503 # Service Unavailable: Model not ready
                return jsonify(result), 500 # Internal Server Error for other transcription errors

            app.logger.info(f"Transcription successful for {temp_filepath} (original: {original_filename}).")
            return jsonify(result), 200 # OK

        except Exception as e:
            app.logger.error(f"Unhandled exception during file processing or transcription for {original_filename}: {e}", exc_info=True)
            return jsonify({"error": "Server error during transcription process"}), 500
        finally:
            # Clean up the temporary file in all cases (success or failure)
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                    app.logger.info(f"Temporary file {temp_filepath} removed.")
                except OSError as e:
                    app.logger.error(f"Error removing temporary file {temp_filepath}: {e}", exc_info=True)

    # This part should ideally not be reached if file checks are done correctly
    app.logger.error("File processing failed unexpectedly before transcription could start or after an unhandled issue.")
    return jsonify({"error": "File processing failed due to an unexpected issue"}), 500

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    data = request.get_json()
    if not data or 'text' not in data:
        app.logger.warning("Chat request failed: Missing 'text' in JSON payload.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    user_text = data['text']
    # History is optional, pass it if provided by client
    conversation_history = data.get('history', [])

    app.logger.info(f"Received chat request: '{user_text}', history length: {len(conversation_history)}")

    try:
        bot_response = get_gemini_response(user_text, conversation_history)

        if bot_response.startswith("Error:"):
            app.logger.error(f"Gemini response error: {bot_response}")
            # Check for specific common errors to return appropriate status codes
            if "API key" in bot_response:
                 return jsonify({"error": bot_response}), 503 # Service Unavailable (config issue)
            return jsonify({"error": bot_response}), 500 # Internal Server Error

        app.logger.info(f"Gemini bot response: '{bot_response}'")
        return jsonify({"response": bot_response}), 200
    except Exception as e:
        app.logger.error(f"Exception in /chat endpoint: {e}", exc_info=True)
        return jsonify({"error": "Server error during chat processing"}), 500

@app.route('/synthesize', methods=['POST'])
def synthesize_endpoint():
    data = request.get_json()
    if not data or 'text' not in data:
        app.logger.warning("/synthesize request failed: Missing 'text' in JSON payload.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    text_to_synthesize = data['text']
    app.logger.info(f"Received /synthesize request for text: '{text_to_synthesize[:50]}...'")

    try:
        synthesis_result = synthesize_speech_resemble(text_to_synthesize)

        if "error" in synthesis_result:
            app.logger.error(f"Resemble TTS synthesis error: {synthesis_result['error']}")
            if "configuration error" in synthesis_result['error'] or "not set" in synthesis_result['error']:
                 return jsonify(synthesis_result), 503 # Service Unavailable (config issue)
            return jsonify(synthesis_result), 500 # Internal Server Error for other synthesis errors

        if "audio_url" in synthesis_result:
            app.logger.info(f"Resemble TTS synthesis successful. Audio URL: {synthesis_result['audio_url']}")
            return jsonify({"audio_url": synthesis_result['audio_url']}), 200
        else:
            app.logger.error(f"Resemble TTS did not return an audio URL or known error. Result: {synthesis_result}")
            return jsonify({"error": "TTS synthesis failed to return audio URL."}), 500

    except Exception as e:
        app.logger.error(f"Exception in /synthesize endpoint: {e}", exc_info=True)
        return jsonify({"error": "Server error during speech synthesis"}), 500

if __name__ == '__main__':
    # Flask's development server.
    # For production, a WSGI server like Gunicorn or uWSGI should be used.
    # Model loading via initialization function is suitable for dev mode.
    # For production, consider loading models when worker processes start.
    app.run(debug=True, port=5000, host='0.0.0.0') # Listen on all interfaces