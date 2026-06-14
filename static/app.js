const loaderView = document.querySelector("#loaderView");
const chatView = document.querySelector("#chatView");
const ingestForm = document.querySelector("#ingestForm");
const chatForm = document.querySelector("#chatForm");
const channelUrlInput = document.querySelector("#channelUrl");
const creatorNameInput = document.querySelector("#creatorName");
const statusText = document.querySelector("#statusText");
const progressPanel = document.querySelector("#progressPanel");
const progressStage = document.querySelector("#progressStage");
const progressPercent = document.querySelector("#progressPercent");
const progressFill = document.querySelector("#progressFill");
const progressDetail = document.querySelector("#progressDetail");
const loadButton = document.querySelector("#loadButton");
const overwriteBox = document.querySelector("#overwriteBox");
const overwriteMessage = document.querySelector("#overwriteMessage");
const overwriteButton = document.querySelector("#overwriteButton");
const useExistingButton = document.querySelector("#useExistingButton");
const refreshCreatorsButton = document.querySelector("#refreshCreatorsButton");
const creatorList = document.querySelector("#creatorList");
const activeCreatorName = document.querySelector("#activeCreatorName");
const switchCreatorButton = document.querySelector("#switchCreatorButton");
const messages = document.querySelector("#messages");
const questionInput = document.querySelector("#questionInput");
const sendButton = document.querySelector("#sendButton");

let activeCreator = "";
let pendingIngest = null;
let progressPoll = null;

function setStatus(message) {
  statusText.textContent = message;
}

function setLoading(isLoading) {
  loadButton.disabled = isLoading;
  overwriteButton.disabled = isLoading;
  sendButton.disabled = isLoading;
}

function resetProgress() {
  if (progressPoll) {
    clearInterval(progressPoll);
    progressPoll = null;
  }
  progressPanel.classList.add("hidden");
  progressStage.textContent = "Starting";
  progressPercent.textContent = "0%";
  progressFill.style.width = "0%";
  progressDetail.textContent = "";
}

function updateProgress(job) {
  const percent = Number.isFinite(job.percent) ? Math.max(0, Math.min(job.percent, 100)) : 0;
  progressPanel.classList.remove("hidden");
  progressStage.textContent = labelForStage(job.stage || job.status || "running");
  progressPercent.textContent = `${percent}%`;
  progressFill.style.width = `${percent}%`;

  const parts = [];
  if (job.message) {
    parts.push(job.message);
  }
  if (job.videos_total) {
    parts.push(`${job.videos_processed || 0}/${job.videos_total} videos with captions processed`);
  } else if (job.videos_processed) {
    parts.push(`${job.videos_processed} videos processed`);
  }
  if (job.chunks_stored) {
    parts.push(`${job.chunks_stored} chunks stored`);
  }
  progressDetail.textContent = parts.join(" · ");
}

function labelForStage(stage) {
  const labels = {
    queued: "Queued",
    checking: "Checking",
    resetting: "Replacing",
    video_list: "Fetching videos",
    captions: "Downloading captions",
    chunking: "Chunking transcripts",
    embedding: "Embedding chunks",
    complete: "Complete",
    error: "Error",
    running: "Working",
  };
  return labels[stage] || "Working";
}

function showLoader() {
  chatView.classList.add("hidden");
  loaderView.classList.remove("hidden");
  loadCreators();
}

function showChat(creatorName) {
  activeCreator = creatorName;
  activeCreatorName.textContent = creatorName;
  messages.innerHTML = "";
  appendMessage("assistant", `Loaded ${creatorName}. Ask a question from the ingested videos.`);
  loaderView.classList.add("hidden");
  chatView.classList.remove("hidden");
  questionInput.focus();
}

function appendMessage(role, text, sources = []) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  message.textContent = text;

  if (sources.length) {
    const details = document.createElement("details");
    details.className = "sources";
    const summary = document.createElement("summary");
    summary.textContent = "Sources";
    details.append(summary);
    sources.forEach((source) => {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = source.title || source.url;
      details.append(link);
    });
    message.append(details);
  }

  messages.append(message);
  messages.scrollTop = messages.scrollHeight;
  return message;
}

async function ingestCreator(overwrite = false) {
  const payload = pendingIngest || {
    channel_url: channelUrlInput.value.trim(),
    creator_name: creatorNameInput.value.trim(),
  };
  payload.overwrite = overwrite;
  pendingIngest = payload;

  overwriteBox.classList.add("hidden");
  resetProgress();
  setLoading(true);
  setStatus("Starting ingestion. The chat box will open when loading finishes.");

  try {
    const response = await fetch("/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (response.status === 409) {
      const detail = data.detail || data;
      overwriteMessage.textContent = detail.message || `${payload.creator_name} already exists.`;
      overwriteBox.classList.remove("hidden");
      setStatus("Choose whether to use the existing creator or re-ingest.");
      return;
    }

    if (!response.ok) {
      throw new Error(data.detail || "Ingestion failed");
    }

    if (data.job_id) {
      updateProgress(data);
      pollIngestJob(data.job_id);
      return;
    }

    finishIngest(data);
  } catch (error) {
    setStatus(error.message || "Something went wrong, please try again.");
    setLoading(false);
  }
}

async function pollIngestJob(jobId) {
  progressPoll = setInterval(async () => {
    try {
      const response = await fetch(`/ingest/${jobId}`);
      const job = await response.json();
      if (!response.ok) {
        throw new Error(job.detail || "Could not read ingestion progress");
      }

      updateProgress(job);

      if (job.status === "complete") {
        clearInterval(progressPoll);
        progressPoll = null;
        finishIngest(job.result || job);
      }

      if (job.status === "error") {
        clearInterval(progressPoll);
        progressPoll = null;
        setStatus(job.error || job.message || "Ingestion failed.");
        setLoading(false);
      }
    } catch (error) {
      clearInterval(progressPoll);
      progressPoll = null;
      setStatus(error.message || "Could not read ingestion progress.");
      setLoading(false);
    }
  }, 1000);
}

async function finishIngest(data) {
  setStatus(`Done. ${data.videos_processed} videos processed, ${data.chunks_stored} chunks stored.`);
  updateProgress({
    stage: "complete",
    message: "Creator loaded. Opening chat.",
    percent: 100,
    videos_processed: data.videos_processed,
    chunks_stored: data.chunks_stored,
  });
  await loadCreators();
  setLoading(false);
  showChat(data.creator_name);
}

async function loadCreators() {
  creatorList.innerHTML = "";
  try {
    const response = await fetch("/creators");
    const creators = await response.json();
    if (!creators.length) {
      creatorList.textContent = "No creators loaded yet.";
      return;
    }
    creators.forEach((creator) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = creator.creator_name;
      button.addEventListener("click", () => showChat(creator.creator_name));
      creatorList.append(button);
    });
  } catch {
    creatorList.textContent = "Could not load creators.";
  }
}

ingestForm.addEventListener("submit", (event) => {
  event.preventDefault();
  pendingIngest = null;
  ingestCreator(false);
});

overwriteButton.addEventListener("click", () => ingestCreator(true));

useExistingButton.addEventListener("click", () => {
  const creatorName = pendingIngest?.creator_name || creatorNameInput.value.trim();
  overwriteBox.classList.add("hidden");
  setStatus("");
  showChat(creatorName);
});

refreshCreatorsButton.addEventListener("click", loadCreators);

switchCreatorButton.addEventListener("click", showLoader);

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!activeCreator) {
    appendMessage("error", "Load a creator first");
    return;
  }
  if (!question) {
    return;
  }

  questionInput.value = "";
  appendMessage("user", question);
  const typing = appendMessage("assistant", "Thinking...");
  sendButton.disabled = true;

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, creator_name: activeCreator }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Something went wrong, please try again");
    }
    typing.remove();
    appendMessage("assistant", data.answer, data.sources || []);
  } catch {
    typing.remove();
    appendMessage("assistant error", "Something went wrong, please try again");
  } finally {
    sendButton.disabled = false;
    questionInput.focus();
  }
});

loadCreators();
