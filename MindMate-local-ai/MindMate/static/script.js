/* =========================================
MINDMATE HEADQUARTERS
========================================= */

let currentEmotion = "";
let history = [];              // the conversation so far, sent with every message
let controller = null;         // lets the user stop a reply mid-way
const MAX_HISTORY = 32;

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

    setStatus(mood + " is the loudest feeling right now");

    const mark = document.getElementById("console-mark");
    if (mark) {
        mark.hidden = false;
    }
}

/* ---------- chat helpers ---------- */

function setStatus(text) {
    const status = document.getElementById("console-status");
    if (status) {
        status.textContent = text;
    }
}

function addMessage(className, text) {
    const chatMessages = document.getElementById("chat-messages");
    const el = document.createElement("div");
    el.className = "message " + className;
    el.dir = "auto";                       // Arabic shows right-to-left automatically
    el.textContent = text;                 // always textContent: never inject model output as HTML
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return el;
}

function isArabic(text) {
    const letters = text.match(/\p{L}/gu) || [];
    const arabic = text.match(/[؀-ۿ]/g) || [];
    return letters.length > 0 && arabic.length >= letters.length / 3;
}

function addHelpCard(lines, arabic) {
    const chatMessages = document.getElementById("chat-messages");
    if (chatMessages.lastElementChild && chatMessages.lastElementChild.classList.contains("help-card")) {
        return;
    }
    const card = document.createElement("div");
    card.className = "message help-card";
    card.dir = arabic ? "rtl" : "ltr";
    const title = document.createElement("strong");
    title.textContent = arabic ? "ما يلزمك تشيلها لحالك" : "You don't have to handle this alone";
    card.appendChild(title);

    lines.forEach((line) => {
        const a = document.createElement("a");
        a.href = "tel:" + line.number;
        a.className = "help-line";
        const label = document.createElement("span");
        label.textContent = arabic ? (line.name_ar || line.name) : line.name;
        const note = document.createElement("small");
        note.textContent = (arabic ? (line.note_ar || line.note) : line.note) || "";
        label.appendChild(note);
        const num = document.createElement("b");
        num.textContent = line.number;
        a.append(label, num);
        card.appendChild(a);
    });

    chatMessages.appendChild(card);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setBusy(busy) {
    const button = document.getElementById("send-btn");
    if (button) {
        button.textContent = busy ? "Stop" : "Send";
        button.classList.toggle("is-stop", busy);
    }
}

/* ---------- streaming reader (Server-Sent Events over fetch) ---------- */

async function streamChat(payload, handlers, signal) {
    const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
        body: JSON.stringify(payload),
        signal
    });

    if (!response.ok) {
        let msg = "Sorry, something went wrong. Please try again.";
        try { msg = (await response.json()).error || msg; } catch (e) { /* keep default */ }
        handlers.onError(msg);
        return { error: true, text: "" };
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";

    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let cut;
        while ((cut = buffer.indexOf("\n\n")) !== -1) {
            const raw = buffer.slice(0, cut);
            buffer = buffer.slice(cut + 2);
            const line = raw.split("\n").find((l) => l.startsWith("data:"));
            if (!line) continue;

            let ev;
            try { ev = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }

            if (ev.type === "token") {
                full += ev.text;
                handlers.onText(full);
            } else if (ev.type === "replace") {
                full = ev.text;
                handlers.onText(full);
            } else if (ev.type === "safety") {
                handlers.onSafety(ev.resources || []);
            } else if (ev.type === "error") {
                handlers.onError(ev.text);
                return { error: true, text: full };
            } else if (ev.type === "done") {
                return { text: full };
            }
        }
    }
    return { text: full };
}

/* ---------- send ---------- */

async function sendMessage() {
    if (controller) {                      // button is "Stop" while a reply is streaming
        controller.abort();
        return;
    }

    const input = document.getElementById("user-message");
    const message = input.value.trim();
    if (message === "") {
        return;
    }

    addMessage("user-message", message);
    input.value = "";

    let bot = addMessage("bot-message typing", "");
    bot.innerHTML = "<span></span><span></span><span></span>";
    let started = false;
    const begin = () => {
        if (!started) {
            started = true;
            bot.className = "message bot-message";
            bot.textContent = "";
        }
    };

    controller = new AbortController();
    setBusy(true);
    setStatus("MindMate is thinking...");

    let result = { text: "" };
    try {
        result = await streamChat(
            { message, emotion: currentEmotion, history },
            {
                onText: (text) => {
                    begin();
                    bot.textContent = text;
                    const box = document.getElementById("chat-messages");
                    box.scrollTop = box.scrollHeight;
                },
                onSafety: (lines) => {
                    addHelpCard(lines, isArabic(message));
                    document.getElementById("chat-messages").appendChild(bot);   // keep reply under the card
                },
                onError: (msg) => {
                    begin();
                    bot.textContent = msg;
                }
            },
            controller.signal
        );
    } catch (error) {
        if (error.name !== "AbortError") {
            console.error(error);
            begin();
            bot.textContent = "Sorry, something went wrong. Please try again.";
            result = { error: true, text: "" };
        }
    }

    if (!started) {
        bot.remove();
    }
    if (!result.error) {
        history.push({ role: "user", content: message });
        if (bot.isConnected && bot.textContent) {
            history.push({ role: "assistant", content: bot.textContent });
        }
        if (history.length > MAX_HISTORY) {
            history = history.slice(-MAX_HISTORY);
        }
    }

    controller = null;
    setBusy(false);
    setStatus(currentEmotion ? currentEmotion + " is the loudest feeling right now" : "Ready when you are");
    input.focus();
}

function handleEnter(event) {
    if (event.key === "Enter" && !event.isComposing) {
        event.preventDefault();
        sendMessage();
    }
}

function showSupportMessage() {
    const message = document.getElementById("support-message");
    message.textContent =
        "If you feel that you may be in immediate danger, call 911. For free psychological support, call 920033360.";
    const list = document.getElementById("support-list");
    if (list) {
        list.hidden = false;
    }
}
