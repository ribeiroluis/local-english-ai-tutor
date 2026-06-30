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
  var audioCtx = null;

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

  function removeLastUserMessage() {
    var msgs = messagesEl.querySelectorAll(".msg-user");
    if (msgs.length > 0) msgs[msgs.length - 1].remove();
  }

  function floatTo16BitPCM(samples) {
    var len = samples.length;
    var buf = new ArrayBuffer(44 + len * 2);
    var view = new DataView(buf);

    function writeString(offset, str) {
      for (var i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    }

    writeString(0, "RIFF");
    view.setUint32(4, 36 + len * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true);
    view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, len * 2, true);

    for (var i = 0; i < len; i++) {
      var s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([buf], { type: "audio/wav" });
  }

  function blobToArrayBuffer(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onloadend = function () { resolve(reader.result); };
      reader.onerror = reject;
      reader.readAsArrayBuffer(blob);
    });
  }

  function webmToWav(blob) {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return blobToArrayBuffer(blob)
      .then(function (buf) { return audioCtx.decodeAudioData(buf); })
      .then(function (audioBuf) {
        var channelData = audioBuf.getChannelData(0);
        var ratio = audioBuf.sampleRate / 16000;
        var outLen = Math.round(channelData.length / ratio);
        var resampled = new Float32Array(outLen);
        for (var i = 0; i < outLen; i++) {
          var srcIdx = Math.round(i * ratio);
          resampled[i] = channelData[Math.min(srcIdx, channelData.length - 1)];
        }
        return floatTo16BitPCM(resampled);
      });
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

        webmToWav(blob)
          .then(function (wavBlob) {
            var formData = new FormData();
            formData.append("file", wavBlob, "recording.wav");

            return fetch("/api/transcribe", {
              method: "POST",
              body: formData,
            });
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
