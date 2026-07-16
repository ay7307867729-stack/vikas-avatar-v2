const talkBtn = document.getElementById("talkBtn");

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

const recognition = new SpeechRecognition();

recognition.lang = "hi-IN";
recognition.interimResults = false;

window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("response").textContent = "";
});

talkBtn.addEventListener("click", () => {

    recognition.start();

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Listening...`;

});
window.addEventListener("load", () => {

    setTimeout(() => {

        recognition.start();

        talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Listening...`;

    }, 1500);

});

recognition.onresult = async (event) => {

    const text = event.results[0][0].transcript;

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Thinking...`;

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
    responseParagraph.textContent = "";

    // Use browser TTS with a normal female voice.
    await speak(data.reply);

    responseParagraph.textContent = "";
    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;

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
let motionGroup = null;
let mixer = null;
const clock = new THREE.Clock();
let walkPhase = 0;
const walkSpeed = 0.9;
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
        avatar.scale.set(2.8, 2.8, 2.8);
        scene.add(avatar);

        const box = new THREE.Box3().setFromObject(avatar);
        const size = new THREE.Vector3();
        const center = new THREE.Vector3();
        box.getSize(size);
        box.getCenter(center);

        avatar.position.y -= center.y;
        avatar.position.y -= size.y * 0.05;

        const distance = Math.max(size.x, size.y, size.z) * 2.2;
        camera.position.set(0, size.y * 0.8, distance);
        camera.near = distance / 100;
        camera.far = distance * 10;
        camera.updateProjectionMatrix();
        camera.lookAt(new THREE.Vector3(0, 0, 0));

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

function animate(){
    requestAnimationFrame(animate);

    const delta = clock.getDelta();

    if (avatarModel) {
        avatarModel.rotation.y += delta * 0.18;
        walkPhase += delta * walkSpeed;
        avatarModel.position.y = Math.sin(walkPhase * 1.2) * 0.03;
        avatarModel.position.x = Math.sin(walkPhase * 0.5) * 0.02;

        const armSwing = Math.sin(walkPhase * 1.6) * 0.2;
        avatarModel.traverse((child) => {
            if (child.isBone && child.name.toLowerCase().includes('arm')) {
                child.rotation.z = armSwing;
            }
        });
    }

    if (mixer) {
        mixer.update(delta);
    }

    renderer.render(scene, camera);
}

animate();