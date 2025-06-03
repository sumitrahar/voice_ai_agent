import os
import google.generativeai as genai

GENERATIVE_MODEL = None
MODEL_INITIALIZED = False
CONVERSATION_HISTORY_LIMIT = 10 # Max number of (user, model) turns to keep

# Default prompt to guide the chatbot's behavior
DEFAULT_SYSTEM_PROMPT = "You are a helpful and concise multilingual conversational assistant. Respond in the language of the user's prompt if you can determine it, otherwise use English. Keep your answers brief."

def configure_gemini():
    global GENERATIVE_MODEL, MODEL_INITIALIZED
    if MODEL_INITIALIZED:
        print("Gemini model already configured.")
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        # MODEL_INITIALIZED remains False
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    try:
        genai.configure(api_key=api_key)
        # Using gemini-1.5-flash as it's fast and capable for chat.
        # For more complex tasks or if issues arise, gemini-pro could be used.
        GENERATIVE_MODEL = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=DEFAULT_SYSTEM_PROMPT
        )
        MODEL_INITIALIZED = True
        print("Gemini client configured successfully with model 'gemini-1.5-flash'.")
    except Exception as e:
        MODEL_INITIALIZED = False
        print(f"Error configuring Gemini client: {e}")
        raise # Re-raise the exception

def get_gemini_response(user_prompt: str, conversation_history: list = None):
    global GENERATIVE_MODEL, MODEL_INITIALIZED

    if not MODEL_INITIALIZED or GENERATIVE_MODEL is None:
        # Attempt to configure if not already done (e.g., if initial app load failed)
        try:
            print("Gemini model not initialized. Attempting to configure now...")
            configure_gemini()
        except ValueError as ve: # Specifically catch API key error
             return f"Error: Gemini API key not set. {str(ve)}"
        except Exception as e:
            return f"Error: Gemini model could not be initialized. {str(e)}"

        if not MODEL_INITIALIZED or GENERATIVE_MODEL is None: # Check again after attempt
            return "Error: Gemini model is not available."

    try:
        # Construct the chat history for Gemini API
        # The history format expected by Gemini is a list of Content objects (parts: text, role: user/model)
        # For simplicity, we'll manage history as a list of dictionaries [{role: 'user'/'model', 'parts': [text_prompt]}]
        # and pass it directly to start_chat.

        current_chat_session_messages = []
        if conversation_history:
            for entry in conversation_history[-CONVERSATION_HISTORY_LIMIT:]: # Use last N turns
                # Ensure role and parts structure
                if 'role' in entry and 'parts' in entry:
                     current_chat_session_messages.append(entry)
                elif 'text' in entry and 'sender' in entry: # Adapt from a simpler format if needed
                    role = 'user' if entry['sender'] == 'user' else 'model'
                    current_chat_session_messages.append({'role': role, 'parts': [{'text': entry['text']}]})


        # Start a new chat session or use an existing one if state management is more complex
        # For stateless requests per /chat call, we re-start chat with history
        chat = GENERATIVE_MODEL.start_chat(history=current_chat_session_messages)

        print(f"Sending to Gemini: '{user_prompt}' with history length: {len(current_chat_session_messages)}")
        response = chat.send_message(user_prompt)

        # Extract text from response
        # Response object can have complex structure, need to access text part
        if response and response.parts:
            # Join parts if there are multiple, though for text prompts usually one part.
            bot_response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
            if not bot_response_text and response.candidates and response.candidates[0].content.parts:
                 bot_response_text = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))

            print(f"Gemini response: {bot_response_text}")
            return bot_response_text
        elif response and hasattr(response, 'text') and response.text: # Older API or simpler response
            print(f"Gemini response (simple): {response.text}")
            return response.text
        else:
            # Log the full response if text extraction fails, to help debug
            print(f"Gemini response did not contain expected text. Full response: {response}")
            return "Error: Received an empty or unexpected response from Gemini."

    except Exception as e:
        print(f"Error getting response from Gemini: {e}")
        # Check for specific API errors if possible, e.g., related to API key or quota
        error_message = str(e)
        if "API_KEY_INVALID" in error_message or "API_KEY_MISSING" in error_message:
            return "Error: Gemini API key is invalid or missing. Please check server configuration."
        return f"Error communicating with Gemini: {error_message}"

if __name__ == "__main__":
    print("Running gemini_client.py in standalone mode.")
    try:
        configure_gemini() # Requires GEMINI_API_KEY to be set in environment
        if MODEL_INITIALIZED:
            print("Gemini client configured. Testing a simple prompt...")
            # Example history (adjust to match expected structure if needed)
            sample_history = [
                {'role': 'user', 'parts': [{'text': "Hello there!"}]},
                {'role': 'model', 'parts': [{'text': "Hi! How can I help you today?"}]}
            ]
            test_prompt = "What's the weather like in Paris?"
            response = get_gemini_response(test_prompt, conversation_history=sample_history)
            print(f"Test Prompt: {test_prompt}")
            print(f"Test Response: {response}")
        else:
            print("Gemini client could not be initialized. Ensure GEMINI_API_KEY is set.")
    except ValueError as ve:
        print(ve) # API key not set error
    except Exception as e:
        print(f"Error in standalone test: {e}")
