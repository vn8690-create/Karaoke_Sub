# Kiến trúc
- `src/store.ts`: một store Zustand duy nhất (tracks, clips, media, playhead, UI). Mọi thao tác sửa clip đi qua `commit()` để có undo/redo (tối đa 100 bước).
- `src/media.ts`: nhập file, tính sóng âm, `syncAudio` phát âm thanh theo playhead.
- `src/components/*`: TopBar, Library, Preview (canvas 2D), Inspector, Timeline. Component chỉ đọc/ghi store.
- `src/contracts.ts`: hợp đồng API cho backend (AIAdapter, RenderAdapter, ProjectStorageAdapter, SystemInfo). Frontend không nhúng API key.
- `src/i18n.ts`: bảng chuỗi tiếng Việt; thêm ngôn ngữ bằng cách thêm bảng.
Quy ước: thời gian tính bằng giây; clip có `off` (độ lệch trong file nguồn) để cắt clip âm thanh đúng đoạn.
Quyết định: tạm chạy như web app (Vite). Tauri 2 chưa đóng gói vì môi trường dựng không có Rust; thêm `src-tauri` sau mà không đổi mã giao diện.
