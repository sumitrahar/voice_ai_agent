import os
from resemble import Resemble # Assuming this is the correct import for Resemble AI SDK
import logging

logger = logging.getLogger(__name__)

RESEMBLE_API_KEY_ENV = "RESEMBLE_API_KEY"
RESEMBLE_PROJECT_UUID_ENV = "RESEMBLE_PROJECT_UUID"
RESEMBLE_VOICE_UUID_ENV = "RESEMBLE_VOICE_UUID"

TTS_CONFIGURED = False
PROJECT_UUID = None
VOICE_UUID = None

def configure_resemble_tts():
    global TTS_CONFIGURED, PROJECT_UUID, VOICE_UUID, Resemble # Make Resemble accessible

    if TTS_CONFIGURED:
        logger.info("Resemble TTS already configured.")
        return

    api_key = os.getenv(RESEMBLE_API_KEY_ENV)
    if not api_key:
        logger.error(f"Error: {RESEMBLE_API_KEY_ENV} environment variable not found.")
        raise ValueError(f"{RESEMBLE_API_KEY_ENV} not set.")

    Resemble.api_key(api_key)
    logger.info("Resemble API key configured.")

    # Get Project and Voice UUIDs
    PROJECT_UUID = os.getenv(RESEMBLE_PROJECT_UUID_ENV)
    VOICE_UUID = os.getenv(RESEMBLE_VOICE_UUID_ENV)

    if PROJECT_UUID and VOICE_UUID:
        logger.info(f"Using Project UUID: {PROJECT_UUID} and Voice UUID: {VOICE_UUID} from environment variables.")
    else:
        logger.warning("RESEMBLE_PROJECT_UUID or RESEMBLE_VOICE_UUID not set. Attempting to discover them.")
        try:
            projects = Resemble.v2.projects.all(1, 10)
            if not projects or not projects.get('items'):
                logger.error("No projects found in Resemble account.")
                raise ValueError("No Resemble projects found.")
            PROJECT_UUID = PROJECT_UUID or projects['items'][0]['uuid']

            voices = Resemble.v2.voices.all(1, 10)
            if not voices or not voices.get('items'):
                logger.error(f"No voices found in Resemble project {PROJECT_UUID}.")
                raise ValueError("No Resemble voices found.")
            VOICE_UUID = VOICE_UUID or voices['items'][0]['uuid']

            logger.info(f"Discovered and using Project UUID: {PROJECT_UUID}, Voice UUID: {VOICE_UUID}")
            logger.warning("For production, it's recommended to set RESEMBLE_PROJECT_UUID and RESEMBLE_VOICE_UUID environment variables.")

        except Exception as e:
            logger.error(f"Error discovering Resemble project/voice UUIDs: {e}", exc_info=True)
            raise ValueError(f"Could not determine Resemble project/voice UUIDs: {e}")

    TTS_CONFIGURED = True
    logger.info("Resemble TTS configured successfully.")


def synthesize_speech_resemble(text_to_speak: str, title: str = "ChatbotResponse"):
    global TTS_CONFIGURED, PROJECT_UUID, VOICE_UUID, Resemble

    if not TTS_CONFIGURED:
        try:
            logger.info("Resemble TTS not configured. Attempting to configure now...")
            configure_resemble_tts()
        except ValueError as ve:
            logger.error(f"Resemble TTS configuration failed: {ve}", exc_info=True)
            return {"error": f"Resemble TTS configuration error: {str(ve)}"}
        except Exception as e:
            logger.error(f"Unexpected error during Resemble TTS configuration: {e}", exc_info=True)
            return {"error": f"Resemble TTS unhandled configuration error: {str(e)}"}

        if not TTS_CONFIGURED: # Check again
             return {"error": "Resemble TTS is not available due to configuration issues."}


    if not PROJECT_UUID or not VOICE_UUID:
        logger.error("PROJECT_UUID or VOICE_UUID for Resemble TTS is not set.")
        return {"error": "Resemble TTS project/voice not configured."}

    try:
        logger.info(f"Requesting speech synthesis from Resemble for text: '{text_to_speak[:50]}...'")
        # The create_sync method returns a dictionary which includes a 'link' to the audio file.
        # We need the raw audio data if possible, or handle streaming the link.
        # The original script just printed the response. Let's assume 'link' provides a URL to an audio file.
        # For simplicity, this subtask will return this link.
        # A more advanced version would download the audio and return bytes.

        # Default output format is wav, sample rate 22050.
        # For web playback, mp3 might be better if Resemble supports it directly or if we convert.
        # The create_sync function takes 'output_format' (wav, pcm, mp3) and 'sample_rate'.
        clip_response = Resemble.v2.clips.create_sync(
            project_uuid=PROJECT_UUID,
            voice_uuid=VOICE_UUID,
            body=text_to_speak,
            title=title,
            is_public=False, # Keep clips private unless specified
            is_archived=False,
            sample_rate=22050, # Common sample rate, can be 44100 for higher quality
            output_format="mp3" # Request MP3 for web compatibility
        )

        if clip_response and clip_response.get('success') and clip_response.get('item'):
            audio_url = clip_response['item'].get('audio_src') # The key might be 'audio_src' or 'link' or similar
            if not audio_url: # Fallback check for different key names
                audio_url = clip_response['item'].get('link')

            if audio_url:
                logger.info(f"Resemble TTS successful. Audio URL: {audio_url}")
                return {"audio_url": audio_url} # Return the URL of the MP3 audio
            else:
                logger.error(f"Resemble TTS response missing audio URL. Response: {clip_response}")
                return {"error": "Resemble TTS response did not contain an audio URL."}
        else:
            error_detail = clip_response.get('message', 'Unknown error from Resemble API.') if clip_response else 'No response from Resemble API.'
            logger.error(f"Resemble TTS failed. Success: {clip_response.get('success') if clip_response else 'N/A'}. Details: {error_detail}")
            return {"error": f"Resemble TTS failed: {error_detail}"}

    except Exception as e:
        logger.error(f"Error during Resemble speech synthesis: {e}", exc_info=True)
        return {"error": f"Exception during Resemble speech synthesis: {str(e)}"}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Running resemble_tts_client.py in standalone mode.")
    # Required: RESEMBLE_API_KEY
    # Optional: RESEMBLE_PROJECT_UUID, RESEMBLE_VOICE_UUID
    # Example: export RESEMBLE_API_KEY="your_key_here"
    # export RESEMBLE_PROJECT_UUID="your_project_uuid"
    # export RESEMBLE_VOICE_UUID="your_voice_uuid"
    try:
        configure_resemble_tts()
        if TTS_CONFIGURED:
            logger.info("Resemble TTS client configured. Testing synthesis...")
            test_text = "Hello from the Resemble TTS client!"
            result = synthesize_speech_resemble(test_text)
            if "audio_url" in result:
                logger.info(f"Test synthesis successful. Audio URL: {result['audio_url']}")
            else:
                logger.error(f"Test synthesis failed. Error: {result.get('error')}")
        else:
            logger.error("Resemble TTS client could not be initialized. Ensure API key and UUIDs are correctly set.")
    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
    except Exception as e:
        logger.error(f"Error in standalone test: {e}", exc_info=True)
