const talkBtn = document.getElementById("talkBtn");
const chatBtn = document.getElementById("chatBtn");
const chatOverlay = document.getElementById("chatOverlay");
const closeChatBtn = document.getElementById("closeChatBtn");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");
const chatSendBtn = document.getElementById("chatSendBtn");

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

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = chatInput.value.trim();
    if (!text || chatSendBtn.disabled) return;

    addChatMessage(text, "user");
    chatInput.value = "";
    chatSendBtn.disabled = true;
    const typing = addChatMessage("Anaya is typing... ✨", "ai");
    typing.classList.add("typing");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.reply || "Chat request failed");
        typing.remove();
        addChatMessage(data.reply || "Mujhe koi reply nahi mila.", "ai");
        document.getElementById("response").textContent = data.reply || "";
        const songName = extractSongName(text);
        if (songName) playSong(songName);
    } catch (error) {
        typing.remove();
        addChatMessage(error.message || "Abhi chat service available nahi hai.", "ai");
    } finally {
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

talkBtn.addEventListener("click", () => {

    if (!SpeechRecognition) {
        alert("Voice input is not supported in this browser. Please use Chrome or Edge.");
        return;
    }

    if(isListening){
        console.log("Already listening");
        return;
    }

    recognition.start();
    isListening = true;

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Listening...`;

});


recognition.onend = () => {
    isListening = false;
    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
};


recognition.onresult = async (event) => {

    const text = event.results[0][0].transcript;
    const lowerText = text.toLowerCase();

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Thinking...`;
    triggerTalkAnimation();

    try {
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
        responseParagraph.textContent = data.reply || "No reply received.";

        // Use browser TTS with a normal female voice.
        await speak(data.reply || "No reply received.");
        // Agar user ne song play karne ko bola hai


        const songName = extractSongName(text);
        if (songName) playSong(songName);

    } finally {
        stopTalkAnimation();
        talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;
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
        speech.onend = () => resolve();
        speech.onerror = (event) => reject(event.error || new Error('Speech synthesis error'));

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
    const lower = text.toLowerCase();
    const intent = /\b(play|song|music|gaana|gana|bajao|chalao|sunao|suna[oao]?)\b/i;
    if (!intent.test(lower)) return "";
    return text
        .replace(/\b(please|play|song|music|gaana|gana|bajao|chalao|sunao|suna[oao]?)\b/gi, "")
        .replace(/^(ko|koi|mujhe|mera|meri|par|on)\s+/i, "")
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
        player.src = `https://www.youtube.com/embed/${data.videoId}?autoplay=1&playsinline=1&rel=0`;
        status.textContent = `▶ ${data.title}`;
    } catch (error) {
        console.error("YouTube playback error:", error);
        status.textContent = error.message || "Song play nahi ho paya.";
    }
}


// ===== 3D Avatar Scene =====

const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(
    75,
    1,
    0.1,
    1000
);

const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true
});

let avatarModel = null;
let avatarRoot = null;
let motionGroup = null;
let mixer = null;
const clock = new THREE.Clock();
let walkPhase = 0;
const walkSpeed = 0.9;
let talking = false;
let talkPulse = 0;
let avatarTargetX = 0;
let avatarTargetY = 0;
let avatarTargetZ = 0;
let avatarCurrentX = 0;
let avatarCurrentY = 0;
let avatarCurrentZ = 0;
let animatedBones = [];
const boneRestRotations = new Map();
let eyeTargets = [];
let blinkAmount = 0;
let blinkTimer = 0;
const eyeRestRotations = new Map();
const eyeRestScales = new Map();
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.physicallyCorrectLights = true;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const avatarContainer = document.getElementById("avatar");

function resizeRenderer() {
    const width = avatarContainer.clientWidth || window.innerWidth;
    const height = avatarContainer.clientHeight || window.innerHeight;
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
}

resizeRenderer();
window.addEventListener("resize", resizeRenderer);

avatarContainer.appendChild(renderer.domElement);

renderer.setClearColor(0x000000, 0);

const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0x222244, 0.8);
scene.add(hemisphereLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 2.2);
directionalLight.position.set(5, 10, 7);
directionalLight.castShadow = true;
directionalLight.shadow.camera.near = 0.5;
directionalLight.shadow.camera.far = 50;
directionalLight.shadow.mapSize.set(1024, 1024);
scene.add(directionalLight);

const fillLight = new THREE.PointLight(0xffffff, 0.8);
fillLight.position.set(-4, 2, 5);
scene.add(fillLight);

camera.position.set(0, 1.2, 8);
camera.lookAt(0, 0, 0);

// ===== Load GLB Avatar =====

const loader = new THREE.GLTFLoader();
if (THREE.DRACOLoader) {
    const dracoLoader = new THREE.DRACOLoader();
    dracoLoader.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/libs/draco/');
    loader.setDRACOLoader(dracoLoader);
}

const modelUrl = window.modelUrl || "/static/models/modelToUsed.glb";
console.log("GLB URL:", modelUrl);

loader.load(
    modelUrl,
    function (gltf) {
        const avatar = gltf.scene;
        avatarModel = avatar;
        avatarRoot = new THREE.Group();
        avatarRoot.add(avatar);
        scene.add(avatarRoot);

        const box = new THREE.Box3().setFromObject(avatar);
        const size = new THREE.Vector3();
        const center = new THREE.Vector3();
        box.getSize(size);
        box.getCenter(center);

        avatar.traverse((child) => {
            if (child.isMesh) {
                child.material.side = THREE.DoubleSide;
                child.castShadow = true;
                child.receiveShadow = true;

                if (child.material.map) {
                    child.material.map.encoding = THREE.sRGBEncoding;
                }
                if (child.material.emissiveMap) {
                    child.material.emissiveMap.encoding = THREE.sRGBEncoding;
                }
                if (child.material.normalMap) {
                    child.material.normalMap.encoding = THREE.LinearEncoding;
                }
            }
        });

        const distance = Math.max(size.x, size.y, size.z) * 2.2;
        camera.position.set(0, size.y * 0.8, distance);
        camera.near = distance / 100;
        camera.far = distance * 10;
        camera.updateProjectionMatrix();
        camera.lookAt(new THREE.Vector3(0, 0, 0));

        avatarCurrentX = avatar.position.x;
        avatarCurrentY = avatar.position.y;
        avatarCurrentZ = avatar.position.z;
        avatarTargetX = avatar.position.x;
        avatarTargetY = avatar.position.y;
        avatarTargetZ = avatar.position.z;

        animatedBones = [];
        boneRestRotations.clear();
        eyeTargets = [];
        eyeRestRotations.clear();
        eyeRestScales.clear();
        avatarRoot.traverse((child) => {
            if (child.isBone) {
                const name = child.name.toLowerCase();
                const isBodyBone = /hand|wrist|finger|forearm|arm|upperarm|shoulder|clav|spine|neck|head/.test(name);
                if (isBodyBone) {
                    animatedBones.push(child);
                    boneRestRotations.set(child.uuid, {
                        x: child.rotation.x,
                        y: child.rotation.y,
                        z: child.rotation.z
                    });
                }

                if (/eye|eyelid|lid/.test(name)) {
                    eyeTargets.push({ type: 'bone', object: child });
                    eyeRestRotations.set(child.uuid, {
                        x: child.rotation.x,
                        y: child.rotation.y,
                        z: child.rotation.z
                    });
                }
            }

            if (child.isMesh) {
                const name = child.name.toLowerCase();
                if (/eye|eyelid|lid/.test(name)) {
                    eyeTargets.push({ type: 'mesh', object: child });
                    eyeRestScales.set(child.uuid, child.scale.clone());
                }
            }
        });

        console.log("GLB loaded successfully", avatar);
    },
    function (xhr) {
        if (xhr.lengthComputable) {
            console.log(`Model loading: ${Math.round((xhr.loaded / xhr.total) * 100)}%`);
        }
    },
    function (error) {
        console.error("GLB Error:", error);
    }
);

const axesHelper = new THREE.AxesHelper(2);
scene.add(axesHelper);

function triggerTalkAnimation() {
    talking = true;
    talkPulse = Math.max(talkPulse, 0.7);
    avatarTargetX = 0.55;
    avatarTargetY = 0.06;
    avatarTargetZ = -0.12;
}

function stopTalkAnimation() {
    talking = false;
    avatarTargetX = 0;
    avatarTargetY = 0;
    avatarTargetZ = 0;
}

function animate() {
    requestAnimationFrame(animate);

    const delta = clock.getDelta();
    walkPhase += delta * walkSpeed;

    if (talking) {
        talkPulse = Math.min(1, talkPulse + delta * 4.2);
    } else {
        talkPulse = Math.max(0, talkPulse - delta * 2.1);
    }

    if (avatarModel && avatarRoot) {
        avatarCurrentX += (avatarTargetX - avatarCurrentX) * Math.min(1, delta * 2.8);
        avatarCurrentY += (avatarTargetY - avatarCurrentY) * Math.min(1, delta * 2.8);
        avatarCurrentZ += (avatarTargetZ - avatarCurrentZ) * Math.min(1, delta * 2.8);

        const idleBob = Math.sin(walkPhase * 2.4) * 0.03;
        const sway = talking ? Math.sin(walkPhase * 6.5) * 0.18 : Math.sin(walkPhase * 1.8) * 0.05;
        const lean = talking ? 0.12 : 0.03;

        avatarRoot.position.set(avatarCurrentX, avatarCurrentY + idleBob, avatarCurrentZ);
        avatarRoot.rotation.y = sway;
        avatarRoot.rotation.z = talking ? 0.08 : 0.02;
        avatarRoot.rotation.x = lean;
    }

    if (animatedBones.length) {
        animatedBones.forEach((bone, index) => {
            const name = bone.name.toLowerCase();
            const rest = boneRestRotations.get(bone.uuid) || { x: 0, y: 0, z: 0 };
            const phase = walkPhase * 6 + index * 0.55;
            const leftSide = name.includes('left');
            const isArm = /arm|forearm|upperarm|shoulder|clav/.test(name);
            const isHand = /hand|wrist|finger/.test(name);
            const isBody = /spine|neck|head/.test(name);

            if (talking) {
                if (isHand) {
                    bone.rotation.z = Math.sin(phase) * 0.35 + (leftSide ? 0.08 : -0.08);
                    bone.rotation.x = 0.16 + Math.sin(phase * 1.2) * 0.05;
                } else if (isArm) {
                    bone.rotation.z = Math.sin(phase) * 0.22 + (leftSide ? 0.05 : -0.05);
                    bone.rotation.x = 0.06 + Math.sin(phase * 0.9) * 0.03;
                } else if (isBody) {
                    bone.rotation.y = Math.sin(phase * 0.6) * 0.08;
                    bone.rotation.z = Math.sin(phase * 0.4) * 0.04;
                }
            } else {
                bone.rotation.x = rest.x;
                bone.rotation.y = rest.y;
                bone.rotation.z = rest.z;
            }
        });
    }

    blinkTimer -= delta;
    if (blinkTimer <= 0) {
        blinkTimer = talking ? 0.35 + Math.random() * 0.25 : 1.2 + Math.random() * 2.5;
        blinkAmount = 1;
    }

    if (blinkAmount > 0) {
        blinkAmount = Math.max(0, blinkAmount - delta * 8.5);
    }

    if (eyeTargets.length) {
        const blinkValue = Math.max(0, blinkAmount);
        eyeTargets.forEach((entry) => {
            const name = entry.object.name.toLowerCase();

            if (entry.type === 'bone') {
                const rest = eyeRestRotations.get(entry.object.uuid) || { x: 0, y: 0, z: 0 };
                if (/eyelid|lid/.test(name)) {
                    entry.object.rotation.x = rest.x + blinkValue * 0.55 + (talking ? 0.02 : 0);
                    entry.object.rotation.z = rest.z + (talking ? 0.04 : 0);
                } else if (/eye/.test(name)) {
                    entry.object.rotation.x = rest.x + (talking ? 0.01 : 0);
                    entry.object.rotation.y = rest.y + (talking ? 0.01 : 0);
                }
            } else if (entry.type === 'mesh') {
                const restScale = eyeRestScales.get(entry.object.uuid);
                if (restScale) {
                    if (/eyelid|lid/.test(name)) {
                        const closeAmount = Math.max(0.05, 1 - blinkValue * 0.9);
                        entry.object.scale.set(restScale.x, restScale.y * closeAmount, restScale.z * closeAmount);
                    } else if (/eye/.test(name)) {
                        const openness = Math.max(0.9, 1 - blinkValue * 0.08);
                        entry.object.scale.set(restScale.x * openness, restScale.y * openness, restScale.z * openness);
                    }
                }
            }
        });
    }

    if (camera) {
        camera.position.x = Math.sin(walkPhase * 0.45) * 0.12;
        camera.position.y = 1.2 + Math.sin(walkPhase * 0.9) * 0.03;
        camera.lookAt(new THREE.Vector3(0, 0.2, 0));
    }

    renderer.render(scene, camera);
}

animate();
const songBtn = document.getElementById("songBtn");

songBtn.onclick = () => {

    let songName = prompt("Kaunsa song chalana hai?");

    if(songName){
        playSong(songName);
    }

};