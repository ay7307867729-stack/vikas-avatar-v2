const talkBtn = document.getElementById("talkBtn");

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

const recognition = new SpeechRecognition();

recognition.lang = "hi-IN";
recognition.interimResults = false;


talkBtn.addEventListener("click", () => {

    recognition.start();

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Listening...`;

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


    speak(data.reply);


    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;

};


// AI ki awaaz
function speak(text){

    const speech = new SpeechSynthesisUtterance(text);

    speech.lang = "hi-IN";

    window.speechSynthesis.speak(speech);

}


recognition.onerror = () => {

    talkBtn.innerHTML = `<i class="fas fa-microphone"></i> Talk`;

    alert("Mic Error");

};