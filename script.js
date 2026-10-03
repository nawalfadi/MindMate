/* =========================================
MINDMATE - JAVASCRIPT
========================================= */

/* =========================================
MOOD CHECK-IN
========================================= */

function selectMood(mood) {

const result = document.getElementById("mood-result");
const messages = {
    "Happy":
        "That's great! Keep doing the things that make you feel good. 😊",
    "Okay":
        "It's okay to feel just okay. Take a moment for yourself today. 🌱",
    "Low":
        "I'm sorry you're feeling low. Remember that you don't have to deal with everything alone. 💙",
    "Stressed":
        "It sounds like you're under some pressure. Try taking a slow breath and giving yourself a short break. 🫁",
    "Angry":
        "It's okay to feel angry. Give yourself some space and try to understand what's behind the feeling. 🌱"
};
result.textContent = messages[mood] || "Thank you for checking in with yourself.";

}

/* =========================================
CHATBOT
========================================= */

async function sendMessage() {

const input =
    document.getElementById("user-message");
const message =
    input.value.trim();
// Don't send empty messages
if (message === "") {
    return;
}
// Get chat container
const chatMessages =
    document.getElementById("chat-messages");
// Add user's message
const userMessage =
    document.createElement("div");
userMessage.className =
    "message user-message";
userMessage.textContent =
    message;
chatMessages.appendChild(
    userMessage
);
// Clear input
input.value = "";
// Scroll to bottom
chatMessages.scrollTop =
    chatMessages.scrollHeight;
// Show temporary message
const typingMessage =
    document.createElement("div");
typingMessage.className =
    "message bot-message";
typingMessage.textContent =
    "MindMate is thinking...";
typingMessage.id =
    "typing-message";
chatMessages.appendChild(
    typingMessage
);
try {
    /*
        Send the message to our
        Python Flask backend.
    */
    const response =
        await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });
    const data =
        await response.json();
    // Remove typing message
    const typing =
        document.getElementById(
            "typing-message"
        );
    if (typing) {
        typing.remove();
    }
    // Create bot message
    const botMessage =
        document.createElement("div");
    botMessage.className =
        "message bot-message";
    botMessage.textContent =
        data.reply ||
        "I'm here to listen. Tell me more about how you're feeling.";
    chatMessages.appendChild(
        botMessage
    );
    // Scroll down
    chatMessages.scrollTop =
        chatMessages.scrollHeight;
} catch (error) {
    console.error(error);
    const typing =
        document.getElementById(
            "typing-message"
        );
    if (typing) {
        typing.remove();
    }
    const errorMessage =
        document.createElement("div");
    errorMessage.className =
        "message bot-message";
    errorMessage.textContent =
        "Sorry, something went wrong. Please try again.";
    chatMessages.appendChild(
        errorMessage
    );
    chatMessages.scrollTop =
        chatMessages.scrollHeight;
}

}

/* =========================================
ENTER KEY
========================================= */

function handleEnter(event) {

if (event.key === "Enter") {
    sendMessage();
}

}

/* =========================================
SUPPORT BUTTON
========================================= */

function showSupportMessage() {

const message =
    document.getElementById(
        "support-message"
    );
message.textContent =
    "If you feel that you may be in immediate danger, please contact emergency services or a qualified mental health professional.";

}