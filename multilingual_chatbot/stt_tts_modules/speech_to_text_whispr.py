import torch
from transformers import pipeline
import os

ASR_PIPELINE = None
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
MODEL_LOADED = False

# Default model is now the multilingual 'whisper-base'
DEFAULT_MODEL_NAME = "openai/whisper-base"

def load_stt_model(model_name=DEFAULT_MODEL_NAME): # Use the new default
    global ASR_PIPELINE, MODEL_LOADED, DEVICE

    # Check if the requested model is already loaded
    if MODEL_LOADED and ASR_PIPELINE and hasattr(ASR_PIPELINE, 'model') and \
       hasattr(ASR_PIPELINE.model, 'name_or_path') and ASR_PIPELINE.model.name_or_path == model_name:
        print(f"STT model '{model_name}' already loaded.")
        return

    # If a different model was loaded, or not loaded, proceed to load the requested one
    MODEL_LOADED = False # Reset flag if we're changing models or loading for the first time
    ASR_PIPELINE = None  # Ensure pipeline is reset before loading new model

    print(f"Loading STT model ({model_name}) on device: {DEVICE}...")
    try:
        ASR_PIPELINE = pipeline(
            "automatic-speech-recognition",
            model=model_name,
            chunk_length_s=30,
            device=DEVICE,
            framework="pt" # Ensure PyTorch is used
        )
        MODEL_LOADED = True
        print(f"STT Pipeline '{model_name}' loaded successfully on {DEVICE}.")
    except Exception as e:
        MODEL_LOADED = False
        ASR_PIPELINE = None # Explicitly set to None on failure
        print(f"Error loading STT pipeline '{model_name}': {e}")
        raise # Re-raise to notify the caller (app.py)

def transcribe_audio_file(audio_filepath):
    global ASR_PIPELINE, MODEL_LOADED
    if not MODEL_LOADED or ASR_PIPELINE is None:
        print("STT model not pre-loaded or ASR_PIPELINE is None. Attempting to load default model...")
        try:
            load_stt_model() # Load default model (now multilingual)
        except Exception as e:
            # This error will be a string, not a dict, so the calling app.py endpoint needs to handle it.
            # For consistency, return a dict, but this part of app.py might need adjustment if it expects only dicts.
            print(f"STT model could not be loaded during transcription attempt: {str(e)}")
            return {"error": f"STT model could not be loaded: {str(e)}"}

        if not MODEL_LOADED or ASR_PIPELINE is None: # Check again
             return {"error": "STT model is not available even after attempting to load."}


    if not os.path.exists(audio_filepath):
        return {"error": f"Audio file not found: {audio_filepath}"}

    try:
        current_model_name = ASR_PIPELINE.model.name_or_path if ASR_PIPELINE and hasattr(ASR_PIPELINE, 'model') else "Unknown"
        print(f"Transcribing audio file: {audio_filepath} using model '{current_model_name}'...")

        # For multilingual models, the pipeline usually detects language automatically.
        # The exact way to get language depends on pipeline version and task configuration.
        # We can pass `return_timestamps=True` or other flags to potentially get more metadata.
        # Or, sometimes language is part of the main output.
        # The `tokenizer` of the pipeline might also have language info after processing.

        # Call pipeline to get transcription
        # Some pipelines might allow generate_kwargs={"language": "en"} to force lang,
        # but we want auto-detection.
        prediction = ASR_PIPELINE(audio_filepath)
        text = prediction["text"]

        detected_language = None
        # Try to extract language from prediction if available. This can be highly variable.
        # Some pipelines might return a dict like {'text': '...', 'chunks': [{'language': 'en', ...}]}
        # or {'text': '...', 'language': 'en'} directly.
        if isinstance(prediction, dict):
            if "language" in prediction: # Direct language key
                detected_language = prediction["language"]
            elif "chunks" in prediction and isinstance(prediction["chunks"], list) and len(prediction["chunks"]) > 0:
                # Check if language is in the first chunk (common for some Whisper pipeline setups)
                if isinstance(prediction["chunks"][0], dict) and "language" in prediction["chunks"][0]:
                    detected_language = prediction["chunks"][0]["language"]

        # Fallback: Check tokenizer if it has language information (less reliable for per-transcription)
        if not detected_language:
            if hasattr(ASR_PIPELINE, 'tokenizer') and hasattr(ASR_PIPELINE.tokenizer, 'language') and ASR_PIPELINE.tokenizer.language:
                # This might be the model's default language or last used, not always current detection
                print(f"Found language in tokenizer: {ASR_PIPELINE.tokenizer.language}. This might not be the detected language for this specific file.")
                # detected_language = ASR_PIPELINE.tokenizer.language # Uncomment if this behavior is desired as a fallback

        print(f"Transcription result: {text}")
        if detected_language:
            print(f"Detected language: {detected_language}")
            return {"text": text, "language": detected_language}
        else:
            print("Language detection data not found in standard output fields for this transcription.")
            return {"text": text}

    except Exception as e:
        print(f"Error during transcription: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    print("Running speech_to_text_whispr.py in standalone mode (multilingual).")
    print(f"Attempting to use device: {DEVICE}")
    try:
        load_stt_model() # Load default multilingual model (openai/whisper-base)
        if MODEL_LOADED and ASR_PIPELINE:
            print(f"Model '{ASR_PIPELINE.model.name_or_path}' loaded. To test, call transcribe_audio_file('path/to/audio.wav')")
            print("Consider using a non-English audio file for a more thorough multilingual test.")
            # Example (requires a dummy audio file to be present for actual testing):
            # if os.path.exists("dummy_audio_multilingual.wav"):
            #     result = transcribe_audio_file("dummy_audio_multilingual.wav")
            #     print(f"Standalone test transcription result: {result}")
            # else:
            #     print("Dummy audio file 'dummy_audio_multilingual.wav' not found. Skipping transcription test.")
        else:
            print(f"STT Model '{DEFAULT_MODEL_NAME}' could not be loaded.")
    except Exception as e:
        print(f"Error in standalone test setup for speech_to_text_whispr.py: {e}")
