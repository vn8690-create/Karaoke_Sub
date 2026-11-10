# NVS Karaoke Studio PRO – bản giao diện (frontend) v0.1

Dự án mới hoàn toàn (không đụng tới giao diện cũ). React + TypeScript + Tailwind v4 + Zustand + Vite. Tiếng Việt, có khung i18n.

## Chạy
```
npm install
npm run dev        # mở http://localhost:5173 bằng Chrome/Edge
npm run typecheck  # kiểm tra kiểu
npm test           # 5 test cho timeline store
npm run build      # typecheck + build production
```
Phím tắt: Space phát/dừng · S cắt clip tại playhead · Delete xoá · Ctrl+Z/Ctrl+Y · Ctrl+S lưu. Chuột phải clip: menu cắt/xoá.

## Chức năng THẬT (đã có code chạy)
- Bố cục 5 khu vực, kéo đổi kích thước panel (trái, phải, timeline).
- Nhập file thật (âm thanh/ảnh/video theo khả năng giải mã của trình duyệt); sóng âm thật cho file âm thanh.
- Timeline: kéo thả clip, kéo từ thư viện vào track, đổi track cùng loại, kéo mép để đổi độ dài, cắt, xoá, snap vào playhead/mép clip, khoá/ẩn/tắt tiếng track, zoom, kéo playhead, undo/redo.
- Preview: ảnh nền, chữ Karaoke tô màu theo tiến độ (từ clip lời), tỉ lệ 16:9/9:16/1:1/4:3, lưới, vùng an toàn, toàn màn hình, phát nhạc đồng bộ playhead, bước từng khung.
- Inspector: sửa vị trí, tỉ lệ, độ mờ, thời gian, nội dung lời của clip đang chọn.
- Lưu/Mở cấu trúc dự án (.nvs.json, không kèm file media). Chỉ số GPU/CPU/RAM do trình duyệt báo.

## MOCK / CHƯA HỖ TRỢ (nút bấm sẽ báo rõ, không giả vờ)
Auto Karaoke Wizard, AI căn từng từ, Karaoke Editor theo từ, import/export LRC/ASS/SRT, thư viện hiệu ứng và template, Export Center và render, Settings, keyframe, speed curve, blend mode, font/viền/bóng nâng cao, preview video (chỉ phát được âm thanh của file video khi tách riêng), proxy preview, đo VRAM thực, đóng gói Tauri 2.
Dữ liệu mẫu: 4 dòng lời ghi **[MOCK]** trên track lời.
Chưa kiểm chứng: chưa được mở trong trình duyệt thật ở môi trường dựng, mới qua typecheck, test và build.
