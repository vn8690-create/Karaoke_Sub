# Bàn giao cho Codex
1. Chạy `npm install && npm run dev`, đọc `ARCHITECTURE.md` và `src/contracts.ts`.
2. Backend FastAPI (Python 3.12): cài adapter theo `contracts.ts`: `WhisperAdapter`, `KaraokeGenAdapter`, `RenderAdapter` (FFmpeg), `ProjectStorageAdapter`; giữ `MockAIAdapter` cho chế độ demo, ghi rõ MOCK.
3. Nối nút "Auto Karaoke" (TopBar) và "Xuất video": hiện chỉ gọi `notify` báo chưa hỗ trợ. Thay bằng wizard + hàng đợi job có hủy/progress.
4. Máy dev GTX 1050 Ti 4GB: bắt buộc CPU fallback, không giả định chạy được mọi model, hiển thị VRAM/RAM thật qua `SystemInfo`.
5. Không đổi định dạng `.nvs.json` mà không nâng `version`.
6. Mỗi bước phải giữ `npm run build` và `npm test` xanh.
