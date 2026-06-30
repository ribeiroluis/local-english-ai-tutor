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

  function log() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift("[chat.js]");
    console.log.apply(console, args);
  }

  function logError() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift("[chat.js ERROR]");
    console.error.apply(console, args);
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    logError("getUserMedia not available");
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

    var blob = new Blob([buf], { type: "audio/wav" });
    log("WAV encoded", len, "samples,", (len / 16000).toFixed(2), "seconds");
    return blob;
  }

  function blobToArrayBuffer(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onloadend = function () { resolve(reader.result); };
      reader.onerror = function () { reject(new Error("FileReader failed")); };
      reader.readAsArrayBuffer(blob);
    });
  }

  function webmToWav(blob) {
    log("Converting webm to WAV, size:", (blob.size / 1024).toFixed(1), "KB");
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return blobToArrayBuffer(blob)
      .then(function (buf) { return audioCtx.decodeAudioData(buf); })
      .then(function (audioBuf) {
        var channelData = audioBuf.getChannelData(0);
        log("Decoded audio:", audioBuf.sampleRate, "Hz,", channelData.length, "samples,", (channelData.length / audioBuf.sampleRate).toFixed(2), "sec");
        var ratio = audioBuf.sampleRate / 16000;
        var outLen = Math.round(channelData.length / ratio);
        var resampled = new Float32Array(outLen);
        for (var i = 0; i < outLen; i++) {
          var srcIdx = Math.round(i * ratio);
          resampled[i] = channelData[Math.min(srcIdx, channelData.length - 1)];
        }
        log("Resampled to 16000 Hz:", resampled.length, "samples");
        return floatTo16BitPCM(resampled);
      });
  }

  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(function (stream) {
      log("Microphone access granted");

      var options = { mimeType: "audio/webm;codecs=opus" };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = { mimeType: "audio/webm" };
      }
      mediaRecorder = new MediaRecorder(stream, options);
      log("MediaRecorder created:", mediaRecorder.mimeType);

      mediaRecorder.ondataavailable = function (e) {
        if (e.data.size > 0) {
          audioChunks.push(e.data);
          log("Audio chunk:", (e.data.size / 1024).toFixed(1), "KB");
        }
      };

      mediaRecorder.onstop = function () {
        var totalSize = audioChunks.reduce(function (sum, c) { return sum + c.size; }, 0);
        log("Recording stopped, total:", (totalSize / 1024).toFixed(1), "KB, chunks:", audioChunks.length);

        addMessage("user", "Processing audio...");
        indicatorEl.classList.remove("hidden");

        var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
        audioChunks = [];

        webmToWav(blob)
          .then(function (wavBlob) {
            log("Sending WAV to backend, size:", (wavBlob.size / 1024).toFixed(1), "KB");
            var formData = new FormData();
            formData.append("file", wavBlob, "recording.wav");

            return fetch("/api/transcribe", {
              method: "POST",
              body: formData,
            });
          })
          .then(function (r) {
            log("Backend response status:", r.status);
            return r.json();
          })
          .then(function (data) {
            indicatorEl.classList.add("hidden");
            removeLastUserMessage();
            log("Transcription result:", JSON.stringify(data));
            if (data.text) {
              addMessage("user", data.text);
            } else {
              addMessage("system", "Could not understand. Try again.");
              logError("Empty transcription. Backend response:", JSON.stringify(data));
            }
          })
          .catch(function (err) {
            indicatorEl.classList.add("hidden");
            removeLastUserMessage();
            addMessage("system", "Transcription failed. Try again.");
            logError("Transcription error:", err);
          });
      };

      mediaRecorder.onerror = function (err) {
        logError("MediaRecorder error:", err);
      };
    })
    .catch(function (err) {
      logError("getUserMedia denied:", err);
      addMessage("system", "Microphone access denied. Allow mic access and refresh.");
      recordBtn.disabled = true;
    });

  recordBtn.addEventListener("click", toggleRecording);

  function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  function startRecording() {
    if (!mediaRecorder || isRecording) return;
    log("Recording started");
    isRecording = true;
    audioChunks = [];
    mediaRecorder.start();
    recordBtn.classList.add("is-recording");
  }

  function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    log("Recording stopping...");
    isRecording = false;
    if (mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    recordBtn.classList.remove("is-recording");
  }
})();
