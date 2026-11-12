"use strict";

const $ = (id) => document.getElementById(id);
const state = { project: null, projects: [], segments: [], dirty: false, referenceDirty: false, mediaPending: false, backgroundAssets: [], backgroundProviders: [], pending: false, muted: false, poll: null, generation: 0, revision: 0, lyricKey: "", previewRevision: -1, previewLines: [], activeRow: -1, toastTimer: null, smartPreview: null };
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

function showGuide(open, { scroll = false, focus = false } = {}) {
  const panel = $("guide-panel");
  panel.hidden = !open;
  for (const id of ["help-toggle", "quick-help"]) $(id).setAttribute("aria-expanded", String(open));
  if (open && scroll) panel.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  if (focus) (open ? $("guide-title") : $("help-toggle")).focus({ preventScroll: true });
}

$("help-toggle").addEventListener("click", () => showGuide($("guide-panel").hidden, { scroll: true, focus: true }));
$("quick-help").addEventListener("click", () => showGuide(true, { scroll: true, focus: true }));
$("close-guide").addEventListener("click", () => showGuide(false, { focus: true }));
document.querySelectorAll("[data-guide-target]").forEach((button) => {
  button.addEventListener("click", () => {
    showGuide(false);
    const target = $(button.dataset.guideTarget);
    target.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    target.focus({ preventScroll: true });
  });
});

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

function referenceText() { return $("reference-lyrics").value; }

function syncReference(project, { changed = false, preserveDraft = false } = {}) {
  const saved = project.reference_lyrics || {};
  if (changed && preserveDraft && referenceText().trim()) {
    state.referenceDirty = true;
  } else if (changed || !state.referenceDirty) {
    $("reference-lyrics").value = saved.raw_text || "";
    state.referenceDirty = false;
  }
  if (changed) {
    $("reference-file").value = "";
    $("reference-file-name").textContent = "UTF-8 / UTF-16 · tối đa 200 KB";
    $("timing-offset").value = "0";
  }
  updateReferenceStatus();
}

function updateReferenceStatus() {
  const project = state.project;
  const saved = project?.reference_lyrics;
  const hasText = Boolean(referenceText().trim());
  const status = $("reference-status");
  if (!project) status.textContent = hasText ? "Đã nhập lời. Tạo hoặc chọn dự án để lưu và căn thời gian." : "Có thể nhập lời trước, rồi tạo hoặc chọn dự án.";
  else if (state.referenceDirty) status.textContent = "Lời chuẩn chưa lưu. Lưu để xem phần chữ đã bỏ chỉ dẫn, hoặc căn trực tiếp theo giọng hát.";
  else if (saved?.text) status.textContent = `Đã lưu lời chuẩn · ${saved.lines?.length || saved.text.split("\n").length} câu · bỏ ${saved.ignored_lines || 0} dòng chỉ dẫn.`;
  else status.textContent = "Chọn TXT hoặc dán lời đúng, rồi lưu hoặc căn theo giọng hát.";
  $("reference-preview").hidden = !saved?.text;
  $("reference-cleaned").textContent = saved?.text || "";
  $("reference-preview-label").textContent = state.referenceDirty ? "Lời chuẩn đã lưu trước đó (chưa gồm phần đang sửa)" : "Xem lời đã bỏ chỉ dẫn";

  const notice = $("alignment-notice");
  notice.replaceChildren();
  const alignment = project?.alignment;
  const stale = Boolean(project?.segments?.length && (state.referenceDirty || project.reference_pending || alignment?.stale ||
    (saved?.text && (!alignment || alignment.source !== "reference" || (alignment.reference_text && alignment.reference_text !== saved.text)))));
  if (stale) notice.append(node("p", "", alignment?.engine === "smart-sync"
    ? "Smart Sync đã sửa một phần lời; những câu chưa được duyệt vẫn giữ nguyên. Hãy kiểm tra câu đỏ/vàng hoặc chỉnh tay. Không cần căn lại toàn bài."
    : "Lời chuẩn và mốc hiện tại chưa khớp nhau. Hãy thử Smart Lyrics Sync để ghép chữ TXT với thời gian đã có, hoặc dùng Căn lời theo giọng hát để căn lại."));
  if (!stale && alignment?.source === "reference" && alignment?.engine !== "manual-estimate") {
    notice.append(node("p", "alignment-success", alignment?.engine === "smart-sync"
      ? "Đã dùng chữ TXT qua Smart Sync. Những mốc ước lượng vẫn cần nghe kiểm tra."
      : alignment?.engine === "manual-preserve"
      ? "Đã dùng đúng chữ TXT, GIỮ NGUYÊN thời gian từng từ trước đó."
      : "Đã căn theo lời chuẩn. Nghe kiểm tra các mốc trước khi xuất."));
  }
  if (Array.isArray(alignment?.warnings)) for (const warning of alignment.warnings) notice.append(node("p", "", warning));
  notice.hidden = !notice.childNodes.length;
  notice.classList.toggle("stale", stale);
}

async function saveReference(showToast = true) {
  if (!state.project || !state.referenceDirty) return;
  const text = referenceText();
  if (!text.trim()) return;
  const projectId = state.project.id;
  const project = await api(`/api/projects/${encodeURIComponent(projectId)}/reference`, { method: "PUT", body: { text } });
  if (state.project?.id !== projectId) return;
  if (referenceText() === text) state.referenceDirty = false;
  updateProject(project);
  if (showToast) toast("Đã lưu lời chuẩn. Nhấn Căn lời theo giọng hát để tạo thời gian từ âm thanh.");
  return project;
}

$("reference-lyrics").addEventListener("input", () => {
  state.referenceDirty = referenceText() !== (state.project?.reference_lyrics?.raw_text || "");
  updateReferenceStatus(); updateButtons();
});
$("reference-file").addEventListener("change", async () => {
  const file = $("reference-file").files[0];
  if (!file) return;
  const generation = state.generation;
  try {
    if (!/\.txt$/i.test(file.name)) throw new Error("Vui lòng chọn file .txt chứa lời bài hát.");
    if (file.size > 200 * 1024) throw new Error("File lời tối đa 200 KB. Chỉ giữ lời bài hát cần căn.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (state.generation !== generation) return;
    const encoding = bytes[0] === 0xff && bytes[1] === 0xfe ? "utf-16le" : bytes[0] === 0xfe && bytes[1] === 0xff ? "utf-16be" : "utf-8";
    let text;
    try { text = new TextDecoder(encoding, { fatal: true }).decode(bytes).replace(/^\uFEFF/, ""); }
    catch (_) { throw new Error("Không đọc được mã chữ. Hãy lưu TXT dạng UTF-8 (hoặc UTF-16 có BOM) rồi thử lại."); }
    if (text.length > 100000) throw new Error("Lời tối đa 100.000 ký tự.");
    if (text.includes("\u0000")) throw new Error("File có dữ liệu không phải văn bản. Hãy lưu lời thành TXT UTF-8 rồi thử lại.");
    $("reference-lyrics").value = text;
    $("reference-file-name").textContent = file.name;
    $("reference-lyrics").dispatchEvent(new Event("input"));
    toast("Đã đọc TXT. Nhấn Lưu lời chuẩn hoặc Căn lời theo giọng hát.");
  } catch (error) { $("reference-file").value = ""; toast(error.message, true); }
});
$("save-reference").addEventListener("click", async () => {
  if (isBusy()) return;
  state.pending = true; updateButtons();
  try { await saveReference(); }
  catch (error) { toast(error.message, true); }
  finally { state.pending = false; updateButtons(); updateDownloads(); }
});
$("apply-reference").addEventListener("click", async () => {
  if (isBusy() || !state.project || !referenceText().trim()) return;
  const estimate = $("reference-allow-estimate").checked;
  if (estimate && !window.confirm("Số câu/từ khác nhau sẽ làm mốc từng từ thành ƯỚC LƯỢNG. Dự án giữ bản sao lời cũ. Tiếp tục ghép TXT?")) return;
  state.pending = true; updateButtons();
  try {
    if (state.referenceDirty) await saveReference(false);
    if (!state.project) throw new Error("Hãy chọn dự án trước.");
    const projectId = state.project.id;
    const project = await api(`/api/projects/${encodeURIComponent(projectId)}/reference/apply-timing`, {
      method: "POST", body: { estimate },
    });
    if (state.project?.id !== projectId) return;
    $("reference-allow-estimate").checked = false;
    updateProject(project, true);
    toast(estimate
      ? "Đã ghép đúng chữ TXT bằng mốc ƯỚC LƯỢNG. Hãy nghe và chỉnh từng từ trước khi xuất."
      : "Đã ghép đúng chữ TXT và giữ nguyên TOÀN BỘ mốc từng từ!");
  } catch (error) {
    toast(error.message, true);
  } finally { state.pending = false; updateButtons(); updateDownloads(); }
});


const smartLabels = { safe: "Xanh · giữ mốc", review: "Vàng · cần duyệt",
  blocked: "Đỏ · chưa ghép", same: "Không đổi" };

function smartSelectedRows() {
  return [...$("smart-rows").querySelectorAll("input[type=checkbox]:checked")].map((item) => item.value);
}

function renderSmartPanel() {
  const preview = state.smartPreview;
  const canUndo = Boolean(state.project?.smart_sync?.can_undo);
  $("smart-panel").hidden = !preview && !canUndo;
  const container = $("smart-rows");
  container.replaceChildren();
  if (!preview) {
    $("smart-summary").textContent = canUndo
      ? "Đã cập nhật lời bằng Smart Sync. Có thể hoàn tác trước khi chỉnh tay thêm."
      : "";
    updateButtons();
    return;
  }
  const counts = preview.counts;
  $("smart-summary").textContent =
    counts.safe + " câu xanh · " + counts.review + " câu vàng · "
    + counts.blocked + " câu đỏ · " + counts.same + " câu đã đúng. "
    + "Xanh được chọn trước, vàng phải tự chọn. Đỏ không thể áp dụng tự động.";
  for (const item of preview.items) {
    const row = node("article", "smart-row smart-" + item.status);
    const heading = node("div", "smart-row-heading");
    const badge = node("strong", "smart-status", smartLabels[item.status] || "Kiểm tra");
    heading.append(badge);
    if (item.old_index !== null) {
      const listen = node("button", "smart-listen", "▶ " + exactTime(item.start));
      listen.type = "button";
      listen.title = "Nghe đoạn trước khi chấp nhận sửa lời";
      listen.addEventListener("click", () => {
        seekTo(item.start);
        audio.play().catch((e) => toast("Không phát được: " + e.message, true));
      });
      heading.append(listen);
    }
    if (item.status === "safe" || item.status === "review") {
      const label = node("label", "smart-check");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = item.id;
      input.checked = item.status === "safe";
      input.addEventListener("change", updateButtons);
      label.append(input, node("span", "", "Chọn sửa"));
      heading.append(label);
    }
    row.append(heading);
    const compare = node("div", "smart-compare");
    const before = node("div", "smart-compare-pane");
    before.append(node("small", "", "Whisper / lời đang có"),
                  node("p", "", item.old_text || "(Chưa có câu trong audio)"));
    const after = node("div", "smart-compare-pane");
    after.append(node("small", "", "Lời từ TXT chuẩn"),
                 node("p", "", item.new_text || "(Không tìm thấy lời TXT tương ứng)"));
    compare.append(before, after);
    row.append(compare);
    row.append(node("p", "smart-explain", item.reason
      + (item.score ? " · Độ tương đồng chữ: " + item.score + "%" : "")));
    container.append(row);
  }
  updateButtons();
}

$("smart-preview").addEventListener("click", async () => {
  if (isBusy() || !state.project || state.dirty) {
    toast("Hãy Lưu lời đang chỉnh trước khi chạy Smart Sync.", true);
    return;
  }
  const projectId = state.project.id;
  state.pending = true;
  updateButtons();
  try {
    if (state.referenceDirty) await saveReference(false);
    const result = await api("/api/projects/" + encodeURIComponent(projectId) + "/smart-sync/preview",
                             { method: "POST" });
    if (state.project?.id !== projectId) return;
    state.smartPreview = {
      ...result, projectId,
      segmentKey: JSON.stringify(state.project.segments || []),
      referenceText: state.project.reference_lyrics?.text || "",
    };
    renderSmartPanel();
    $("smart-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast("Smart Sync: " + error.message, true);
  } finally { state.pending = false; updateButtons(); }
});

$("smart-apply").addEventListener("click", async () => {
  const preview = state.smartPreview;
  if (isBusy() || state.dirty || !preview || !state.project) return;
  const selected = smartSelectedRows();
  if (!selected.length) return toast("Chưa chọn câu để sửa.", true);
  const selectedReview = preview.items.filter((row) => selected.includes(row.id) && row.status === "review");
  if (selectedReview.length && !window.confirm(
    "Bạn đã chọn " + selectedReview.length + " câu VÀNG cần kiểm tra. "
    + "Có thể có từ được ước lượng thời gian. Áp dụng rồi nghe lại từng đoạn nhé?"
  )) return;
  const projectId = state.project.id;
  state.pending = true; updateButtons();
  try {
    const updated = await api("/api/projects/" + encodeURIComponent(projectId) + "/smart-sync/apply", {
      method: "POST", body: { revision: preview.revision, selected },
    });
    if (state.project?.id !== projectId) return;
    state.smartPreview = null;
    updateProject(updated, true);
    toast("Đã áp dụng " + selected.length + " câu từ TXT; các câu đỏ giữ nguyên. "
      + "Có thể Hoàn tác nếu cần.");
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; updateButtons(); }
});

$("smart-undo").addEventListener("click", async () => {
  if (isBusy() || !state.project || state.dirty || !state.project.smart_sync?.can_undo) return;
  if (!window.confirm("Hoàn tác Smart Sync gần nhất? Mốc và lời trước đó sẽ được khôi phục.")) return;
  const projectId = state.project.id;
  state.pending = true; updateButtons();
  try {
    const restored = await api("/api/projects/" + encodeURIComponent(projectId) + "/smart-sync/undo", {
      method: "POST",
    });
    if (state.project?.id !== projectId) return;
    state.smartPreview = null;
    updateProject(restored, true);
    toast("Đã hoàn tác Smart Sync, phục hồi lời và mốc cũ.");
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; updateButtons(); }
});

$("align-button").addEventListener("click", () => projectAction("align", {
  text: referenceText(), model: $("model").value, language: $("language").value,
  device: $("device").value, separate: $("separate-first").checked,
}));
$("timing-offset").addEventListener("input", updateButtons);
$("apply-timing").addEventListener("click", async () => {
  const offset = Number($("timing-offset").value);
  if (!Number.isFinite(offset) || offset < -30 || offset > 30 || !offset) return toast("Nhập số giây cần dịch từ -30 đến 30, khác 0.", true);
  const project = await projectAction("timing", { offset_seconds: offset });
  if (project) { $("timing-offset").value = "0"; updateButtons(); toast(`Đã dịch toàn bài ${offset > 0 ? "+" : ""}${offset} giây. Nghe lại trước khi xuất.`); }
});

function safeMediaUrl(value) {
  if (typeof value !== "string" || !value) return null;
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch (_) { return null; }
}

function providerConfigured() {
  const id = $("background-provider").value;
  return id === "commons" || Boolean(state.backgroundProviders.find((provider) => provider.id === id)?.configured);
}

function updateBackgroundMode() {
  const mode = $("background-mode").value;
  $("background-manual").hidden = mode !== "manual";
  $("background-local").hidden = mode !== "local";
  $("background-online").hidden = mode !== "online";
  if (mode === "manual") $("background-auto").checked = false;
  $("provider-status").textContent = $("background-provider").value === "pexels" ? providerConfigured() ? "Pexels đã được cấu hình. Key không được hiển thị lại." : "Pexels chưa có key. Có thể dùng Wikimedia Commons ngay." : "Wikimedia Commons không cần API key.";
  updateBackgroundButtons();
}

function updateBackgroundButtons() {
  const mode = $("background-mode").value;
  const unavailable = mode === "online" && !providerConfigured();
  $("background-mode").disabled = state.mediaPending || state.pending;
  $("background-provider").disabled = state.mediaPending;
  $("background-folder").disabled = state.mediaPending;
  $("background-query").disabled = state.mediaPending;
  $("background-recursive").disabled = state.mediaPending;
  $("scan-backgrounds").disabled = state.mediaPending || !$("background-folder").value.trim();
  $("search-backgrounds").disabled = state.mediaPending || !$("background-query").value.trim() || !providerConfigured();
  $("save-provider-key").disabled = state.mediaPending || !$("pexels-key").value.trim();
  $("background-auto").disabled = mode === "manual" || state.mediaPending || state.pending;
  $("auto-background-button").disabled = !state.project || isBusy() || state.mediaPending || mode === "manual" || unavailable;
  document.querySelectorAll(".use-background").forEach((button) => { button.disabled = !state.project || Boolean(isBusy()) || state.mediaPending; });
}

function backgroundRequest() {
  const mode = $("background-mode").value;
  if (mode === "local") {
    const folder = $("background-folder").value.trim();
    if (!folder) throw new Error("Nhập đường dẫn thư mục video trên máy chạy app trước.");
    return { mode: "local", folder, recursive: $("background-recursive").checked };
  }
  if (mode === "online") {
    const query = $("background-query").value.trim();
    if (!query) throw new Error("Nhập từ khóa tìm video nền trước.");
    if (!providerConfigured()) throw new Error("Pexels chưa có API key. Lưu key hoặc chọn Wikimedia Commons.");
    return { mode: "online", provider: $("background-provider").value, query };
  }
  throw new Error("Chọn nguồn Thư mục video trên máy hoặc Kho video online để tự lấy nền.");
}

function renderBackgroundResults(assets) {
  state.backgroundAssets = Array.isArray(assets) ? assets : [];
  const box = $("background-results"); box.replaceChildren();
  for (const asset of state.backgroundAssets) {
    const card = node("article", "background-card");
    const preview = safeMediaUrl(asset.preview_url);
    if (preview) {
      const media = node(asset.provider === "local" ? "video" : "img", "background-thumb");
      media.src = preview;
      if (asset.provider === "local") { media.controls = true; media.muted = true; media.preload = "none"; }
      else { media.alt = asset.title || "Video nền"; media.loading = "lazy"; }
      card.append(media);
    }
    card.append(node("strong", "background-card-title", asset.title || "Video nền"));
    const credit = [asset.author, asset.license].filter(Boolean).join(" · ");
    if (credit) card.append(node("p", "background-credit", credit));
    const links = node("div", "background-links");
    for (const [value, label] of [[asset.source_url, "Xem nguồn"], [asset.license_url, "Giấy phép"]]) {
      const href = safeMediaUrl(value);
      if (href) { const link = node("a", "", label); link.href = href; link.target = "_blank"; link.rel = "noopener noreferrer"; links.append(link); }
    }
    if (links.childNodes.length) card.append(links);
    const use = node("button", "button small secondary use-background", "Dùng nền này");
    use.type = "button";
    use.addEventListener("click", async () => {
      const project = await projectAction("background", { mode: "selected", asset_id: asset.id });
      if (project) $("background-status").textContent = "Đang chuẩn bị nền đã chọn. Theo dõi tiến độ xử lý của dự án.";
    });
    card.append(use); box.append(card);
  }
  $("background-status").textContent = state.backgroundAssets.length ? `Tìm được ${state.backgroundAssets.length} video. Xem nguồn/giấy phép, rồi dùng clip phù hợp.` : "Chưa tìm thấy video. Thử từ khóa hoặc thư mục khác.";
  updateBackgroundButtons();
}

function updateBackgroundAttribution() {
  const info = state.project?.background_info;
  const box = $("background-attribution"); box.replaceChildren();
  box.hidden = !info;
  if (!info) return;
  box.append(node("strong", "", "Nền đang dùng"), node("p", "", info.title || "Video nền"));
  const credit = [info.provider, info.author, info.license].filter(Boolean).join(" · ");
  if (credit) box.append(node("p", "background-credit", credit));
  for (const [value, label] of [[info.source_url, "Nguồn video"], [info.license_url, "Giấy phép"]]) {
    const href = safeMediaUrl(value);
    if (href) { const link = node("a", "", label); link.href = href; link.target = "_blank"; link.rel = "noopener noreferrer"; box.append(link); }
  }
}

async function loadBackgroundProviders() {
  const data = await api("/api/backgrounds/providers");
  state.backgroundProviders = data.providers || [];
  updateBackgroundMode();
}

$("background-mode").addEventListener("change", updateBackgroundMode);
$("background-provider").addEventListener("change", updateBackgroundMode);
for (const id of ["background-folder", "background-query", "pexels-key"]) $(id).addEventListener("input", updateBackgroundButtons);
$("scan-backgrounds").addEventListener("click", async () => {
  if (state.mediaPending) return;
  try {
    const body = { folder: $("background-folder").value.trim(), recursive: $("background-recursive").checked };
    if (!body.folder) throw new Error("Nhập đường dẫn thư mục video trước.");
    state.mediaPending = true; updateBackgroundButtons();
    $("background-status").textContent = "Đang quét video trong thư mục…";
    const data = await api("/api/backgrounds/local/scan", { method: "POST", body });
    renderBackgroundResults(data.assets);
  } catch (error) { $("background-status").textContent = error.message; toast(error.message, true); }
  finally { state.mediaPending = false; updateBackgroundButtons(); }
});
$("search-backgrounds").addEventListener("click", async () => {
  if (state.mediaPending) return;
  try {
    const query = $("background-query").value.trim();
    if (!query) throw new Error("Nhập từ khóa tìm video trước.");
    state.mediaPending = true; updateBackgroundButtons();
    $("background-status").textContent = "Đang tìm video online…";
    const data = await api("/api/backgrounds/search", { method: "POST", body: { query, provider: $("background-provider").value, limit: 6 } });
    renderBackgroundResults(data.assets);
  } catch (error) { $("background-status").textContent = error.message; toast(error.message, true); }
  finally { state.mediaPending = false; updateBackgroundButtons(); }
});
$("save-provider-key").addEventListener("click", async () => {
  if (state.mediaPending) return;
  try {
    const key = $("pexels-key").value.trim();
    if (!key) return;
    state.mediaPending = true; updateBackgroundButtons();
    const data = await api("/api/backgrounds/settings", { method: "PUT", body: { pexels_api_key: key } });
    $("pexels-key").value = "";
    if (Array.isArray(data.providers)) state.backgroundProviders = data.providers;
    else await loadBackgroundProviders();
    updateBackgroundMode(); toast("Đã lưu API key vào cấu hình local.");
  } catch (error) { toast(error.message, true); }
  finally { state.mediaPending = false; updateBackgroundButtons(); }
});
$("auto-background-button").addEventListener("click", async () => {
  try {
    const project = await projectAction("background", backgroundRequest());
    if (project) $("background-status").textContent = "Đang tự chọn và chuẩn bị video nền. Theo dõi tiến độ xử lý của dự án.";
  } catch (error) { toast(error.message, true); }
});

const subtitleStyleIds = ["font-size", "font-family", "text-color", "highlight-color", "subtitle-position", "margin-percent"];
function restoreSubtitleStyle(project) {
  const saved = { ...(project.last_render || {}), ...(project.subtitle_style || {}) };
  if (!saved) return;
  const controls = { font_size: "font-size", font_family: "font-family", text_color: "text-color", highlight_color: "highlight-color", position: "subtitle-position", margin_percent: "margin-percent" };
  $("countdown-enabled").checked = Boolean(saved.countdown);
  // Motion settings belong to the last render, not ASR/lyric timing.
  for (const [setting, id] of Object.entries({
    motion_intro: "motion-intro", motion_outro: "motion-outro",
    motion_transition: "motion-transition",
  })) {
    if (saved[setting] !== undefined) $(id).value = saved[setting];
  }
  for (const [key, id] of Object.entries(controls)) if (saved[key] !== undefined) $(id).value = saved[key];
  if (saved.resolution) $("resolution").value = saved.resolution;
  resizePreview();
}

function updateButtons() {
  const available = Boolean(state.project);
  const blocked = !available || isBusy();
  $("create-button").disabled = state.pending;
  $("project-select").disabled = state.pending;
  $("new-project").disabled = state.pending;
  $("transcribe-button").disabled = blocked;
  $("separate-button").disabled = blocked;
  const hasReference = Boolean(referenceText().trim());
  $("align-button").disabled = blocked || !hasReference;
  $("save-reference").disabled = blocked || !hasReference || !state.referenceDirty;
  $("smart-preview").disabled = blocked || state.dirty || !hasReference || !state.segments.length;
  $("smart-apply").disabled = blocked || state.dirty || !state.smartPreview
    || !smartSelectedRows().length;
  $("smart-undo").disabled = blocked || state.dirty || !state.project?.smart_sync?.can_undo;
  $("apply-reference").disabled = blocked || !hasReference || !state.segments.length;
  $("reference-allow-estimate").disabled = blocked || !hasReference || !state.segments.length;
  $("reference-lyrics").disabled = Boolean(isBusy());
  $("reference-file").disabled = Boolean(isBusy());
  $("timing-offset").disabled = blocked || !state.segments.length;
  $("apply-timing").disabled = blocked || !state.segments.length || !Number($("timing-offset").value);
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
  updateBackgroundButtons();
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

function updateProject(project, force = false, { preserveReference = false } = {}) {
  const changed = state.project?.id !== project.id;
  if (state.smartPreview && (
    state.smartPreview.projectId !== project.id
    || state.smartPreview.segmentKey !== JSON.stringify(project.segments || [])
    || state.smartPreview.referenceText !== (project.reference_lyrics?.text || "")
  )) state.smartPreview = null;
  if (!state.project?.files?.instrumental && project.files?.instrumental) $("export-mode").value = "instrumental";
  state.project = project;
  syncReference(project, { changed, preserveDraft: preserveReference });
  if (changed) restoreSubtitleStyle(project);
  updateBackgroundAttribution();
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
  renderSmartPanel();
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
    $("countdown-overlay").hidden = true;
    $("stage-empty").hidden = false;
    $("stage-lyrics").hidden = true;
    $("stage-empty").querySelector("p").textContent = state.project ? state.project.title : "Sân khấu đang chờ bài hát của bạn";
    $("stage-empty").querySelector("small").textContent = state.project ? "Nhấn tạo sub tự động hoặc thêm lời thủ công" : "Tải bài hát lên để bắt đầu một dự án mới";
    return;
  }
  $("stage-empty").hidden = true;
  $("stage-lyrics").hidden = false;
  const lines = previewLines();
  if (!lines.length) { $("countdown-overlay").hidden = true; return; }
  // Same three-second gap rule used by ASS exporter. No countdown over lyrics.
  let precedingEnd = 0;
  let countdownNumber = 0;
  if ($("countdown-enabled").checked) {
    for (const segment of lines) {
      if (segment.start - precedingEnd >= 3 - 1e-9 &&
          position >= segment.start - 3 && position < segment.start) {
        countdownNumber = Math.max(1, Math.min(3, Math.ceil(segment.start - position)));
        break;
      }
      precedingEnd = Math.max(precedingEnd, segment.end);
    }
  }
  $("countdown-overlay").hidden = !countdownNumber;
  if (countdownNumber) {
    const litNotes = 4 - countdownNumber;
    $("countdown-overlay").querySelectorAll(".countdown-note").forEach((note, index) => {
      note.classList.toggle("lit", index < litNotes);
      note.classList.toggle("fresh", index === litNotes - 1);
    });
  }
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
    state.pending = true; updateButtons();
    await saveLyrics(false);
    const project = await api(`/api/projects/${encodeURIComponent(state.project.id)}/${action}`, { method: "POST", body });
    if (action === "align" && referenceText() === body.text) state.referenceDirty = false;
    updateProject(project);
    return project;
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; updateButtons(); updateDownloads(); }
}

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.pending || !$("source").files.length) return;
  try {
    const automaticBackground = $("background-auto").checked ? backgroundRequest() : null;
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
    updateProject(project, true, { preserveReference: true });
    if (state.referenceDirty && referenceText().trim()) await saveReference(false);
    if (automaticBackground) {
      const withBackground = await api(`/api/projects/${encodeURIComponent(state.project.id)}/background`, { method: "POST", body: automaticBackground });
      updateProject(withBackground);
      toast("Đã tạo dự án. Đang tự chọn nền; chờ xử lý xong trước khi căn lời hoặc xuất video.");
      return;
    }
    toast(referenceText().trim() ? "Đã tạo dự án và lưu lời chuẩn. Tiếp theo, nhấn Căn lời theo giọng hát." : "Đã tạo dự án. Nhập TXT để căn lời chuẩn hoặc dùng Tạo lời & canh thời gian.");
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; $("create-button").replaceChildren(document.createTextNode("Tạo dự án "), node("span", "", "↗")); updateButtons(); updateDownloads(); }
});

$("project-select").addEventListener("change", async (event) => {
  const id = event.target.value;
  if (!id || id === state.project?.id) return;
  try {
    state.pending = true; updateButtons();
    await saveLyrics(false);
    await saveReference(false);
    const project = await api(`/api/projects/${encodeURIComponent(id)}`);
    state.generation += 1;
    state.dirty = false;
    audio.pause();
    $("audio-mode").value = "original";
    $("export-mode").value = project.files?.instrumental ? "instrumental" : "original";
    updateProject(project, true);
  } catch (error) { toast(error.message, true); updateProjectSelect(); }
  finally { state.pending = false; updateButtons(); updateDownloads(); }
});

$("new-project").addEventListener("click", async () => {
  try {
    state.pending = true; updateButtons();
    await saveLyrics(false);
    await saveReference(false);
    clearTimeout(state.poll);
    state.generation += 1; state.project = null; state.segments = []; state.dirty = false; state.smartPreview = null; renderSmartPanel();
    audio.pause(); audio.removeAttribute("src"); audio.load();
    backgroundVideo.pause(); backgroundVideo.removeAttribute("src"); backgroundVideo.load();
    backgroundVideo.hidden = true; $("background-image").hidden = true;
    $("project-name").textContent = "Chưa chọn bài hát";
    $("stage-badge").textContent = "YOUR MUSIC. YOUR STAGE.";
    $("result-panel").hidden = true;
    $("downloads").hidden = true;
    $("upload-form").reset();
    $("reference-lyrics").value = ""; $("reference-file").value = "";
    $("reference-file-name").textContent = "UTF-8 / UTF-16 · tối đa 200 KB";
    state.referenceDirty = false;
    $("timing-offset").value = "0";
    updateReferenceStatus();
    updateBackgroundAttribution();
    resetFileLabels();
    updateProjectSelect(); renderEditor(); renderPreview(); updateProgress(); updateButtons();
    $("title").focus();
  } catch (error) { toast(error.message, true); }
  finally { state.pending = false; updateButtons(); updateDownloads(); }
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
  const margin = Number($("margin-percent").value);
  if (!Number.isFinite(margin) || margin < 5 || margin > 25) throw new Error("Lề chữ cần nằm trong khoảng 5–25%.");
  return { resolution: $("resolution").value, font_size: Math.round(fontSize), font_family: $("font-family").value,
    text_color: $("text-color").value, highlight_color: $("highlight-color").value,
    position: $("subtitle-position").value, margin_percent: margin,
    countdown: $("countdown-enabled").checked };
}
$("render-button").addEventListener("click", () => {
  try {
    if ($("export-mode").value === "instrumental" && !state.project?.files?.instrumental) throw new Error("Hãy tách vocal hoặc thêm nhạc beat trước khi xuất chế độ karaoke.");
    projectAction("render", {
      ...exportSettings(),
      audio_mode: $("export-mode").value,
      motion_intro: $("motion-intro").value,
      motion_outro: $("motion-outro").value,
      motion_transition: $("motion-transition").value,
      motion_title: $("motion-title").value.trim(),
    });
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
  const stage = $("stage");
  const width = stage.clientWidth;
  const size = Number($("font-size").value) || 54;
  const margin = Math.max(5, Math.min(25, Number($("margin-percent").value) || 9));
  const position = $("subtitle-position").value;
  $("current-lyric").style.fontSize = `${Math.max(1, width * size / 1920)}px`;
  $("current-lyric").style.fontFamily = $("font-family").value;
  stage.style.setProperty("--lyric-text", $("text-color").value);
  stage.style.setProperty("--lyric-highlight", $("highlight-color").value);
  const lyrics = $("stage-lyrics");
  const horizontalMargin = width * 60 / ($("resolution").value === "720p" ? 1280 : 1920);
  lyrics.style.paddingLeft = `${horizontalMargin}px`;
  lyrics.style.paddingRight = `${horizontalMargin}px`;
  lyrics.style.paddingTop = `${stage.clientHeight * margin / 100}px`;
  lyrics.style.paddingBottom = `${stage.clientHeight * margin / 100}px`;
  lyrics.style.justifyContent = position === "top" ? "flex-start" : position === "center" ? "center" : "flex-end";
  // Put the notes just above the actual lyric baseline at any subtitle position.
  const overlay = $("countdown-overlay");
  const offset = Math.max(36, $("current-lyric").getBoundingClientRect().height + 16);
  overlay.style.bottom = position === "bottom" ? `calc(${margin}% + ${offset}px)` : "auto";
  overlay.style.top = position === "top" ? `calc(${margin}% + ${offset}px)`
    : position === "center" ? "calc(50% - 85px)" : "auto";
}
window.addEventListener("resize", resizePreview);
document.addEventListener("fullscreenchange", resizePreview);
for (const id of subtitleStyleIds) $(id).addEventListener("input", resizePreview);
$("countdown-enabled").addEventListener("change", renderPreview);
$("resolution").addEventListener("change", resizePreview);
window.addEventListener("beforeunload", (event) => { if (state.dirty || state.referenceDirty) { event.preventDefault(); event.returnValue = ""; } });

async function initialize() {
  resizePreview(); renderEditor(); updateReferenceStatus(); updateBackgroundMode(); renderSmartPanel(); updateButtons();
  const results = await Promise.allSettled([api("/api/system"), refreshProjects(), loadBackgroundProviders()]);
  if (results[0].status === "fulfilled") {
    const info = results[0].value;
    $("gpu-status").textContent = info.cuda ? `CUDA · ${info.gpu || "NVIDIA GPU"}` : info.torch ? "CPU · chưa có CUDA" : "Chưa cài AI · xem hướng dẫn";
    $("gpu-status").title = info.model_cache ? `Model cache: ${info.model_cache}` : "Chọn CUDA khi đã cài bản PyTorch hỗ trợ NVIDIA.";
    if (!info.ffmpeg || !info.ffprobe) toast("Chưa tìm thấy FFmpeg / FFprobe. Hãy chạy bộ cài trước khi tạo dự án.", true);
  } else { $("gpu-status").textContent = "Chưa kết nối máy chủ"; toast(`Không kiểm tra được hệ thống: ${results[0].reason.message}`, true); }
  if (results[1].status === "fulfilled" && state.projects.length === 0) showGuide(true);
  if (results[1].status === "rejected") toast(`Không tải được dự án: ${results[1].reason.message}`, true);
  if (results[2].status === "rejected") $("background-status").textContent = `Chưa tải được danh sách kho video: ${results[2].reason.message}`;
}
initialize();
