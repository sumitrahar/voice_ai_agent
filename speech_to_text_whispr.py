import torch
from transformers import pipeline
from datasets import load_dataset

# Determine the device (GPU if available, otherwise CPU)
device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Initialize the ASR pipeline
# We explicitly set framework="pt" to use PyTorch and avoid Keras 3 issues with TensorFlow.
# If you installed 'tf-keras' and want to use TensorFlow, you can remove framework="pt",
# but PyTorch is generally well-supported and recommended for Hugging Face models.
try:
    pipe = pipeline(
      "automatic-speech-recognition",
      model="openai/whisper-base.en", # Using a smaller base model for quicker testing
      chunk_length_s=30,
      device=device,
      framework="pt"  # Explicitly use PyTorch backend
    )
    print("Pipeline loaded successfully.")
except Exception as e:
    print(f"Error loading pipeline: {e}")
    exit()

# Load a dummy dataset for testing
try:
    ds = load_dataset("hf-internal-testing/librispeech_asr_dummy", "clean", split="validation")
    print("Dataset loaded successfully.")
except Exception as e:
    print(f"Error loading dataset: {e}")
    exit()

# Get a sample from the dataset
# ds[0]["audio"] is a dictionary containing 'path', 'array', 'sampling_rate'
# The pipeline expects the raw audio waveform, which is in 'array'
audio_sample_dict = ds[0]["audio"]
audio_input = audio_sample_dict["array"] # This is the NumPy array of the audio
sampling_rate = audio_sample_dict["sampling_rate"]

print(f"Audio sample loaded. Duration: {len(audio_input)/sampling_rate:.2f}s, Sampling rate: {sampling_rate} Hz")

# Perform prediction to get text
# We pass a copy of the audio array to the pipeline
try:
    print("Performing prediction (text only)...")
    # The pipeline can also accept a dictionary like {'raw': audio_input, 'sampling_rate': sampling_rate}
    # or just the raw array if the model's processor can infer/handle the sampling rate (Whisper's can).
    prediction_output = pipe(audio_input.copy(), batch_size=8)
    text_prediction = prediction_output["text"]
    print(f"Prediction (text only): {text_prediction}")
except Exception as e:
    print(f"Error during text-only prediction: {e}")

# Perform prediction to get timestamps
try:
    print("\nPerforming prediction (with timestamps)...")
    # The pipeline can also accept a dictionary like {'raw': audio_input, 'sampling_rate': sampling_rate}
    # or just the raw array if the model's processor can infer/handle the sampling rate (Whisper's can).
    prediction_with_timestamps_output = pipe(audio_input.copy(), batch_size=8, return_timestamps=True)
    chunks_prediction = prediction_with_timestamps_output["chunks"]
    print(f"Prediction (with timestamps/chunks):")
    for i, chunk in enumerate(chunks_prediction):
        print(f"  Chunk {i+1}: \"{chunk['text']}\" (Timestamp: {chunk['timestamp'][0]:.2f}s - {chunk['timestamp'][1]:.2f}s)")
except Exception as e:
    print(f"Error during prediction with timestamps: {e}")

print("\nScript finished.")