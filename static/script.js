const talkBtn = document.getElementById("talkBtn");
const chatBtn = document.getElementById("chatBtn");
const chatOverlay = document.getElementById("chatOverlay");
const closeChatBtn = document.getElementById("closeChatBtn");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");
const chatSendBtn = document.getElementById("chatSendBtn");
const screenWatchBtn = document.getElementById("screenWatchBtn");
const screenStopBtn = document.getElementById("screenStopBtn");
const screenStatus = document.getElementById("screenStatus");

let screenStream = null;
let screenVideo = null;
let screenWatchTimer = null;
let screenAnalysisBusy = false;
let lastScreenReply = "";
let visionControlsVoice = false;

function setScreenStatus(text) {
    if (screenStatus) screenStatus.textContent = text;
}

function stopScreenWatching() {
    if (screenWatchTimer) {
        clearInterval(screenWatchTimer);
        screenWatchTimer = null;
    }
    if (screenStream) screenStream.getTracks().forEach((track) => track.stop());
    screenStream = null;
    if (screenVideo) {
        screenVideo.srcObject = null;
        screenVideo.remove();
        screenVideo = null;
    }
    screenAnalysisBusy = false;
    if (screenWatchBtn) screenWatchBtn.hidden = false;
    if (screenStopBtn) screenStopBtn.hidden = true;
    setScreenStatus("Screen sharing is off.");
    if (visionControlsVoice) stopVisionVoiceSession();
}

function stopVisionVoiceSession() {
    visionControlsVoice = false;
    voiceSessionActive = false;
    if (silenceTimer) clearTimeout(silenceTimer);
    silenceTimer = null;
    try { recognition.stop(); } catch (_) {}
    window.speechSynthesis.cancel();
    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
    talkBtn.classList.remove("voice-active");
}

async function analyzeScreenFrame(question = "") {
    if (!screenVideo || !screenStream || screenAnalysisBusy || screenVideo.readyState < 2) return;
    screenAnalysisBusy = true;
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 960 / (screenVideo.videoWidth || 960));
    canvas.width = Math.max(1, Math.round((screenVideo.videoWidth || 960) * scale));
    canvas.height = Math.max(1, Math.round((screenVideo.videoHeight || 540) * scale));
    canvas.getContext("2d").drawImage(screenVideo, 0, 0, canvas.width, canvas.height);
    setScreenStatus("Screen dekh rahi hoon…");

    try {
        const response = await fetch("/screen_analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                image: canvas.toDataURL("image/jpeg", 0.55),
                prompt: question || "Screen par abhi kya visible hai, aur pichhle frame se koi important change ho to short Roman Hindi me batao. Passwords, tokens ya private text ko repeat mat karo."
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Screen analysis failed");
        const reply = (data.reply || "Screen par kuch clearly dikh nahi raha.").trim();
        if (reply !== lastScreenReply) {
            lastScreenReply = reply;
            document.getElementById("response").textContent = reply;
            addChatMessage(reply, "ai");
            // Speak only changed observations so the watcher does not talk over itself.
            try {
                startChatAvatarReaction();
                await speak(reply);
            } catch (_) { /* speech is optional */ }
            finally { stopChatAvatarReaction(); }
        }
        setScreenStatus("● Watching screen — last update abhi hua");
    } catch (error) {
        setScreenStatus(error.message || "Screen analysis available nahi hai.");
    } finally {
        screenAnalysisBusy = false;
    }
}

async function startScreenWatching() {
    if (!navigator.mediaDevices?.getDisplayMedia) {
        setScreenStatus("Is browser me screen sharing supported nahi hai.");
        return;
    }
    try {
        setScreenStatus("Permission maang rahi hoon…");
        screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 1, max: 2 } },
            audio: false
        });
        screenVideo = document.createElement("video");
        screenVideo.muted = true;
        screenVideo.playsInline = true;
        screenVideo.srcObject = screenStream;
        await screenVideo.play();
        screenStream.getVideoTracks()[0].addEventListener("ended", stopScreenWatching, { once: true });
        screenWatchBtn.hidden = true;
        screenStopBtn.hidden = false;
        // Vision permission also enables hands-free voice questions. The mic
        // remains active for as long as the display-capture permission lives.
        visionControlsVoice = true;
        voiceSessionActive = true;
        startRecognitionLoop();
        lastScreenReply = "";
        await analyzeScreenFrame();
        screenWatchTimer = setInterval(analyzeScreenFrame, 6000);
    } catch (error) {
        stopScreenWatching();
        if (error.name === "NotAllowedError") setScreenStatus("Screen permission nahi mili. Jab chaho dobara Start dabao.");
        else setScreenStatus(error.message || "Screen share start nahi ho saka.");
    }
}

screenWatchBtn?.addEventListener("click", startScreenWatching);
screenStopBtn?.addEventListener("click", stopScreenWatching);

function setChatOpen(isOpen) {
    chatOverlay.classList.toggle("open", isOpen);
    chatOverlay.setAttribute("aria-hidden", String(!isOpen));
    document.querySelector(".avatar-box").classList.toggle("chat-hidden", isOpen);
    if (isOpen) setTimeout(() => chatInput.focus(), 250);
}

chatBtn.addEventListener("click", () => setChatOpen(true));
closeChatBtn.addEventListener("click", () => setChatOpen(false));
chatOverlay.addEventListener("click", (event) => {
    if (event.target === chatOverlay) setChatOpen(false);
});

function addChatMessage(text, type) {
    const message = document.createElement("div");
    message.className = `message ${type}-message`;
    message.textContent = text;
    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return message;
}

function naturalReplyDelay(text) {
    // A small, bounded pause makes chat feel conversational without being sluggish.
    const lengthPause = Math.min(1100, Math.max(250, (text || "").length * 14));
    return lengthPause + Math.floor(Math.random() * 260);
}

function startChatAvatarReaction() {
    triggerTalkAnimation();
    document.querySelector(".avatar-box")?.classList.add("chat-talking");
    // Activate AI circle animation
    const aiCircle = document.getElementById('aiCircle');
    if (aiCircle) {
        aiCircle.classList.add('active');
    }
}

function stopChatAvatarReaction() {
    stopTalkAnimation();
    document.querySelector(".avatar-box")?.classList.remove("chat-talking");
    // Deactivate AI circle animation
    const aiCircle = document.getElementById('aiCircle');
    if (aiCircle) {
        aiCircle.classList.remove('active');
    }
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = chatInput.value.trim();
    if (!text || chatSendBtn.disabled) return;

    addChatMessage(text, "user");
    chatInput.value = "";
    chatSendBtn.disabled = true;
    // Start music independently from the AI request. This means a missing or
    // slow Groq response cannot prevent a requested song from playing.
    const requestedSong = extractSongName(text);
    if (requestedSong) playSong(requestedSong);
    const typing = addChatMessage("Anaya is typing... ✨", "ai");
    typing.classList.add("typing");
    startChatAvatarReaction();

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.reply || "Chat request failed");
        await new Promise((resolve) => setTimeout(resolve, naturalReplyDelay(data.reply)));
        typing.remove();
        addChatMessage(data.reply || "Mujhe koi reply nahi mila.", "ai");
        document.getElementById("response").textContent = data.reply || "";
    } catch (error) {
        typing.remove();
        addChatMessage(error.message || "Abhi chat service available nahi hai.", "ai");
    } finally {
        stopChatAvatarReaction();
        chatSendBtn.disabled = false;
        chatInput.focus();
    }
});

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

// Speech recognition is not available in every browser (Firefox and many
// mobile browsers do not expose it). Keep the rest of the UI usable there.
const recognition = SpeechRecognition ? new SpeechRecognition() : {
    start() {
        throw new Error("Speech recognition is not supported by this browser.");
    }
};
recognition.onstart = () => {
    console.log("MIC STARTED");
};

recognition.onerror = (event) => {
    console.log("MIC ERROR:", event.error);
};

recognition.onend = () => {
    console.log("MIC STOPPED");
};
recognition.lang = "hi-IN";
recognition.interimResults = false;

window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("response").textContent = "";
});

let isListening = false;
let voiceSessionActive = false;
let voiceRequestInFlight = false;
let silenceTimer = null;
const SILENCE_LIMIT_MS = 10000;

function resetSilenceTimer() {
    if (silenceTimer) clearTimeout(silenceTimer);
    // Display capture is the explicit keep-alive permission for voice mode.
    if (!voiceSessionActive || screenStream) return;
    silenceTimer = setTimeout(() => {
        voiceSessionActive = false;
        silenceTimer = null;
        try { recognition.stop(); } catch (_) {}
        window.speechSynthesis.cancel();
        talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
        talkBtn.classList.remove("voice-active");
    }, SILENCE_LIMIT_MS);
}

talkBtn.addEventListener("click", () => {

    if (!SpeechRecognition) {
        alert("Voice input is not supported in this browser. Please use Chrome or Edge.");
        return;
    }

    if (voiceSessionActive) {
        if (visionControlsVoice) return;
        voiceSessionActive = false;
        isListening = false;
        try { recognition.stop(); } catch (_) {}
        window.speechSynthesis.cancel();
        talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
        talkBtn.classList.remove("voice-active");
        return;
    }

    voiceSessionActive = true;
    startRecognitionLoop();

});

function startRecognitionLoop() {
    if (!voiceSessionActive || isListening || voiceRequestInFlight) return;
    try {
        recognition.start();
        isListening = true;
        talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Listening… (tap to stop)`;
        talkBtn.classList.add("voice-active");
    } catch (_) {}
}

recognition.onend = () => {
    isListening = false;
    if (voiceSessionActive && !voiceRequestInFlight) setTimeout(startRecognitionLoop, 250);
    if (!voiceSessionActive) {
        talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
        talkBtn.classList.remove("voice-active");
    }
};


recognition.onresult = async (event) => {

    const text = event.results[0][0].transcript;
    resetSilenceTimer();
    window.speechSynthesis.cancel();
    const requestedSong = extractSongName(text);
    // Voice commands should launch playback immediately, before chat/TTS.
    if (requestedSong) playSong(requestedSong);

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Thinking...`;
    triggerTalkAnimation();

    voiceRequestInFlight = true;
    try {
        if (screenStream) {
            // While Vision is active, answer the spoken question against the
            // latest approved screen frame instead of a text-only chat call.
            await analyzeScreenFrame(`User ka sawal: "${text}". Current shared screen ko dekhkar short Roman Hindi me seedha jawab do. Agar screen par jawab nahi milta, clearly bolo ki screen par nahi dikh raha. Private passwords, tokens aur sensitive text repeat mat karo.`);
            return;
        }
        // Gemini ko message bhejna
        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: text
            })

        });


        const data = await response.json();
        const responseParagraph = document.getElementById("response");
        if (!response.ok) {
            throw new Error(data.reply || "Chat request failed");
        }
        const reply = (data.reply || "No reply received.")
            .replace(/\s+/g, " ")
            // Remove the sentence limit to allow full responses
            // .split(/(?<=[.!?।])\s+/)
            // .slice(0, 2)
            // .join(" ");
            .trim();
        responseParagraph.textContent = reply;

        // Use browser TTS with a normal female voice.
        await speak(reply);
        // Agar user ne song play karne ko bola hai
        resetSilenceTimer();


    } finally {
        voiceRequestInFlight = false;
        stopTalkAnimation();
        if (voiceSessionActive) {
            talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Listening… (tap to stop)`;
            setTimeout(startRecognitionLoop, 250);
        } else {
            talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
        }
    }

};

let availableVoices = [];

function refreshVoices() {
    availableVoices = window.speechSynthesis.getVoices();
    if (availableVoices.length) {
        console.log('Loaded speech voices:', availableVoices.map(v => `${v.name} (${v.lang})`));
    }
}

window.speechSynthesis.onvoiceschanged = refreshVoices;
refreshVoices();

function getVoiceString(voice) {
    return `${voice.name || ''} ${voice.lang || ''} ${voice.voiceURI || ''}`.toLowerCase();
}

async function getAvailableVoices() {
    let voices = availableVoices.length ? availableVoices : window.speechSynthesis.getVoices() || [];
    if (!voices.length) {
        await new Promise((resolve) => setTimeout(resolve, 250));
        voices = window.speechSynthesis.getVoices() || [];
    }
    return voices;
}

function selectFemaleVoice(voices) {
    const voiceKey = getVoiceString;
    const hindiLanguage = /^(hi|hi[-_]?in|hi-in|hindi)$/i;
    const femaleNames = [
        /aarti/, /priya/, /aditi/, /anya/, /uma/, /neha/, /swara/, /sunita/, /kalpana/, /geeta/, /lekha/, /prerna/, /google hindi/, /google हिन्दी/, /microsoft .*sunita/, /female/
    ];

    const femaleHindi = voices.find((voice) => {
        const text = voiceKey(voice);
        return hindiLanguage.test(voice.lang || '') && femaleNames.some((pattern) => pattern.test(text));
    });

    if (femaleHindi) return femaleHindi;

    const anyFemale = voices.find((voice) => femaleNames.some((pattern) => pattern.test(voiceKey(voice))));
    if (anyFemale) return anyFemale;

    const anyHindi = voices.find((voice) => hindiLanguage.test(voice.lang || '') || /hindi/.test(voiceKey(voice)));
    if (anyHindi) return anyHindi;

    const genericFemale = voices.find((voice) => /female/.test(voiceKey(voice)));
    if (genericFemale) return genericFemale;

    return voices[0] || null;
}

// AI ki awaaz
async function speak(text) {
    if (!text) return;

    const speech = new SpeechSynthesisUtterance(text);
    const voices = await getAvailableVoices();
    const selected = selectFemaleVoice(voices);

    if (selected) {
        speech.voice = selected;
        speech.lang = selected.lang || 'hi-IN';
        speech.volume = 1.0;
        speech.pitch = 1.0;
        speech.rate = 1.0;
        console.log('Speech voice selected:', selected.name, selected.lang);
    } else {
        speech.lang = 'hi-IN';
        speech.volume = 1.0;
        speech.pitch = 1.0;
        speech.rate = 1.0;
        console.log('No speech voices available yet.');
    }

    return new Promise((resolve, reject) => {
        speech.onend = () => {
            console.log('Speech ended, restarting microphone if voice session is active');
            // Restart microphone when AI finishes speaking
            if (voiceSessionActive && !visionControlsVoice) {
                setTimeout(startRecognitionLoop, 500);
            }
            resolve();
        };
        speech.onerror = (event) => reject(event.error || new Error('Speech synthesis error'));

        // Stop microphone when AI starts speaking
        if (isListening && voiceSessionActive) {
            console.log('AI starting to speak, stopping microphone');
            try {
                recognition.stop();
                isListening = false;
                // Update button to show AI is speaking
                if (!visionControlsVoice) {
                    talkBtn.innerHTML = `<i class="fas fa-microphone-slash"></i> AI Speaking...`;
                    talkBtn.classList.remove("voice-active");
                }
            } catch (e) {
                console.log('Error stopping recognition:', e);
            }
        }

        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(speech);
    });
}

// Server-side TTS playback: requests /tts and plays returned MP3. Throws on failure.
async function playTTS(text, gender = 'female') {
    const res = await fetch('/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, gender })
    });

    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error('TTS request failed: ' + res.status + ' ' + body);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await audio.play();
}

recognition.onerror = () => {

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;

    alert("Mic Error");

};
function extractSongName(text) {
    if (!text || typeof text !== "string") return "";

    // Match both English and common Roman-Hindi voice phrases. Keep this
    // client-side so playback can begin without waiting for /chat.
    const command = text.trim().replace(/[.!?]+$/, "");
    const requestPattern = /^(?:please\s+)?(?:play|listen(?:\s+to)?|put\s+on|start)\s+(?:the\s+)?(?:song\s+|music\s+)?(.+)$/iu;
    const hindiPattern = /^(?:please\s+)?(?:mujhe\s+)?(?:koi\s+)?(?:song|gaana|gana|music|गाना|सॉन्ग|म्यूजिक)\s+(?:bajao|chalao|sunao|suna do|play karo|बजाओ|चलाओ|सुनाओ)\s*(.*)$/iu;
    const reverseHindiPattern = /^(?:please\s+)?(.+?)\s+(?:song|gaana|gana|गाना|सॉन्ग)\s+(?:bajao|chalao|sunao|suna do|बजाओ|चलाओ|सुनाओ)$/iu;
    const titleVerbPattern = /^(?:please\s+)?(.+?)\s+(?:bajao|chalao|sunao|suna do|play karo|बजाओ|चलाओ|सुनाओ)$/iu;

    const match = command.match(requestPattern) || command.match(hindiPattern) || command.match(reverseHindiPattern) || command.match(titleVerbPattern);
    if (!match) return "";

    return (match[1] || "")
        .replace(/^(?:ko|par|on|please)\s+/i, "")
        .replace(/\s+/g, " ")
        .trim();
}

async function playSong(songName) {
    const status = document.getElementById("songStatus");
    const player = document.getElementById("ytplayer");
    songName = (songName || "").trim();
    if (!songName) {
        status.textContent = "Song ka naam batao.";
        return;
    }
    status.textContent = `YouTube par “${songName}” dhoondh raha hoon...`;
    try {
        const response = await fetch(`/youtube_search?q=${encodeURIComponent(songName)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Song nahi mila");
        // Reassigning the iframe URL also stops the previous song cleanly.
        player.src = `https://www.youtube.com/embed/${encodeURIComponent(data.videoId)}?autoplay=1&playsinline=1&rel=0`;
        status.textContent = `▶ ${data.title}`;
    } catch (error) {
        console.error("YouTube playback error:", error);
        status.textContent = error.message || "Song play nahi ho paya.";
    }
}


// Initialize Live2D model when page loads
window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("response").textContent = "";

    // Set up microphone button
    const talkBtn = document.getElementById("talkBtn");
    if (talkBtn) {
        talkBtn.addEventListener("click", toggleMicrophone);
    }
});

// Keep existing song button functionality
const songBtn = document.getElementById("songBtn");

songBtn.onclick = () => {
    let songName = prompt("Kaunsa song chalana hai?");
    if(songName){
        playSong(songName);
    }
};

// AI Circle animation functions (replacing Live2D functions)
function triggerTalkAnimation() {
    const aiCircle = document.getElementById('aiCircle');
    if (aiCircle) {
        aiCircle.classList.add('active');
    }
}

function stopTalkAnimation() {
    const aiCircle = document.getElementById('aiCircle');
    if (aiCircle) {
        aiCircle.classList.remove('active');
    }
}
