# Chạy thử NVS Karaoke Studio PRO với backend Windows thật

Bản này không sử dụng API key và không cần cloud. Backend Python chạy tại 127.0.0.1:8776; frontend React có thể chạy ở chế độ phát triển (Vite proxy) hoặc bản build production cùng cổng.

## Cách 1: Một cửa sổ backend (khuyên dùng sau khi đã build)

Từ thư mục gốc Karaoke_Sub trong PowerShell:

    cd nvs_studio
    npm ci
    npm run build
    cd ..
    .\windows\START.bat

Mở trình duyệt tới:

    http://127.0.0.1:8776/nvs/

Nếu lần đầu chưa thiết lập Python và FFmpeg, chạy windows\SETUP.bat trước. Cần Node.js 22 hoặc mới hơn để build frontend; bản build đã tạo sẽ chạy từ Python mà không cần Vite chạy riêng.

## Cách 2: Live development

Cửa sổ số 1 (trong thư mục gốc Karaoke_Sub):

    .\windows\START.bat

Cửa sổ số 2:

    cd nvs_studio
    npm ci
    npm run dev

Mở địa chỉ Vite hiển thị trong terminal (thường http://localhost:5173).
Vite proxy cùng origin cho /api, không cần CORS mở công khai.

## Kiểm thử thủ công (không cần AI)

1. Nhấn Auto Karaoke → chọn **Backend local_studio**. Trạng thái phải là "đã kết nối".
2. Chọn một file MP3/WAV, nhấn **Tạo dự án từ file nhạc**.
3. Chọn dự án mới và nhấn **Mở Editor không chạy AI**.
4. Trong Karaoke Editor, bấm **Nhập** và chọn LRC/SRT/TXT có thời gian nằm trong độ dài bài hát.
5. Bấm **Lưu backend**. Mở lại dự án từ Wizard để xác nhận lời không mất.
6. Bấm **Xuất video**, chọn **Nhạc gốc** và 720p cho lần test đầu, nhấn **Xuất MP4**.
7. Đợi trạng thái backend báo hoàn thành và kiểm tra chất lượng. Nhấn **Tải MP4**.
8. Có thể tải ASS/SRT/LRC và ZIP sao lưu dự án.

Lưu ý: nếu nhập TXT không mốc thời gian, ứng dụng chỉ chia thời gian theo ước lượng; cần chỉnh chính xác trước khi xuất. Không hiển thị kết quả MOCK như AI thật.

## Auto Karaoke AI thật

Trong Wizard, chọn **Backend**, một dự án có audio, ngôn ngữ vi/en/ja/auto và lời chuẩn (nếu có). Gửi lời chuẩn gọi stable-ts; để trống gọi Whisper. Lần đầu có thể tải model. GPU GTX 1050 Ti 4GB có thể thiếu VRAM với model lớn hoặc bước tách giọng; sử dụng CPU hoặc model nhỏ khi có lỗi bộ nhớ. AI riêng chưa được CI kiểm thử vì phải tải model và cần giọng hát thật.

## Hạn chế đã biết

- Hiệu ứng canvas nâng cao (glow, pop, bounce, type, fade) **chưa render vào MP4**. Backend ASS mới dùng tô quét từ và các màu/font cơ bản.
- Chưa có Tauri/installer Windows, chưa có preview video động trong editor.
- Chức năng hủy render đã có; hủy trong Wizard hiện mới dừng theo dõi, chưa ngắt model ASR/align đang chạy trên backend.
- Bản frontend cần build trước nếu muốn truy cập qua /nvs/. Nếu 404, kiểm tra có nvs_studio/dist.
- Trình duyệt khi mở file media phải có bộ giải mã hỗ trợ; backend vẫn cần FFmpeg.

## Smoke tự động (GitHub Actions)

File nvs_studio/tests/real-backend.test.ts dùng WAV 2 giây tự tạo, gọi FastAPI thật, upload file, lưu lời, xuất SRT/ASS/LRC, MP4 720p, QC và ZIP sao lưu.
GitHub Actions workflow: .github/workflows/nvs-real-backend.yml.
Đây là thử nghiệm tích hợp không dùng AI. Kết quả video 7–10 phút phải thử thêm trên máy đích.
