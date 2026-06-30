(function () {
  var selectedTopic = null;
  var selectedLevel = null;

  var topicGrid = document.getElementById("topic-grid");
  var levelBtns = document.querySelectorAll(".level-btn");
  var startBtn = document.getElementById("start-btn");

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
        window.location.href = "/chat?session_id=" + data.session_id;
      })
      .catch(function () {
        startBtn.disabled = false;
        startBtn.textContent = "Start Conversation";
        alert("Failed to start session. Try again.");
      });
  });

  function updateStartBtn() {
    startBtn.disabled = !(selectedTopic && selectedLevel);
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }
})();
