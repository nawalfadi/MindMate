/* =========================================
MINDMATE HEADQUARTERS
========================================= */

let currentEmotion = "";

const moodMessages = {
    Anxiety:
        "Anxiety is trying to protect you by planning for what might go wrong. It causes trouble when it is the only feeling in charge. Name one thing that is happening right now.",
    Envy:
        "Envy admires what someone else has. That pull can show you what you want. Ask which part of it is actually yours.",
    Embarrassment:
        "Embarrassment wants to hide, and it is often shy rather than unkind. The warm feeling can settle. You can stay.",
    Ennui:
        "This is the flat, whatever feeling. It barely wants to move, and it still counts. A small change of scene can be enough.",
    Disgust:
        "Disgust turns you away from what is bad for you. You can keep that boundary and still be yourself around other people.",
    Fear:
        "Fear is trying to keep you safe, from physical danger and from social risk. If the alarm is ahead of the moment, check what is actually here.",
    Joy:
        "Joy wants things to feel good. It does not have to run the whole day. Leave room for what feels good, and for the other feelings too.",
    Anger:
        "Anger shows up when something feels unfair. The heat is information. Give it space, then ask what crossed a line.",
    Sadness:
        "Sadness helps a loss be felt and can bring you closer to other people. Let it be here. It belongs in who you are."
};

function selectMood(mood) {
    const key = mood.toLowerCase();
    currentEmotion = mood;
    document.body.dataset.emotion = key;

    document.querySelectorAll(".mood-card").forEach((card) => {
        const selected = card.dataset.emotion === key;
        card.classList.toggle("is-selected", selected);
        card.setAttribute("aria-pressed", selected ? "true" : "false");
    });

    const result = document.getElementById("mood-result");
    result.textContent = moodMessages[mood] || "Thank you for checking in with yourself.";

    const status = document.getElementById("console-status");
    if (status) {
        status.textContent = mood + " is the loudest feeling right now";
    }

    const mark = document.getElementById("console-mark");
    if (mark) {
        mark.hidden = false;
    }
}

async function sendMessage() {
    const input = document.getElementById("user-message");
    const message = input.value.trim();

    if (message === "") {
        return;
    }

    const chatMessages = document.getElementById("chat-messages");

    const userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.textContent = message;
    chatMessages.appendChild(userMessage);

    input.value = "";
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const typingMessage = document.createElement("div");
    typingMessage.className = "message bot-message";
    typingMessage.textContent = "MindMate is thinking...";
    typingMessage.id = "typing-message";
    chatMessages.appendChild(typingMessage);

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                emotion: currentEmotion
            })
        });

        const data = await response.json();
        const typing = document.getElementById("typing-message");
        if (typing) {
            typing.remove();
        }

        const botMessage = document.createElement("div");
        botMessage.className = "message bot-message";
        botMessage.textContent = data.reply ||
            "I'm here to listen. Tell me more about how you're feeling.";
        chatMessages.appendChild(botMessage);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (error) {
        console.error(error);
        const typing = document.getElementById("typing-message");
        if (typing) {
            typing.remove();
        }

        const errorMessage = document.createElement("div");
        errorMessage.className = "message bot-message";
        errorMessage.textContent = "Sorry, something went wrong. Please try again.";
        chatMessages.appendChild(errorMessage);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function handleEnter(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

function showSupportMessage() {
    const message = document.getElementById("support-message");
    message.textContent =
        "If you feel that you may be in immediate danger, please contact emergency services or a qualified mental health professional.";
}
