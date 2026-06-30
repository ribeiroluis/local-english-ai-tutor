(function () {
  var selectedTopic = null;
  var selectedLevel = null;
  var sessionId = null;
  var mediaRecorder = null;
  var audioChunks = [];
  var isRecording = false;
  var audioCtx = null;

  var welcomeScreen = document.getElementById("welcome-screen");
  var chatScreen = document.getElementById("chat-screen");
  var reviewModal = document.getElementById("review-modal");
  var topicGrid = document.getElementById("topic-grid");
  var levelBtns = document.querySelectorAll(".level-btn");
  var startBtn = document.getElementById("start-btn");
  var recordBtn = document.getElementById("record-btn");
  var circleIndicator = document.getElementById("circle-indicator");
  var circleLabel = document.getElementById("circle-label");
  var chatTopicLabel = document.getElementById("chat-topic-label");
  var chatLevelLabel = document.getElementById("chat-level-label");
  var endSessionBtn = document.getElementById("end-session-btn");
  var correctionsList = document.getElementById("corrections-list");
  var newConversationBtn = document.getElementById("new-conversation-btn");

  function log() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift("[app.js]");
    console.log.apply(console, args);
  }

  function logError() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift("[app.js ERROR]");
    console.error.apply(console, args);
  }

  function showWelcome() {
    welcomeScreen.classList.remove("hidden");
    chatScreen.classList.add("hidden");
    reviewModal.classList.add("hidden");
  }

  function showChat() {
    welcomeScreen.classList.add("hidden");
    chatScreen.classList.remove("hidden");
    reviewModal.classList.add("hidden");
  }

  function showReview() {
    welcomeScreen.classList.add("hidden");
    chatScreen.classList.add("hidden");
    reviewModal.classList.remove("hidden");
  }

  function setCircleState(state, label) {
    circleIndicator.className = "circle-indicator " + state;
    circleLabel.textContent = label;
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  fetch("/api/progress")
    .then(function (r) { return r.json(); })
    .then(function (progress) {
      selectedTopic = progress.last_topic || null;
      selectedLevel = progress.last_level || null;
      if (selectedLevel) {
        levelBtns.forEach(function (btn) {
          if (btn.dataset.level === selectedLevel) {
            btn.classList.add("is-selected");
          }
        });
      }
      updateStartBtn();
    });

  fetch("/api/topics")
    .then(function (r) { return r.json(); })
    .then(function (topics) {
      topicGrid.innerHTML = "";
      topics.forEach(function (t) {
        var card = document.createElement("div");
        card.className = "topic-card";
        card.dataset.topicId = t.id;
        if (t.id === selectedTopic) {
          card.classList.add("is-selected");
        }
        card.innerHTML =
          '<div class="topic-card-name">' + escapeHtml(t.name) +
          '</div><div class="topic-card-desc">' + escapeHtml(t.description) +
          "</div>";
        card.addEventListener("click", function () {
          document.querySelectorAll(".topic-card").forEach(function (c) {
            c.classList.remove("is-selected");
          });
          card.classList.add("is-selected");
          selectedTopic = t.id;
          updateStartBtn();
        });
        topicGrid.appendChild(card);
      });
    });

  levelBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      levelBtns.forEach(function (b) { b.classList.remove("is-selected"); });
      btn.classList.add("is-selected");
      selectedLevel = btn.dataset.level;
      updateStartBtn();
    });
  });

  startBtn.addEventListener("click", function () {
    if (!selectedTopic || !selectedLevel) return;
    startBtn.disabled = true;
    startBtn.textContent = "Starting...";

    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: selectedTopic, level: selectedLevel }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        sessionId = data.session_id;
        chatTopicLabel.textContent = selectedTopic;
        chatLevelLabel.textContent = selectedLevel;
        setCircleState("idle", "Tap mic to start");
        showChat();
        startBtn.disabled = false;
        startBtn.textContent = "Start Conversation";
      })
      .catch(function () {
        startBtn.disabled = false;
        startBtn.textContent = "Start Conversation";
        alert("Failed to start session. Try again.");
      });
  });

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
        log("Decoded audio:", audioBuf.sampleRate, "Hz,", channelData.length, "samples");
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

  function sendAudio(wavBlob) {
    setCircleState("processing", "Processing...");
    log("Sending WAV to converse, size:", (wavBlob.size / 1024).toFixed(1), "KB");

    var formData = new FormData();
    formData.append("file", wavBlob, "recording.wav");
    formData.append("session_id", sessionId);

    fetch("/api/converse", {
      method: "POST",
      body: formData,
    })
      .then(function (r) {
        log("Converse response status:", r.status);
        var transcript = r.headers.get("X-Transcript") || "";
        var reply = r.headers.get("X-Reply") || "";
        var ttsError = r.headers.get("X-TTS-Error") || null;
        return r.blob().then(function (blob) {
          return { blob: blob, transcript: transcript, reply: reply, ttsError: ttsError };
        });
      })
      .then(function (result) {
        log("AI reply:", result.reply);

        if (result.ttsError) {
          logError("TTS failed:", result.ttsError);
          setCircleState("idle", "Tap mic to start");
          return;
        }

        if (result.blob.size === 0) {
          setCircleState("idle", "Tap mic to start");
          return;
        }

        setCircleState("playing", "Playing...");
        var audioUrl = URL.createObjectURL(result.blob);
        var audio = new Audio(audioUrl);
        audio.onended = function () {
          URL.revokeObjectURL(audioUrl);
          setCircleState("idle", "Tap mic to start");
        };
        audio.play().catch(function (err) {
          logError("Audio playback failed:", err);
          setCircleState("idle", "Tap mic to start");
        });
      })
      .catch(function (err) {
        logError("Converse error:", err);
        setCircleState("idle", "Tap mic to start");
      });
  }

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
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
          }
        };

        mediaRecorder.onstop = function () {
          log("Recording stopped, chunks:", audioChunks.length);
          setCircleState("processing", "Processing...");

          var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
          audioChunks = [];

          webmToWav(blob)
            .then(function (wavBlob) {
              sendAudio(wavBlob);
            })
            .catch(function (err) {
              logError("WAV conversion failed:", err);
              setCircleState("idle", "Tap mic to start");
            });
        };

        mediaRecorder.onerror = function (err) {
          logError("MediaRecorder error:", err);
        };
      })
      .catch(function (err) {
        logError("getUserMedia denied:", err);
        recordBtn.disabled = true;
        setCircleState("idle", "Mic unavailable");
      });
  } else {
    logError("getUserMedia not available");
    recordBtn.disabled = true;
    setCircleState("idle", "Mic unavailable");
  }

  recordBtn.addEventListener("click", function () {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  function startRecording() {
    if (!mediaRecorder || isRecording) return;
    log("Recording started");
    isRecording = true;
    audioChunks = [];
    mediaRecorder.start();
    recordBtn.classList.add("is-recording");
    setCircleState("recording", "Recording...");
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

  endSessionBtn.addEventListener("click", function () {
    if (isRecording) {
      stopRecording();
    }
    setCircleState("processing", "Generating review...");

    fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderCorrections(data.corrections);
        showReview();
      })
      .catch(function (err) {
        logError("Review failed:", err);
        setCircleState("idle", "Tap mic to start");
        alert("Failed to generate review. Try again.");
      });
  });

  function renderCorrections(corrections) {
    correctionsList.innerHTML = "";

    if (!corrections || corrections.length === 0) {
      correctionsList.innerHTML = '<p class="no-corrections">No errors found. Great job!</p>';
      return;
    }

    var summary = {};
    corrections.forEach(function (c) {
      var type = c.error_type || "other";
      summary[type] = (summary[type] || 0) + 1;
    });

    var summaryEl = document.createElement("div");
    summaryEl.className = "corrections-summary";
    var summaryHtml = "<h3>Error Summary</h3><div class='summary-bars'>";
    Object.keys(summary).forEach(function (type) {
      var pct = Math.round((summary[type] / corrections.length) * 100);
      summaryHtml +=
        "<div class='summary-row'><span class='summary-label'>" + type +
        "</span><div class='summary-bar'><div class='summary-fill' style='width:" + pct + "%'></div></div>" +
        "<span class='summary-count'>" + summary[type] + "</span></div>";
    });
    summaryHtml += "</div>";
    summaryEl.innerHTML = summaryHtml;
    correctionsList.appendChild(summaryEl);

    corrections.forEach(function (c, i) {
      var card = document.createElement("div");
      card.className = "correction-card";
      card.innerHTML =
        "<div class='correction-original'>" + escapeHtml(c.original_text || "") + "</div>" +
        "<div class='correction-corrected'>" + escapeHtml(c.corrected_text || "") + "</div>" +
        "<div class='correction-explanation'>" + escapeHtml(c.explanation_pt || "") + "</div>" +
        "<div class='correction-type'>" + escapeHtml(c.error_type || "other") + "</div>";
      correctionsList.appendChild(card);
    });
  }

  newConversationBtn.addEventListener("click", function () {
    sessionId = null;
    audioCtx = null;
    showWelcome();
  });

  function updateStartBtn() {
    startBtn.disabled = !(selectedTopic && selectedLevel);
  }
})();
