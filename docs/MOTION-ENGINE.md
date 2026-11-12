# Motion Engine (HyperFrames + GSAP) cho Karaoke Studio

## Phạm vi

Module **tùy chọn** ở `motion_engine/`, hoạt động độc lập với Whisper, Demucs,
Smart Lyrics Sync, thời gian từng từ và bộ dựng phụ đề ASS hiện tại.

- **4 preset:** Neon Pulse, Cinema Gold, Minimal Clean, Retro Wave
- **3 chuyển cảnh:** Fade, Wipe Left, Smooth Left
- **Intro & Outro:** mỗi clip 3 giây (được dựng bằng HyperFrames CLI + GSAP timeline)
- **Preview:** xem intro, outro và mô phỏng chuyển cảnh ngay trong giao diện Local Studio
- **Xuất video:** giữ pipeline FFmpeg cũ để dựng bài hát, sau đó ghép clip intro/outro
  bằng `xfade`, giữ âm thanh bài hát và dịch âm thanh theo đúng khoảng intro
- **Trạng thái mặc định:** tắt, không cài npm vẫn dùng karaoke bình thường

## Cài tùy chọn trên Windows

1. Cài **Node.js 22 trở lên** và đảm bảo `node --version` hiển thị đúng.
2. Cài FFmpeg như hướng dẫn Karaoke Studio hiện tại.
3. Mở **PowerShell** trong thư mục Karaoke_Sub:
   ```powershell
   Set-Location .\motion_engine
   npm install
   Set-Location ..
   .\windows\START.bat
   ```
4. Mở `http://127.0.0.1:8776/`. Vào **Xuất thành phẩm → MOTION ENGINE**.
5. Chọn Intro và/hoặc Outro, chọn chuyển cảnh. Có thể bấm **Xem hiệu ứng** trước.
6. Khi trạng thái hiện **HyperFrames + GSAP sẵn sàng**, bấm **Xuất video karaoke**.

**Khuyến cáo:** HyperFrames có yêu cầu Node.js 22+, Chromium và FFmpeg.
Các preset ở đây chạy render một worker để tránh tranh bộ nhớ với GPU GTX 1050 Ti;
nếu thiếu thư viện chỉ phần xuất Motion bị chặn với thông báo cụ thể, không mất dự án.

## Cấu trúc

- `motion_engine/core.py`: preset, dựng HTML composition và gọi binary cục bộ
  `hyperframes` (không tự download khi bấm nút).
- `motion_engine/compositor.py`: FFmpeg xfade để ghép MP4 đã xuất.
- `local_studio/app.py`: endpoint API presets, preview, GSAP nội bộ, và render tùy chọn.
- `local_studio/static/motion_ui.js`: hiển thị UI mà không can thiệp script karaoke.
- `motion_engine/package.json`: phụ thuộc cố định CLI và GSAP, chỉ cài khi lựa chọn.

Ví dụ: intro 3s + bài 60s + outro 3s, hai chuyển cảnh 0,55s:
tổng video **64,90 giây**. Âm thanh bài hát bắt đầu ở giây 2,45 khi màn
intro chuyển sang bài chính; vị trí từng từ so với audio gốc vẫn giữ y nguyên.

## Phân biệt preview và export

Preview mở trong khung 16:9, dùng animation CSS khi chưa cài npm. Nếu đã cài
GSAP thì timeline có thể phát trực tiếp. **Preview chỉ cho biết phong cách**,
còn chuyển cảnh cuối cùng được dựng bởi FFmpeg, nên xuất thử bản ngắn trước
khi làm video dài.

Các preset chỉ gồm mã nguồn mới của dự án Karaoke, không sao chép toàn bộ repo
HyperFrames; sử dụng CLI `hyperframes` chính thức và JS `gsap` từ npm.
Không có nhạc hoặc ảnh bên thứ ba được đi kèm.

## Bản quyền / đường dẫn

- HyperFrames: https://github.com/heygen-com/hyperframes (Apache-2.0).
- GSAP: https://github.com/greensock/GSAP, package `gsap` trên npm.
- Xem điều khoản bản quyền của phiên bản trước khi đóng gói để bán.

## Kiểm thử

Kiểm thử mặc định kiểm tra API preview, escape HTML, schema, mô phỏng lệnh CLI,
và FFmpeg crossfade thật với âm thanh. Workflow Motion Engine riêng thực hiện
cài npm, validate composition và thử render HyperFrames khi CI có Chromium.

Không khẳng định đã kiểm thử trên GPU GTX 1050 Ti tại nhà, cũng không tự thay
đổi các chức năng Karaoke hiện có nếu Motion Engine tắt.
