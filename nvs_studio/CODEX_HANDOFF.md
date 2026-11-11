# Bàn giao
1. `npm ci && npm run typecheck && npm test && npm run build` phải xanh (hiện 37 test đơn vị). `node e2e/e2e.mjs` 34 kiểm tra trình duyệt.
2. Đọc `docs/KARAOKE_EDITOR.md` (dữ liệu, phím, API đã dùng, API còn thiếu, giới hạn).
3. Không sửa `backend/`, `local_studio/`, `frontend/`: người khác phụ trách render, FFmpeg, kiểm tra MP4, backup ZIP.
4. Việc cần phối hợp backend: danh sách "API còn thiếu" trong tài liệu trên. Chạy thử toàn bộ Wizard/lưu lời với backend thật (chưa làm).
5. Giữ nguyên `.nvs.json` (version 1) và hợp đồng trong `src/contracts.ts`; đổi thì nâng version.
6. Nút "Xuất video" và "Cài đặt" vẫn báo chưa hỗ trợ đúng ý, nối khi RenderAdapter sẵn sàng.
