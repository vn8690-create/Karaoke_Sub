# NVS Karaoke Studio PRO (frontend)

React + TypeScript + Tailwind v4 + Zustand + Vite. Giao diện tiếng Việt, có khung i18n. Nằm trong thư mục `nvs_studio/` để không đụng `frontend/`, `backend/`, `local_studio/`.

```
npm ci
npm run dev        # http://localhost:5173 ; /api được proxy tới 127.0.0.1:8776 (local_studio)
npm run typecheck && npm test && npm run build
node e2e/e2e.mjs   # kiểm thử trình duyệt thật (xem e2e/e2e.mjs để biết cách cài playwright-core)
```
Chi tiết Karaoke Editor/Wizard: `docs/KARAOKE_EDITOR.md`. Kiến trúc: `ARCHITECTURE.md`. Bàn giao: `CODEX_HANDOFF.md`, `TODO_BACKEND.md`.

## Thật / MOCK
**Thật:** layout, timeline (kéo thả, cắt, snap, undo/redo), nhập nhạc + sóng âm, Karaoke Editor (kéo mép từng từ trên waveform, phím tinh chỉnh, đánh dấu mép bằng phím M, nghe thử câu, offset, undo/redo riêng), nhập/xuất LRC·Enhanced LRC·SRT·ASS, 6 hiệu ứng chữ trong preview, Wizard + client API local_studio (đã test với máy chủ giả).
**MOCK:** engine "MOCK" trong Wizard (tiến trình và kết quả giả lập, luôn có nhãn), dữ liệu mẫu `[MOCK]`.
**Chưa làm:** render/xuất video, preview khung hình video, thư viện hiệu ứng/template, Tauri 2, ESLint, nối với backend thật (chưa chạy thử).
