(function () {
  var CEFR_INDEX = { A1: 0, A2: 1, B1: 2, B2: 3, C1: 4, C2: 5 };
  var selectedTopic = null;
  var selectedLevel = null;
  var sessionId = null;
  var sttModel = "base.en";
  var sttBeam = 5;
  var llmModel = "qwen2.5:3b";
  var llmContext = 10;
  var mediaRecorder = null;
  var audioChunks = [];
  var isRecording = false;
  var isPlaying = false;
  var audioCtx = null;
  var micStream = null;
  var analyserNode = null;
  var visualizerRAF = null;
  var playbackSource = null;

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
  var messageList = document.getElementById("message-list");

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

  function getAudioCtx() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return audioCtx;
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
    if (visualizerRAF) {
      cancelAnimationFrame(visualizerRAF);
      visualizerRAF = null;
    }
    circleIndicator.className = "circle-indicator " + state;
    circleIndicator.style.transform = "scale(1)";
    circleLabel.textContent = label;
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function addMessage(text, role) {
    if (!text) return;
    var msgDiv = document.createElement("div");
    msgDiv.className = "message " + role;
    var bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = text;
    msgDiv.appendChild(bubble);
    messageList.appendChild(msgDiv);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function visualize() {
    if (!analyserNode) return;
    var data = new Uint8Array(analyserNode.frequencyBinCount);
    analyserNode.getByteTimeDomainData(data);
    var sum = 0;
    for (var i = 0; i < data.length; i++) {
      var val = (data[i] - 128) / 128;
      sum += val * val;
    }
    var rms = Math.sqrt(sum / data.length);
    var scale = 1 + rms * 0.3;
    circleIndicator.style.transform = "scale(" + scale + ")";
    visualizerRAF = requestAnimationFrame(visualize);
  }

  function startMicVisualizer(stream) {
    var ctx = getAudioCtx();
    if (ctx.state === "suspended") ctx.resume();
    var source = ctx.createMediaStreamSource(stream);
    analyserNode = ctx.createAnalyser();
    analyserNode.fftSize = 256;
    source.connect(analyserNode);
    if (visualizerRAF) cancelAnimationFrame(visualizerRAF);
    visualize();
  }

  function stopMicVisualizer() {
    if (visualizerRAF) {
      cancelAnimationFrame(visualizerRAF);
      visualizerRAF = null;
    }
    analyserNode = null;
    circleIndicator.style.transform = "scale(1)";
  }

  function startPlaybackVisualizer(arrayBuffer) {
    var ctx = getAudioCtx();
    ctx.decodeAudioData(arrayBuffer)
      .then(function (buffer) {
        analyserNode = ctx.createAnalyser();
        analyserNode.fftSize = 256;

        playbackSource = ctx.createBufferSource();
        playbackSource.buffer = buffer;
        playbackSource.connect(analyserNode);
        analyserNode.connect(ctx.destination);

        isPlaying = true;
        playbackSource.start(0);
        if (visualizerRAF) cancelAnimationFrame(visualizerRAF);
        visualize();

        playbackSource.onended = function () {
          isPlaying = false;
          stopPlaybackVisualizer();
          setCircleState("idle", "Tap mic to start");
        };
      })
      .catch(function (err) {
        logError("Audio decode failed:", err);
        isPlaying = false;
        setCircleState("idle", "Tap mic to start");
      });
  }

  function stopPlaybackVisualizer() {
    if (visualizerRAF) {
      cancelAnimationFrame(visualizerRAF);
      visualizerRAF = null;
    }
    if (playbackSource) {
      try { playbackSource.stop(); } catch (e) {}
      playbackSource.disconnect();
      playbackSource = null;
    }
    analyserNode = null;
    isPlaying = false;
    circleIndicator.style.transform = "scale(1)";
  }

  fetch("/api/progress")
    .then(function (r) { return r.json(); })
    .then(function (progress) {
      selectedTopic = progress.last_topic || null;
      selectedLevel = progress.current_cefr || progress.last_level || null;
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

  var optGroups = document.querySelectorAll(".opt-group");
  optGroups.forEach(function (group) {
    var btns = group.querySelectorAll(".opt-btn");
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        btns.forEach(function (b) { b.classList.remove("is-selected"); });
        btn.classList.add("is-selected");
        var val = btn.dataset.value;
        var descEl = document.getElementById("desc-" + group.dataset.group);
        if (descEl && btn.dataset.desc) descEl.textContent = btn.dataset.desc;
        switch (group.dataset.group) {
          case "stt_model": sttModel = val; break;
          case "stt_beam": sttBeam = parseInt(val, 10); break;
          case "llm_model": llmModel = val; break;
          case "llm_context": llmContext = parseInt(val, 10); break;
        }
      });
    });
  });

  startBtn.addEventListener("click", function () {
    if (!selectedTopic || !selectedLevel) return;
    startBtn.disabled = true;
    startBtn.textContent = "Starting...";

    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: selectedTopic,
        level: selectedLevel,
        llm_model: llmModel,
        context_turns: llmContext,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        sessionId = data.session_id;
        chatTopicLabel.textContent = selectedTopic;
        chatLevelLabel.textContent = selectedLevel;
        messageList.innerHTML = "";
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
    var ctx = getAudioCtx();
    return blobToArrayBuffer(blob)
      .then(function (buf) { return ctx.decodeAudioData(buf); })
      .then(function (audioBuf) {
        var channelData = audioBuf.getChannelData(0);
        log("Decoded audio:", audioBuf.sampleRate, "Hz,", channelData.length, "samples");
        var ratio = audioBuf.sampleRate / 16000;
        var outLen = Math.round(channelData.length / ratio);
        var resampled = new Float32Array(outLen);
        for (var i = 0; i < outLen; i++) {
          var srcIdx = i * ratio;
          var lo = Math.floor(srcIdx);
          var hi = Math.min(lo + 1, channelData.length - 1);
          var frac = srcIdx - lo;
          resampled[i] = channelData[lo] * (1 - frac) + channelData[hi] * frac;
        }
        return floatTo16BitPCM(resampled);
      });
  }

  function addThinking() {
    var msgDiv = document.createElement("div");
    msgDiv.className = "message ai thinking";
    msgDiv.id = "thinking-message";
    var bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = "Thinking<span class='thinking-dot'>.</span><span class='thinking-dot'>.</span><span class='thinking-dot'>.</span>";
    msgDiv.appendChild(bubble);
    messageList.appendChild(msgDiv);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function removeThinking() {
    var el = document.getElementById("thinking-message");
    if (el) el.remove();
  }

  function addCorrection(correction) {
    var card = document.createElement("div");
    card.className = "message correction";
    card.innerHTML =
      '<div class="correction-inline">' +
      '<div class="correction-label">Correction</div>' +
      '<div class="correction-original">' + escapeHtml(correction.original || "") + '</div>' +
      '<div class="correction-corrected">' + escapeHtml(correction.corrected || "") + '</div>' +
      '<div class="correction-explanation">' + escapeHtml(correction.explanation_pt || "") + '</div>' +
      '<div class="correction-type">' + escapeHtml(correction.error_type || "other") + '</div>' +
      "</div>";
    messageList.appendChild(card);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function processAudio(wavBlob) {
    log("Processing audio, size:", (wavBlob.size / 1024).toFixed(1), "KB");

    var formData = new FormData();
    formData.append("file", wavBlob, "recording.wav");
    formData.append("beam_size", String(sttBeam));
    formData.append("stt_model", sttModel);

    setCircleState("processing", "Transcribing...");

    fetch("/api/transcribe", { method: "POST", body: formData })
      .then(function (r) { return r.json(); })
      .then(function (sttData) {
        var transcript = sttData.text || "";
        if (!transcript) {
          logError("Empty transcription");
          setCircleState("idle", "Could not understand audio");
          return;
        }

        addMessage(transcript, "user");
        setCircleState("processing", "Thinking...");
        addThinking();

        return fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            text: transcript,
            llm_model: llmModel,
            context_turns: llmContext,
          }),
        });
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        removeThinking();

        if (data.correction && data.correction.original) {
          addCorrection(data.correction);
        }

        addMessage(data.reply || "", "ai");
        setCircleState("processing", "Generating voice...");

        fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: data.reply || "" }),
        })
          .then(function (r) { return r.blob(); })
          .then(function (blob) {
            if (blob.size === 0) {
              logError("TTS returned empty blob");
              setCircleState("idle", "AI replied (no audio)");
              return;
            }

            setCircleState("playing", "Playing...");
            blobToArrayBuffer(blob)
              .then(function (buf) {
                startPlaybackVisualizer(buf);
              })
              .catch(function (err) {
                logError("Playback visualizer failed:", err);
                setCircleState("idle", "Tap mic to start");
              });
          })
          .catch(function (err) {
            logError("TTS error:", err);
            setCircleState("idle", "AI replied (text only)");
          });
      })
      .catch(function (err) {
        logError("Process audio error:", err);
        removeThinking();
        setCircleState("idle", "AI unavailable");
      });
  }

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        micStream = stream;
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
          setCircleState("processing", "Transcribing...");

          var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
          audioChunks = [];

          webmToWav(blob)
            .then(function (wavBlob) {
              processAudio(wavBlob);
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
    if (isPlaying) return;
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
    if (micStream) startMicVisualizer(micStream);
    setCircleState("recording", "Recording...");
  }

  function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    log("Recording stopping...");
    isRecording = false;
    stopMicVisualizer();
    if (mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    recordBtn.classList.remove("is-recording");
  }

  endSessionBtn.addEventListener("click", function () {
    if (isPlaying) stopPlaybackVisualizer();
    if (isRecording) stopRecording();
    setCircleState("processing", "Generating review...");

    fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderReviewSummary(data.summary, data.level_adjustment);
        showReview();
      })
      .catch(function (err) {
        logError("Review failed:", err);
        setCircleState("idle", "Tap mic to start");
        alert("Failed to generate review. Try again.");
      });
  });

  function renderReviewSummary(summary, levelAdjustment) {
    correctionsList.innerHTML = "";

    if (levelAdjustment) {
      var adjDiv = document.createElement("div");
      adjDiv.className = "level-adjustment";
      var from = levelAdjustment.from || "?";
      var to = levelAdjustment.to || "?";
      var direction = from !== to ? (CEFR_INDEX[from] < CEFR_INDEX[to] ? "up" : "down") : "same";
      if (from !== to) {
        adjDiv.innerHTML =
          '<div class="level-adj-label">Level adjusted</div>' +
          '<div class="level-adj-arrow ' + direction + '">' +
          '<span class="level-from">' + escapeHtml(from) + '</span>' +
          '<span class="level-arrow">&rarr;</span>' +
          '<span class="level-to">' + escapeHtml(to) + '</span>' +
          '</div>';
        correctionsList.appendChild(adjDiv);
      }
    }

    if (!summary || summary.total_errors === 0) {
      correctionsList.innerHTML += '<p class="no-corrections">No errors found. Great job!</p>';
      return;
    }

    var summaryEl = document.createElement("div");
    summaryEl.className = "corrections-summary";
    var byType = summary.by_type || {};
    var typeKeys = Object.keys(byType);
    var html = "<h3>Session Summary</h3>";
    html += "<p class='summary-total'>Total errors: <strong>" + summary.total_errors + "</strong></p>";
    if (typeKeys.length > 0) {
      html += "<div class='summary-bars'>";
      typeKeys.forEach(function (type) {
        var pct = Math.round((byType[type] / summary.total_errors) * 100);
        html +=
          "<div class='summary-row'><span class='summary-label'>" + type +
          "</span><div class='summary-bar'><div class='summary-fill' style='width:" + pct + "%'></div></div>" +
          "<span class='summary-count'>" + byType[type] + "</span></div>";
      });
      html += "</div>";
    }
    var topics = summary.topics_to_review || [];
    if (topics.length > 0) {
      html += "<h3>Topics to Review</h3><ul class='topics-list'>";
      topics.forEach(function (t) {
        html += "<li>" + escapeHtml(t) + "</li>";
      });
      html += "</ul>";
    }
    summaryEl.innerHTML = html;
    correctionsList.appendChild(summaryEl);
  }

  newConversationBtn.addEventListener("click", function () {
    if (isPlaying) stopPlaybackVisualizer();
    if (isRecording) stopRecording();
    sessionId = null;
    audioCtx = null;
    showWelcome();
  });

  function updateStartBtn() {
    startBtn.disabled = !(selectedTopic && selectedLevel);
  }
})();
