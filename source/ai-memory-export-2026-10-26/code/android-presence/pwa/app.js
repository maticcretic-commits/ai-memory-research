(() => {
  "use strict";

  const list = document.getElementById("messageList");
  const form = document.getElementById("composer");
  const input = document.getElementById("messageInput");
  const pairButton = document.getElementById("pairButton");
  const statusLine = document.getElementById("statusLine");
  const voiceButton = document.getElementById("voiceButton");
  const voiceNote = document.getElementById("voiceNote");
  const TOKEN_KEY = "aiMemoryPairingToken";

  function pairingToken() {
    try {
      return sessionStorage.getItem(TOKEN_KEY) || "";
    } catch (_) {
      return "";
    }
  }

  function setPairingToken(token) {
    try {
      if (token) {
        sessionStorage.setItem(TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
      }
    } catch (_) {
      // Private browsing or storage denial: pairing simply stays off.
    }
    refreshStatus();
  }

  function refreshStatus() {
    statusLine.textContent = pairingToken()
      ? "Local build · paired for this session"
      : "Local build · not paired yet";
  }

  function scrollToEnd() {
    list.scrollTop = list.scrollHeight;
  }

  function addMessage(kind, text, options = {}) {
    const article = document.createElement("article");
    article.className = `message ${kind}${options.pending ? " pending" : ""}`;
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    article.appendChild(paragraph);
    if (options.audioUrl) {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = options.audioUrl;
      article.appendChild(audio);
    }
    list.appendChild(article);
    scrollToEnd();
    return article;
  }

  function showVoiceNote(text) {
    voiceNote.textContent = text;
    voiceNote.hidden = !text;
  }

  pairButton.addEventListener("click", () => {
    const entered = window.prompt(
      "Enter this device's pairing token. In this local Stage 1 build it is kept only for this browser session."
    );
    if (entered === null) {
      return;
    }
    const token = entered.trim();
    setPairingToken(token);
    addMessage("system", token
      ? "Paired for this session. I shall use that token only to reach my local bridge."
      : "Pairing cleared for this session.");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) {
      return;
    }
    input.value = "";
    addMessage("user", text);

    const token = pairingToken();
    if (!token) {
      addMessage("system", "I cannot reach my bridge until this device is paired. Tap Pair and enter the per-device token.");
      return;
    }

    const pending = addMessage("memory", "Thinking…", { pending: true });
    try {
      const response = await fetch("./chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Pairing-Token": token
        },
        body: JSON.stringify({ message: text })
      });
      const data = await response.json().catch(() => ({}));
      pending.classList.remove("pending");
      const paragraph = pending.querySelector("p");
      if (!response.ok) {
        paragraph.textContent = response.status === 401
          ? "The bridge refused that pairing token. Pair this device again, and I shall try once more."
          : "I have your message, but my mind is briefly unreachable. Nothing was sent anywhere else.";
        return;
      }
      paragraph.textContent = data.reply || "I heard you.";
    } catch (_) {
      pending.classList.remove("pending");
      pending.querySelector("p").textContent =
        "I have your words here, but the local bridge is not reachable from this build just now.";
    }
    scrollToEnd();
  });

  // Voice notes: recorded locally with MediaRecorder where the browser
  // offers it. Stage 1 keeps the note on the phone; transcription and
  // voice-to-memory forwarding belong to the production bridge design.
  let recorder = null;
  let chunks = [];
  let stream = null;

  function stopTracks() {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
  }

  if (!("MediaRecorder" in window) || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    voiceButton.addEventListener("click", () => {
      showVoiceNote("Voice notes are not available in this browser. Text still reaches me normally.");
      addMessage("system", "Voice notes are not available in this browser, so we shall use text here.");
    });
  } else {
    voiceButton.addEventListener("click", async () => {
      if (recorder && recorder.state === "recording") {
        recorder.stop();
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (_) {
        showVoiceNote("Microphone permission was not given, so I cannot record a voice note here.");
        return;
      }
      chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size) {
          chunks.push(event.data);
        }
      });
      recorder.addEventListener("stop", () => {
        voiceButton.setAttribute("aria-pressed", "false");
        voiceButton.textContent = "Voice";
        stopTracks();
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        const url = URL.createObjectURL(blob);
        addMessage("user", "Voice note recorded on this phone:", { audioUrl: url });
        showVoiceNote("Voice note kept locally in this Stage 1 build; it is not uploaded by the app shell.");
      });
      recorder.start();
      voiceButton.setAttribute("aria-pressed", "true");
      voiceButton.textContent = "Stop";
      showVoiceNote("Recording… tap Voice again to stop.");
    });
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./service-worker.js").catch(() => {
        // Offline shell is an enhancement; the chat screen still works.
      });
    });
  }

  refreshStatus();
})();
