document.addEventListener('DOMContentLoaded', () => {
    // --- Existing Hello World Logic (Optional) ---
    const helloButton = document.getElementById('helloButton');
    const responseParagraph = document.getElementById('response');
    if (helloButton && responseParagraph) {
        helloButton.addEventListener('click', () => {
            fetch('/hello')
                .then(response => response.text())
                .then(data => { responseParagraph.textContent = data; })
                .catch(error => {
                    console.error('Error fetching from /hello:', error);
                    responseParagraph.textContent = 'Error connecting to backend.';
                });
        });
    }

    // --- STT Elements and Logic ---
    const recordButton = document.getElementById('recordButton');
    const stopButton = document.getElementById('stopButton');
    const audioPlayback = document.getElementById('audioPlayback');
    const statusMessage = document.getElementById('statusMessage'); // For STT status

    let mediaRecorder;
    let audioChunks = [];
    let mediaStream = null;

    // --- Chat Elements and Logic ---
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    const chatOutput = document.getElementById('chatOutput');
    const chatStatus = document.getElementById('chatStatus');
    const ttsAudioPlayback = document.getElementById('ttsAudioPlayback');

    let conversationHistory = [];
    const MAX_HISTORY_LENGTH = 20;

    // Helper function to stop ongoing TTS
    function stopTTSPlayback() {
        if (ttsAudioPlayback && !ttsAudioPlayback.paused) {
            ttsAudioPlayback.pause();
            ttsAudioPlayback.src = ""; // Clear source
            if (chatStatus) chatStatus.textContent = "Chatbot speech interrupted.";
            console.log("TTS playback stopped due to user interruption.");
            // Remove onended/onerror handlers
            ttsAudioPlayback.onended = null;
            ttsAudioPlayback.onerror = null;
        }
    }

    function appendMessageToChat(sender, message, type = 'normal') {
        const messageElement = document.createElement('p');
        let content = `<strong>${sender}:</strong> `;

        const sanitizedMessage = message.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        content += sanitizedMessage.replace(/\n/g, '<br>');

        messageElement.innerHTML = content;
        if (type === 'error') {
            messageElement.style.color = 'red';
        } else if (type === 'system') {
            messageElement.style.fontStyle = 'italic';
            messageElement.style.color = 'grey';
        }
        chatOutput.appendChild(messageElement);
        chatOutput.scrollTop = chatOutput.scrollHeight;
    }

    async function playTextAsSpeech(text) {
        if (!text.trim()) return;
        if (!ttsAudioPlayback) {
            console.warn("TTS audio element not found. Cannot play speech.");
            if (chatStatus) chatStatus.textContent = "TTS Player not found.";
            return;
        }

        // Ensure any previous TTS is stopped before starting new synthesis/playback
        // This is a good secondary place for it, though primary interruption is at user input points.
        stopTTSPlayback();

        const originalChatStatus = chatStatus ? chatStatus.textContent : "";
        if (chatStatus) chatStatus.textContent = 'Synthesizing speech...';

        try {
            const response = await fetch('/synthesize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });

            const result = await response.json();

            if (response.ok && result.audio_url) {
                if (chatStatus) chatStatus.textContent = 'Speech synthesized. Playing...';
                ttsAudioPlayback.src = result.audio_url;

                try {
                    await ttsAudioPlayback.play();
                    if (chatStatus) chatStatus.textContent = 'Playing audio...';

                    ttsAudioPlayback.onended = () => {
                        if (chatStatus) chatStatus.textContent = 'Audio finished.';
                    };
                    ttsAudioPlayback.onerror = (e) => {
                        console.error("Error playing TTS audio:", e);
                        if (chatStatus) chatStatus.textContent = 'Error playing audio.';
                        appendMessageToChat('System', 'Could not play TTS audio. Playback error.', 'error');
                    };

                } catch (playError) {
                    console.error("Autoplay was prevented or error during play:", playError);
                    if (chatStatus) chatStatus.textContent = 'Could not autoplay speech.';
                    appendMessageToChat('System', `Speech synthesized. <a href="${result.audio_url}" target="_blank" rel="noopener noreferrer">Play audio</a> (Autoplay blocked or failed)`, 'system');
                }
            } else {
                const errorMessage = `TTS Synthesis Error: ${result.error || 'Unknown TTS error'}`;
                console.error(errorMessage);
                if (chatStatus) chatStatus.textContent = 'Failed to synthesize speech.';
                appendMessageToChat('System', errorMessage, 'error');
            }
        } catch (error) {
            console.error('Error fetching synthesized speech:', error);
            if (chatStatus) chatStatus.textContent = 'Network error during TTS request.';
            appendMessageToChat('System', 'Network error: Could not fetch synthesized speech.', 'error');
        }
    }

    async function sendChatMessage(text) {
        stopTTSPlayback(); // Interrupt TTS if user sends new message
        if (!text.trim()) return;

        appendMessageToChat('User', text);
        conversationHistory.push({ role: 'user', parts: [{ text: text }] });

        if (conversationHistory.length > MAX_HISTORY_LENGTH) {
            conversationHistory = conversationHistory.slice(conversationHistory.length - MAX_HISTORY_LENGTH);
        }

        if (chatStatus) chatStatus.textContent = 'Bot is thinking...';
        if(chatInput) chatInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, history: conversationHistory })
            });

            const result = await response.json();

            if (response.ok && result.response) {
                const botResponseText = result.response;
                appendMessageToChat('Bot', botResponseText);
                conversationHistory.push({ role: 'model', parts: [{ text: botResponseText }] });

                await playTextAsSpeech(botResponseText);

                if (chatStatus && !chatStatus.textContent.includes('Playing') && !chatStatus.textContent.includes('Synthesizing') && !chatStatus.textContent.includes('Speech synthesized') && !chatStatus.textContent.includes('interrupted')) {
                    chatStatus.textContent = 'Response received; TTS processed.';
                }

            } else {
                const errorMessage = `Chat Error: ${result.error || 'Unknown error from backend'}`;
                appendMessageToChat('Bot', errorMessage, 'error');
                if (chatStatus) chatStatus.textContent = 'Failed to get chat response.';
            }
        } catch (error) {
            console.error('Error sending chat message:', error);
            const networkError = 'Network error. Could not connect to chat backend.';
            appendMessageToChat('Bot', networkError, 'error');
            if (chatStatus) chatStatus.textContent = 'Network error during chat.';
        }
    }

    if (sendButton && chatInput) {
        sendButton.addEventListener('click', () => {
            sendChatMessage(chatInput.value);
        });

        chatInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                sendChatMessage(chatInput.value);
                event.preventDefault();
            }
        });
    } else {
        console.warn("Chat input or send button not found. Chat functionality disabled.");
        if(chatStatus) chatStatus.textContent = "Chat UI elements not fully loaded.";
    }

    // --- STT Functionality Integration ---
    if (recordButton && stopButton && audioPlayback && statusMessage && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        console.log("STT elements found and media APIs supported.");

        recordButton.addEventListener('click', async () => {
            stopTTSPlayback(); // Interrupt TTS if user starts new recording
            if (statusMessage) statusMessage.textContent = "Requesting microphone permission...";
            audioChunks = [];
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(mediaStream);

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    if (statusMessage) statusMessage.textContent = "Processing audio for transcription...";
                    if (audioChunks.length === 0) {
                        if (statusMessage) statusMessage.textContent = "No audio recorded.";
                        recordButton.disabled = false;
                        stopButton.disabled = true;
                        if (mediaStream) {
                            mediaStream.getTracks().forEach(track => track.stop());
                            mediaStream = null;
                        }
                        return;
                    }

                    const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });

                    let fileExtension = ".webm";
                    if (mediaRecorder.mimeType) {
                        if (mediaRecorder.mimeType.includes("ogg")) fileExtension = ".ogg";
                        else if (mediaRecorder.mimeType.includes("wav")) fileExtension = ".wav";
                        else if (mediaRecorder.mimeType.includes("mp4")) fileExtension = ".mp4";
                    }
                    const audioFile = new File([audioBlob], `audio_recording${fileExtension}`, { type: mediaRecorder.mimeType || 'audio/webm' });

                    const audioUrl = URL.createObjectURL(audioBlob);
                    if (audioPlayback) audioPlayback.src = audioUrl;

                    const formData = new FormData();
                    formData.append('audio_data', audioFile);

                    try {
                        const transcribeResponse = await fetch('/transcribe', {
                            method: 'POST',
                            body: formData
                        });
                        const transcribeResult = await transcribeResponse.json();

                        if (transcribeResponse.ok && transcribeResult.text) {
                            if (statusMessage) statusMessage.textContent = "Transcription successful. Sending to chat...";
                            if (chatInput) {
                                chatInput.value = transcribeResult.text;
                                await sendChatMessage(transcribeResult.text);
                            } else {
                                appendMessageToChat('System (Transcribed)', transcribeResult.text, 'system');
                            }
                        } else {
                            const errMsg = `Transcription Error: ${transcribeResult.error || 'Unknown error'}`;
                            if (statusMessage) statusMessage.textContent = errMsg;
                            appendMessageToChat('System', errMsg, 'error');
                        }
                    } catch (transcribeError) {
                        console.error('Error during transcription request:', transcribeError);
                        const errMsg = 'Error: Could not connect for transcription.';
                        if (statusMessage) statusMessage.textContent = errMsg;
                        appendMessageToChat('System', errMsg, 'error');
                    } finally {
                        URL.revokeObjectURL(audioUrl);
                        audioChunks = [];
                        if (mediaStream) {
                            mediaStream.getTracks().forEach(track => track.stop());
                            mediaStream = null;
                        }
                        recordButton.disabled = false;
                        stopButton.disabled = true;
                    }
                };

                mediaRecorder.start();
                if (statusMessage) statusMessage.textContent = "Recording... Click 'Stop Recording' when done.";
                recordButton.disabled = true;
                stopButton.disabled = false;

            } catch (err) {
                console.error("Error accessing microphone:", err);
                if (statusMessage) statusMessage.textContent = `Mic Error: ${err.message}`;
                appendMessageToChat('System', `Microphone access error: ${err.message}. Please grant permission.`, 'error');
                recordButton.disabled = false;
                stopButton.disabled = true;
            }
        });

        stopButton.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop();
                if (statusMessage) statusMessage.textContent = "Stopping recording...";
            }
        });

    } else {
        const sttNotSupportedMsg = "Audio recording (STT) is not fully supported or some STT UI elements are missing.";
        if(statusMessage) statusMessage.textContent = sttNotSupportedMsg;
        else if(chatStatus) chatStatus.textContent = sttNotSupportedMsg;

        if(recordButton) recordButton.disabled = true;
        if(stopButton) stopButton.disabled = true;
        console.warn(sttNotSupportedMsg);
        if (chatOutput && !statusMessage && !chatStatus) {
             appendMessageToChat('System', sttNotSupportedMsg, 'system');
        }
    }
});
