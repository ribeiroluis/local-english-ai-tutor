(function () {
  var sessionId = new URLSearchParams(window.location.search).get("session_id");
  if (!sessionId) {
    document.body.innerHTML = "<p style='padding:2rem;text-align:center'>No session. <a href='/'>Start a conversation</a>.</p>";
    return;
  }

  var recordBtn = document.getElementById("record-btn");
  var messagesEl = document.getElementById("chat-messages");
  var indicatorEl = document.getElementById("recording-indicator");
  var mediaRecorder = null;
  var audioChunks = [];
  var isRecording = false;

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    addMessage("system", "Microphone not available in this browser.");
    recordBtn.disabled = true;
    return;
  }

  function addMessage(type, text) {
    var empty = messagesEl.querySelector(".empty-state");
    if (empty) empty.remove();

    var bubble = document.createElement("div");
    bubble.className = "msg-bubble msg-" + type;
    bubble.textContent = text;
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(function (stream) {
      var options = { mimeType: "audio/webm;codecs=opus" };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = { mimeType: "audio/webm" };
      }
      mediaRecorder = new MediaRecorder(stream, options);

      mediaRecorder.ondataavailable = function (e) {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = function () {
        addMessage("user", "Processing audio...");
        indicatorEl.classList.remove("hidden");

        var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
        audioChunks = [];

        var formData = new FormData();
        formData.append("file", blob, "recording.webm");

        fetch("/api/transcribe", {
          method: "POST",
          body: formData,
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            indicatorEl.classList.add("hidden");
            removeLastUserMessage();
            if (data.text) {
              addMessage("user", data.text);
            } else {
              addMessage("system", "Could not understand. Try again.");
            }
          })
          .catch(function () {
            indicatorEl.classList.add("hidden");
            removeLastUserMessage();
            addMessage("system", "Transcription failed. Try again.");
          });
      };
    })
    .catch(function () {
      addMessage("system", "Microphone access denied. Allow mic access and refresh.");
      recordBtn.disabled = true;
    });

  function removeLastUserMessage() {
    var msgs = messagesEl.querySelectorAll(".msg-user");
    if (msgs.length > 0) msgs[msgs.length - 1].remove();
  }

  recordBtn.addEventListener("mousedown", startRecording);
  recordBtn.addEventListener("mouseup", stopRecording);
  recordBtn.addEventListener("mouseleave", stopRecording);
  recordBtn.addEventListener("touchstart", function (e) { e.preventDefault(); startRecording(); }, { passive: true });
  recordBtn.addEventListener("touchend", function (e) { e.preventDefault(); stopRecording(); }, { passive: true });

  function startRecording() {
    if (!mediaRecorder || isRecording) return;
    isRecording = true;
    audioChunks = [];
    mediaRecorder.start();
    recordBtn.classList.add("is-recording");
  }

  function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    isRecording = false;
    if (mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    recordBtn.classList.remove("is-recording");
  }
})();
