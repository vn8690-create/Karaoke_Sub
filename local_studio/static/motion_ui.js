"use strict";
// NVS Motion Engine UI. Deliberately isolated from audio, ASR and lyric editors.
(() => {
  const byId = (id) => document.getElementById(id);
  const panel = byId("motion-library");
  const frame = byId("motion-preview-frame");
  const wrap = byId("motion-preview-wrap");
  const status = byId("motion-engine-status");
  let metadata = null;
  async function loadMetadata() {
    try {
      const response = await fetch("/api/motion/presets", { credentials: "same-origin" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      metadata = await response.json();
      if (metadata.engine.installed) {
        status.textContent = "✓ HyperFrames + GSAP sẵn sàng. Intro/outro sẽ được dựng khi xuất video.";
        status.classList.add("ready");
      } else {
        const missing = [];
        if (!metadata.engine.node_ok) missing.push("Node.js 22+");
        if (!metadata.engine.hyperframes) missing.push("HyperFrames");
        if (!metadata.engine.gsap) missing.push("GSAP");
        status.textContent = "Cần cài " + missing.join(", ") +
          ". Preview CSS vẫn xem được, nhưng chưa thể xuất MP4 có Motion Engine.";
        status.classList.remove("ready");
      }
    } catch (error) {
      status.textContent = "Chưa kiểm tra được Motion Engine: " + error.message;
    }
  }
  function selected(kind) {
    const specific = byId(kind === "outro" ? "motion-outro" : "motion-intro").value;
    return specific === "none" ? "neon" : specific;
  }
  function currentTitle() {
    const name = byId("motion-title").value.trim() ||
      byId("project-name").textContent.trim();
    return name && name !== "Chưa chọn bài hát" ? name.slice(0, 100) : "KARAOKE STUDIO";
  }
  function showPreview() {
    const kind = byId("motion-preview-kind").value;
    const params = new URLSearchParams({
      kind,
      preset: selected(kind),
      transition: byId("motion-transition").value,
      title: currentTitle(),
      subtitle: "NVS KARAOKE",
      preview: "1",
    });
    frame.src = "/api/motion/preview?" + params.toString();
    wrap.hidden = false;
  }
  byId("motion-show-preview").addEventListener("click", showPreview);
  for (const id of ["motion-intro", "motion-outro", "motion-transition",
                    "motion-preview-kind", "motion-title"]) {
    byId(id).addEventListener("change", () => {
      if (!wrap.hidden) showPreview();
    });
  }
  panel.addEventListener("toggle", () => {
    if (panel.open && !metadata) loadMetadata();
  });
  loadMetadata();
})();
