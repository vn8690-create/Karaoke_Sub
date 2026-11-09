"use strict";

const $ = (id) => document.getElementById(id);
const state = { project: null, projects: [], segments: [], dirty: false, pending: false, muted: false, poll: null, generation: 0, revision: 0, lyricKey: "", previewRevision: -1, previewLines: [], activeRow: -1, toastTimer: null };
const audio = $("audio");
const backgroundVideo = $("background-video");
const busyStatuses = new Set(["queued", "processing", "rendering", "transcribing", "separating"]);
const clone = (value) => JSON.parse(JSON.stringify(value));
const isBusy = () => state.pending || (state.project && busyStatuses.has(state.project.status));
const fileUrl = (filename) => `/api/projects/${encodeURIComponent(state.project.id)}/files/${encodeURIComponent(filename)}`;
const round = (n) => Math.round(n * 1000) / 1000;
const timeLabel = (n) => `${Math.floor(Math.max(0, n || 0) / 60)}:${String(Math.floor(Math.max(0, n || 0) % 60)).padStart(2, "0")}`;
const exactTime = (n) => `${timeLabel(n)}.${String(Math.floor(((n || 0) % 1) * 100)).padStart(2, "0")}`;

function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

function toast(message, error = false) {
  clearTimeout(state.toastTimer);
  const box = $("toast");
  box.textContent = message;
  box.className = `toast${error ? " error" : ""}`;
  box.hidden = false;
  state.toastTimer = setTimeout(() => { box.hidden = true; }, error ? 11000 : 4500);
}

async function api(path, options = {}) {
  const config = { ...options };
  if (config.body && !(config.body instanceof FormData)) {
    config.headers = { "Content-Type": "application/json", ...config.headers };
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(path, config);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    let detail = data && typeof data === "object" ? data.detail || data.error || data.message : data;
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    if (typeof detail === "object") detail = JSON.stringify(detail);
    throw new Error(detail || `Yêu cầu thất bại (${response.status}).`);
  }
  return data;
}

function updateButtons() {
  const available = Boolean(state.project);
  const blocked = !available || isBusy();
  $("create-button").disabled = state.pending;
  $("transcribe-button").disabled = blocked;
  $("separate-button").disabled = blocked;
  $("add-segment").disabled = blocked;
  $("save-lyrics").disabled = blocked || !state.dirty;
  $("render-button").disabled = blocked || !state.segments.length;
  $("subtitles-button").disabled = blocked || !state.segments.length;
  $("play-button").disabled = !available || !audio.getAttribute("src");
  $("save-state").textContent = state.dirty ? "Chưa lưu" : available && state.segments.length ? "Đã lưu" : "";
  for (const selectId of ["audio-mode", "export-mode"]) {
    const option = $(selectId).querySelector('option[value="instrumental"]');
    option.disabled = !state.project?.files?.instrumental;
  }
  document.querySelectorAll(".word-row input,.word-row button,.delete-line,.add-word").forEach((item) => { item.disabled = Boolean(isBusy()); });
}

function markDirty() {
  state.dirty = true;
  state.revision += 1;
  updateButtons();
  renderPreview();
  $("downloads").hidden = true;
  $("result-panel").hidden = true;
}

function updateProjectSelect() {
  const selected = state.project?.id || "";
  $("project-select").replaceChildren(new Option("Chọn dự án đã lưu", ""));
  for (const project of state.projects) $("project-select").add(new Option(project.title || project.id, project.id));
  $("project-select").value = selected;
}

async function refreshProjects() {
  state.projects = await api("/api/projects");
  if (!Array.isArray(state.projects)) state.projects = state.projects.projects || [];
  updateProjectSelect();
}

function updateProject(project, force = false) {
  const changed = state.project?.id !== project.id;
  if (!state.project?.files?.instrumental && project.files?.instrumental) $("export-mode").value = "instrumental";
  state.project = project;
  if (force || changed || !state.dirty) {
    const next = project.segments || [];
    if (changed || force || JSON.stringify(next) !== JSON.stringify(state.segments)) {
      state.segments = clone(next);
      state.dirty = false;
      state.revision += 1;
      renderEditor();
    }
  }
  $("project-name").textContent = project.title || "Bài hát chưa đặt tên";
  $("stage-badge").textContent = project.title || "YOUR MUSIC. YOUR STAGE.";
  $("duration").textContent = timeLabel(project.duration);
  const oldIndex = state.projects.findIndex((item) => item.id === project.id);
  if (oldIndex >= 0) state.projects[oldIndex] = project; else state.projects.unshift(project);
  updateProjectSelect();
  updateMedia(changed);
  updateProgress();
  updateDownloads();
  updateButtons();
  renderPreview();
  schedulePoll();
}

function updateProgress() {
  const project = state.project;
  const failed = Boolean(project?.error) || project?.status === "error" || project?.status === "failed";
  const panel = $("progress-panel");
  panel.hidden = !project || (!busyStatuses.has(project.status) && !failed);
  panel.classList.toggle("error", failed);
  const progress = Math.max(0, Math.min(100, Number(project?.progress) || 0));
  $("progress-label").textContent = failed ? "Xử lý chưa hoàn tất" : project?.status === "rendering" ? "Đang xuất video karaoke" : "Đang xử lý bài hát";
  $("progress-value").textContent = failed ? "" : `${Math.round(progress)}%`;
  $("progress-bar").value = progress;
  $("progress-bar").hidden = failed;
  $("progress-message").textContent = project?.error || project?.message || "Đang chuẩn bị…";
}

function schedulePoll() {
  clearTimeout(state.poll);
  if (!state.project || !busyStatuses.has(state.project.status)) return;
  const id = state.project.id;
  const generation = state.generation;
  state.poll = setTimeout(async () => {
    try {
      const project = await api(`/api/projects/${encodeURIComponent(id)}`);
      if (generation !== state.generation || state.project?.id !== id) return;
      const wasBusy = busyStatuses.has(state.project.status);
      updateProject(project);
      if (wasBusy && !busyStatuses.has(project.status)) {
        if (project.error) toast(project.error, true);
        else toast(project.message || "Đã xử lý xong. Bạn có thể nghe thử và chỉnh lời.");
      }
    } catch (error) {
      if (generation === state.generation) {
        toast(`Chưa lấy được tiến độ: ${error.message}`, true);
        state.poll = setTimeout(schedulePoll, 3500);
      }
    }
  }, 1500);
}

function updateMedia(changed = false) {
  const project = state.project;
  if (!project) return;
  const files = project.files || {};
  const mode = $("audio-mode").value;
  const filename = mode === "instrumental" ? files.instrumental : files.audio || files.source;
  const url = filename ? fileUrl(filename) : "";
  if (audio.getAttribute("src") !== url) {
    const position = changed ? 0 : audio.currentTime;
    const wasPlaying = !audio.paused;
    audio.pause();
    if (url) audio.src = url; else audio.removeAttribute("src");
    audio.load();
    if (url) audio.addEventListener("loadedmetadata", () => {
      if (Number.isFinite(position)) audio.currentTime = Math.min(position, audio.duration || position);
      if (wasPlaying) audio.play().catch((error) => toast(`Không phát được: ${error.message}`, true));
    }, { once: true });
  }
  updateMute();
  const background = files.background;
  const bgUrl = background ? fileUrl(background) : "";
  const isImage = Boolean(background && /\.(png|jpe?g|webp|gif|bmp)$/i.test(background));
  $("background-image").hidden = !isImage;
  backgroundVideo.hidden = !background || isImage;
  if (isImage && $("background-image").getAttribute("src") !== bgUrl) $("background-image").src = bgUrl;
  if (background && !isImage && backgroundVideo.getAttribute("src") !== bgUrl) {
    backgroundVideo.src = bgUrl;
    backgroundVideo.load();
  }
  if (!background || isImage) backgroundVideo.pause();
}

function updateMute() {
  audio.muted = state.muted || $("audio-mode").value === "silent";
  $("mute-button").setAttribute("aria-pressed", String(state.muted));
  $("mute-button").firstChild.textContent = state.muted ? "⊘ " : "♪ ";
}

function updateDownloads() {
  const box = $("downloads");
  box.replaceChildren();
  if (!state.project || state.dirty || isBusy()) { box.hidden = true; return; }
  const files = state.project.files || {};
  const version = encodeURIComponent(state.project.updated_at || "");
  for (const [key, label] of [["video", "MP4 ↓"], ["ass", "ASS ↓"], ["srt", "SRT ↓"], ["lrc", "LRC ↓"], ["instrumental", "Nhạc beat ↓"]]) {
    if (!files[key]) continue;
    const link = node("a", "", label);
    link.href = `${fileUrl(files[key])}?v=${version}`;
    link.download = files[key];
    box.append(link);
  }
  const projectLink = node("a", "", "Dự án JSON ↓");
  projectLink.href = `/api/projects/${encodeURIComponent(state.project.id)}/download`;
  projectLink.download = "project.json";
  box.append(projectLink);
  box.hidden = false;
  $("result-panel").hidden = !files.video;
  if (files.video) {
    const videoUrl = `${fileUrl(files.video)}?v=${version}`;
    if ($("result-video").getAttribute("src") !== videoUrl) $("result-video").src = videoUrl;
    $("video-download").href = videoUrl;
  }
}

function seekTo(time) {
  if (!state.project) return;
  audio.currentTime = Math.max(0, Math.min(Number(time) || 0, Number.isFinite(audio.duration) ? audio.duration : state.project.duration));
  renderPreview();
}

function lineText(segment) { return (segment.words || []).map((word) => word.text).join(" "); }

function previewLines() {
  if (state.previewRevision === state.revision) return state.previewLines;
  const lines = [];
  state.segments.forEach((segment, sourceIndex) => {
    let chunk = [];
    function flush() {
      if (chunk.length) lines.push({ sourceIndex, start: chunk[0].start, end: chunk[chunk.length - 1].end, words: chunk });
      chunk = [];
    }
    for (const word of segment.words || []) {
      const text = String(word.text || "").trim();
      if (!text) continue;
      // Match the export writer's eight-word / fifty-character line wrapping.
      if (chunk.length && (chunk.length >= 8 || lineText({ words: chunk }).length + text.length > 50)) flush();
      chunk.push({ ...word, text });
    }
    flush();
  });
  state.previewRevision = state.revision;
  state.previewLines = lines;
  return lines;
}

function renderEditor() {
  const container = $("lyrics-list");
  container.replaceChildren();
  state.activeRow = -1;
  $("lyrics-count").textContent = `${state.segments.length} câu`;
  if (!state.segments.length) {
    const empty = node("div", "editor-empty");
    empty.append(node("span", "", "≋"), node("h3", "", "Mỗi lời ca, đúng một nhịp"), node("p", "", "Tạo sub tự động hoặc thêm câu thủ công. Bạn có thể chỉnh lời và thời gian trước khi xuất."));
    container.append(empty);
  }
  state.segments.forEach((segment, index) => {
    const row = node("div", "lyric-row");
    row.dataset.index = index;
    const header = node("div", "lyric-row-header");
    const seekButton = node("button", "line-seek", lineText(segment));
    seekButton.type = "button";
    seekButton.title = "Nghe từ câu này";
    seekButton.addEventListener("click", () => { seekTo(segment.start); audio.play().catch((error) => toast(error.message, true)); });
    const timing = node("span", "line-timing", `${exactTime(segment.start)} → ${exactTime(segment.end)}`);
    const deleteButton = node("button", "delete-line", "×");
    deleteButton.type = "button";
    deleteButton.title = "Xóa câu này";
    deleteButton.setAttribute("aria-label", `Xóa câu ${index + 1}`);
    deleteButton.addEventListener("click", () => { state.segments.splice(index, 1); markDirty(); renderEditor(); });
    header.append(node("span", "line-number", String(index + 1).padStart(2, "0")), seekButton, timing, deleteButton);
    row.append(header);
    const details = node("details", "word-details");
    details.append(node("summary", "", "Chỉnh từng từ"));
    const table = node("div", "word-table");
    const tableHeader = node("div", "word-table-header");
    ["TỪ / LỜI", "BẮT ĐẦU (s)", "KẾT THÚC (s)", ""].forEach((label) => tableHeader.append(node("span", "", label)));
    table.append(tableHeader);
    function updateLine() {
      if (segment.words.length) {
        segment.start = Math.min(...segment.words.map((word) => Number(word.start)));
        segment.end = Math.max(...segment.words.map((word) => Number(word.end)));
      }
      seekButton.textContent = lineText(segment);
      timing.textContent = `${exactTime(segment.start)} → ${exactTime(segment.end)}`;
      markDirty();
    }
    segment.words.forEach((word, wordIndex) => {
      const wordRow = node("div", "word-row");
      for (const key of ["text", "start", "end"]) {
        const input = node("input");
        input.type = key === "text" ? "text" : "number";
        input.value = word[key];
        input.setAttribute("aria-label", `${key === "text" ? "Lời" : key === "start" ? "Bắt đầu" : "Kết thúc"}, từ ${wordIndex + 1}, câu ${index + 1}`);
        if (key !== "text") { input.min = "0"; input.step = "0.01"; }
        else input.maxLength = 100;
        input.addEventListener("input", () => {
          word[key] = key === "text" ? input.value : input.valueAsNumber;
          updateLine();
        });
        wordRow.append(input);
      }
      const removeWord = node("button", "delete-word", "×");
      removeWord.type = "button";
      removeWord.setAttribute("aria-label", `Xóa từ ${wordIndex + 1}, câu ${index + 1}`);
      removeWord.addEventListener("click", () => {
        segment.words.splice(wordIndex, 1);
        if (!segment.words.length) state.segments.splice(index, 1);
        else updateLine();
        markDirty(); renderEditor();
        const reopened = container.querySelector(`.lyric-row[data-index="${index}"] details`);
        if (reopened) reopened.open = true;
      });
      wordRow.append(removeWord);
      table.append(wordRow);
    });
    const addWord = node("button", "add-word", "+ Thêm từ");
    addWord.type = "button";
    addWord.addEventListener("click", () => {
      const start = Number(segment.end) || 0;
      const duration = state.project?.duration || start + .5;
      segment.words.push({ text: "từ", start: round(Math.min(start, Math.max(0, duration - .5))), end: round(Math.min(start + .5, duration)) });
      updateLine(); renderEditor();
      container.querySelector(`.lyric-row[data-index="${index}"] details`).open = true;
    });
    table.append(addWord); details.append(table); row.append(details); container.append(row);
  });
  updateButtons();
}

function renderPreview() {
  const position = audio.currentTime || 0;
  const total = Number.isFinite(audio.duration) ? audio.duration : state.project?.duration || 0;
  $("current-time").textContent = timeLabel(position);
  $("duration").textContent = timeLabel(total);
  $("seek").value = total > 0 ? position / total * 1000 : 0;
  if (!state.project || !state.segments.length) {
    $("stage-empty").hidden = false;
    $("stage-lyrics").hidden = true;
    $("stage-empty").querySelector("p").textContent = state.project ? state.project.title : "Sân khấu đang chờ bài hát của bạn";
    $("stage-empty").querySelector("small").textContent = state.project ? "Nhấn tạo sub tự động hoặc thêm lời thủ công" : "Tải bài hát lên để bắt đầu một dự án mới";
    return;
  }
  $("stage-empty").hidden = true;
  $("stage-lyrics").hidden = false;
  const lines = previewLines();
  if (!lines.length) return;
  let index = lines.findIndex((segment) => position >= segment.start && position <= segment.end);
  let upcoming = false;
  if (index < 0) {
    index = lines.findIndex((segment) => segment.start > position);
    upcoming = index >= 0;
  }
  if (index < 0) index = lines.length - 1;
  const segment = lines[index];
  const key = `${index}-${state.revision}`;
  if (key !== state.lyricKey) {
    state.lyricKey = key;
    $("current-lyric").replaceChildren();
    segment.words.forEach((word, wordIndex) => {
      if (wordIndex) $("current-lyric").append(document.createTextNode(" "));
      $("current-lyric").append(node("span", "lyric-word", word.text));
    });
    $("next-lyric").textContent = lines[index + 1] ? lineText(lines[index + 1]) : "";
  }
  $("lyric-context").textContent = upcoming ? `VÀO LỜI SAU ${Math.ceil(segment.start - position)} GIÂY` : position > segment.end ? "♫" : "";
  const spans = $("current-lyric").children;
  segment.words.forEach((word, wordIndex) => {
    const span = spans[wordIndex];
    span.classList.toggle("sung", position >= word.end);
    const singing = position >= word.start && position < word.end;
    span.classList.toggle("singing", singing);
    if (singing) span.style.setProperty("--word-progress", `${Math.min(100, Math.max(0, (position - word.start) / Math.max(.001, word.end - word.start) * 100))}%`);
  });
  if (state.activeRow !== segment.sourceIndex) {
    document.querySelectorAll(".lyric-row.active").forEach((row) => row.classList.remove("active"));
    const row = $("lyrics-list").querySelector(`.lyric-row[data-index="${segment.sourceIndex}"]`);
    if (row) row.classList.add("active");
    state.activeRow = segment.sourceIndex;
  }
  if (!backgroundVideo.hidden && Number.isFinite(backgroundVideo.duration) && backgroundVideo.duration > 0) {
    const expected = position % backgroundVideo.duration;
    if (Math.abs(backgroundVideo.currentTime - expected) > .5) backgroundVideo.currentTime = expected;
  }
}

function validateSegments() {
  let previousEnd = 0;
  for (let index = 0; index < state.segments.length; index++) {
    const segment = state.segments[index];
    if (!segment.words?.length) throw new Error(`Câu ${index + 1} chưa có lời.`);
    let wordEnd = -1;
    for (const word of segment.words) {
      if (!word.text.trim()) throw new Error(`Câu ${index + 1}: lời có từ đang để trống.`);
      if (!Number.isFinite(word.start) || !Number.isFinite(word.end) || word.start < 0 || word.end <= word.start) throw new Error(`Câu ${index + 1}: thời gian kết thúc mỗi từ phải lớn hơn thời gian bắt đầu.`);
      if (word.start < wordEnd - .001) throw new Error(`Câu ${index + 1}: các từ bị chồng thời gian. Hãy chỉnh lại mốc từng từ.`);
      if (state.project.duration && word.end > state.project.duration + .05) throw new Error(`Câu ${index + 1}: mốc thời gian vượt độ dài bài hát.`);
      word.text = word.text.trim();
      wordEnd = word.end;
    }
    segment.start = segment.words[0].start;
    segment.end = segment.words[segment.words.length - 1].end;
    if (segment.start < previousEnd - .001) throw new Error(`Câu ${index + 1} chồng thời gian với câu trước. Hãy chỉnh mốc từng từ.`);
    previousEnd = segment.end;
  }
}

async function saveLyrics(showToast = true) {
  if (!state.project || !state.dirty) return;
  validateSegments();
  const project = await api(`/api/projects/${encodeURIComponent(state.project.id)}/lyrics`, { method: "PUT", body: { segments: state.segments } });
  updateProject(project, true);
  if (showToast) toast("Đã lưu lời và thời gian.");
}

async function projectAction(action, body) {
  if (!state.project || isBusy()) return;
  try {
    await saveLyrics(false);
    state.pending = true; updateButtons();
    const project = await api(`/api/projects/${encodeURIComponent(state.project.id)}/${action}`, { method: "POST", body });
    updateProject(project);
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; updateButtons(); updateDownloads(); }
}

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.pending || !$("source").files.length) return;
  try {
    await saveLyrics(false);
    state.pending = true; updateButtons();
    $("create-button").textContent = "Đang tải bài hát lên máy…";
    const data = new FormData();
    data.append("title", $("title").value.trim() || $("source").files[0].name.replace(/\.[^.]+$/, ""));
    for (const field of ["source", "background", "instrumental"]) if ($(field).files.length) data.append(field, $(field).files[0]);
    const project = await api("/api/projects", { method: "POST", body: data });
    state.generation += 1;
    state.dirty = false;
    audio.pause();
    $("audio-mode").value = "original";
    $("export-mode").value = project.files?.instrumental ? "instrumental" : "original";
    updateProject(project, true);
    toast("Đã tạo dự án. Tiếp theo, nhấn “Tạo lời & canh thời gian”.");
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; $("create-button").replaceChildren(document.createTextNode("Tạo dự án "), node("span", "", "↗")); updateButtons(); updateDownloads(); }
});

$("project-select").addEventListener("change", async (event) => {
  const id = event.target.value;
  if (!id || id === state.project?.id) return;
  try {
    await saveLyrics(false);
    const project = await api(`/api/projects/${encodeURIComponent(id)}`);
    state.generation += 1;
    state.dirty = false;
    audio.pause();
    $("audio-mode").value = "original";
    $("export-mode").value = project.files?.instrumental ? "instrumental" : "original";
    updateProject(project, true);
  } catch (error) { toast(error.message, true); updateProjectSelect(); }
});

$("new-project").addEventListener("click", async () => {
  try {
    await saveLyrics(false);
    clearTimeout(state.poll);
    state.generation += 1; state.project = null; state.segments = []; state.dirty = false;
    audio.pause(); audio.removeAttribute("src"); audio.load();
    backgroundVideo.pause(); backgroundVideo.removeAttribute("src"); backgroundVideo.load();
    backgroundVideo.hidden = true; $("background-image").hidden = true;
    $("project-name").textContent = "Chưa chọn bài hát";
    $("stage-badge").textContent = "YOUR MUSIC. YOUR STAGE.";
    $("result-panel").hidden = true;
    $("downloads").hidden = true;
    $("upload-form").reset();
    resetFileLabels();
    updateProjectSelect(); renderEditor(); renderPreview(); updateProgress(); updateButtons();
    $("title").focus();
  } catch (error) { toast(error.message, true); }
});

function resetFileLabels() {
  $("source-label").textContent = "Thả bài hát vào đây";
  $("background-label").textContent = "Tùy chọn · lặp theo bài hát";
  $("instrumental-label").textContent = "Tùy chọn · thay cho tách vocal";
}
for (const field of ["source", "background", "instrumental"]) $(field).addEventListener("change", () => {
  if ($(field).files.length) $(`${field}-label`).textContent = $(field).files[0].name;
  if (field === "source" && !$("title").value && $(field).files.length) $("title").value = $(field).files[0].name.replace(/\.[^.]+$/, "");
});
const uploadZone = document.querySelector(".upload-zone");
for (const name of ["dragenter", "dragover"]) uploadZone.addEventListener(name, (event) => { event.preventDefault(); uploadZone.classList.add("drag-over"); });
for (const name of ["dragleave", "drop"]) uploadZone.addEventListener(name, (event) => { event.preventDefault(); uploadZone.classList.remove("drag-over"); });
uploadZone.addEventListener("drop", (event) => {
  if (!event.dataTransfer.files.length) return;
  const transfer = new DataTransfer(); transfer.items.add(event.dataTransfer.files[0]);
  $("source").files = transfer.files;
  $("source").dispatchEvent(new Event("change"));
});

$("transcribe-button").addEventListener("click", () => projectAction("transcribe", { model: $("model").value, language: $("language").value, device: $("device").value, separate: $("separate-first").checked }));
$("separate-button").addEventListener("click", () => projectAction("separate", { device: $("device").value }));
$("save-lyrics").addEventListener("click", async () => { try { await saveLyrics(); } catch (error) { toast(error.message, true); } });

function exportSettings() {
  const fontSize = Number($("font-size").value);
  if (!Number.isFinite(fontSize) || fontSize < 24 || fontSize > 100) throw new Error("Cỡ chữ cần nằm trong khoảng 24–100.");
  return { resolution: $("resolution").value, font_size: Math.round(fontSize) };
}
$("render-button").addEventListener("click", () => {
  try {
    if ($("export-mode").value === "instrumental" && !state.project?.files?.instrumental) throw new Error("Hãy tách vocal hoặc thêm nhạc beat trước khi xuất chế độ karaoke.");
    projectAction("render", { ...exportSettings(), audio_mode: $("export-mode").value });
  } catch (error) { toast(error.message, true); }
});
$("subtitles-button").addEventListener("click", () => { try { projectAction("subtitles", exportSettings()); } catch (error) { toast(error.message, true); } });

$("play-button").addEventListener("click", async () => {
  try { if (audio.paused) await audio.play(); else audio.pause(); }
  catch (error) { toast(`Không phát được bài hát: ${error.message}`, true); }
});
$("mute-button").addEventListener("click", () => { state.muted = !state.muted; updateMute(); });
$("audio-mode").addEventListener("change", () => { updateMedia(); updateButtons(); });
$("seek").addEventListener("input", () => seekTo(Number($("seek").value) / 1000 * (Number.isFinite(audio.duration) ? audio.duration : state.project?.duration || 0)));
audio.addEventListener("play", () => {
  $("play-button").textContent = "Ⅱ"; $("play-button").setAttribute("aria-label", "Tạm dừng");
  if (!backgroundVideo.hidden) backgroundVideo.play().catch(() => {});
  function animate() { renderPreview(); if (!audio.paused) requestAnimationFrame(animate); }
  requestAnimationFrame(animate);
});
audio.addEventListener("pause", () => { $("play-button").textContent = "▶"; $("play-button").setAttribute("aria-label", "Phát"); backgroundVideo.pause(); renderPreview(); });
audio.addEventListener("loadedmetadata", renderPreview);
audio.addEventListener("timeupdate", renderPreview);
audio.addEventListener("seeked", renderPreview);
audio.addEventListener("error", () => { if (audio.getAttribute("src")) toast("Không đọc được âm thanh nghe thử. Hãy chờ xử lý xong hoặc kiểm tra file nguồn.", true); });
$("fullscreen-button").addEventListener("click", async () => {
  try { if (document.fullscreenElement) await document.exitFullscreen(); else await $("stage").requestFullscreen(); }
  catch (error) { toast(`Không mở được toàn màn hình: ${error.message}`, true); }
});
document.addEventListener("keydown", (event) => {
  const target = event.target;
  if (target.matches("input,textarea,select,button") || target.isContentEditable || $("add-dialog").open) return;
  if (event.code === "Space" && !$("play-button").disabled) { event.preventDefault(); $("play-button").click(); }
  if (event.key.toLowerCase() === "m") $("mute-button").click();
});

$("add-segment").addEventListener("click", () => {
  const last = state.segments[state.segments.length - 1];
  const current = audio.currentTime || 0;
  const start = round(Math.max(current, last ? last.end : 0));
  $("new-start").value = start;
  $("new-end").value = round(Math.min(start + 5, state.project.duration || start + 5));
  $("new-line").value = "";
  $("add-dialog").showModal();
  $("new-line").focus();
});
$("close-dialog").addEventListener("click", () => $("add-dialog").close());
$("add-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const start = Number($("new-start").value), end = Number($("new-end").value);
  const words = $("new-line").value.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) return toast("Thời gian kết thúc cần lớn hơn thời gian bắt đầu.", true);
  if (state.project.duration && end > state.project.duration + .05) return toast("Câu hát vượt độ dài bài hát.", true);
  if (state.segments.some((segment) => start < segment.end && end > segment.start)) return toast("Câu hát đang chồng thời gian với câu khác. Chọn khoảng trống trong bài hát.", true);
  const interval = (end - start) / words.length;
  state.segments.push({ start, end, words: words.map((text, index) => ({ text, start: round(start + interval * index), end: round(start + interval * (index + 1)) })) });
  state.segments.sort((a, b) => a.start - b.start);
  markDirty(); renderEditor(); $("add-dialog").close(); seekTo(start);
});

function resizePreview() {
  const width = $("stage").clientWidth;
  const size = Number($("font-size").value) || 54;
  $("current-lyric").style.fontSize = `${Math.max(15, width * size / 1920)}px`;
}
window.addEventListener("resize", resizePreview);
document.addEventListener("fullscreenchange", resizePreview);
$("font-size").addEventListener("input", resizePreview);
$("resolution").addEventListener("change", resizePreview);
window.addEventListener("beforeunload", (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ""; } });

async function initialize() {
  resizePreview(); renderEditor(); updateButtons();
  const results = await Promise.allSettled([api("/api/system"), refreshProjects()]);
  if (results[0].status === "fulfilled") {
    const info = results[0].value;
    $("gpu-status").textContent = info.cuda ? `CUDA · ${info.gpu || "NVIDIA GPU"}` : info.torch ? "CPU · chưa có CUDA" : "Chưa cài AI · xem hướng dẫn";
    $("gpu-status").title = info.model_cache ? `Model cache: ${info.model_cache}` : "Chọn CUDA khi đã cài bản PyTorch hỗ trợ NVIDIA.";
    if (!info.ffmpeg || !info.ffprobe) toast("Chưa tìm thấy FFmpeg / FFprobe. Hãy chạy bộ cài trước khi tạo dự án.", true);
  } else { $("gpu-status").textContent = "Chưa kết nối máy chủ"; toast(`Không kiểm tra được hệ thống: ${results[0].reason.message}`, true); }
  if (results[1].status === "rejected") toast(`Không tải được dự án: ${results[1].reason.message}`, true);
}
initialize();
