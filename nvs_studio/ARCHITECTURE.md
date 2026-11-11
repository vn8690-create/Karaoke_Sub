# Kiến trúc
- `src/store.ts`: store dự án/timeline (clips, media, playhead, UI). `src/karaokeStore.ts`: store lời Karaoke (lines, chọn, offset, kiểu chữ, undo/redo riêng).
- `src/karaoke.ts`: mô hình + phép sửa thuần. `src/formats.ts`: parser/exporter. `src/backend.ts`: client API local_studio. `src/adapters/`: `AIAdapter` (mock, backend).
- `src/components/`: TopBar, Library, Preview (canvas), Inspector (+ KaraokeStylePanel), Timeline, KaraokeEditor (canvas waveform + từ), Wizard, karaokeDraw (vẽ chữ Karaoke).
- `src/contracts.ts`: hợp đồng adapter dùng chung (AIAdapter, RenderAdapter, ProjectStorageAdapter, SystemInfo).
Quy ước: giây; clip có `off`; lời dùng thời gian dự án. Dev chạy web (Vite). Đóng gói Tauri 2 chưa làm.
