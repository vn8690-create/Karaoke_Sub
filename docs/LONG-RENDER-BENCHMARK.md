# Kiểm thử render video dài 7–10 phút trên Windows

Đây là **benchmark FFmpeg thực tế**, không liên quan UI Claude và không cần model AI.
Chương trình tạo nhạc tone giả lập, một dòng karaoke và video nền test ngắn;
sau đó xuất MP4 bằng đúng renderer Local Studio rồi dùng FFprobe kiểm tra thành phẩm.

## Chạy từ thư mục gốc Karaoke_Sub

Thử nhanh 15 giây (720p):

    python -m local_studio.benchmark --seconds 15

Thử vấn đề video dài 8 phút, 1080p, video nền lặp:

    python -m local_studio.benchmark --minutes 8 --resolution 1080p --loop-background --save benchmark-8min.mp4

Nếu đang dùng môi trường Windows được tạo bởi SETUP.bat, thay lệnh python
bằng python.exe trong venv của bạn, ví dụ:

    .venv-local\Scripts\python.exe -m local_studio.benchmark --minutes 8 --resolution 1080p --loop-background --save benchmark-8min.mp4

Lưu ý: không nên chạy 8 phút nếu còn ít dung lượng ổ đĩa; chương trình
cần tệp WAV trung gian và MP4 xuất ra.

## Kết quả

JSON báo:
- requested_seconds / actual_seconds: thời lượng yêu cầu và thực tế.
- elapsed_seconds: thời gian tạo MP4, KHÔNG gồm bước tạo media giả lập.
- relative_speed_x: tốc độ xử lý so với thời gian thực (1.0 nghĩa là 8 phút nhạc cần khoảng 8 phút render).
- resolution, has_audio, output_mb và file lưu nếu chọn --save.

Renderer hiện dùng libx264 (CPU). Benchmark **không phải** bài đo GPU/NVENC
hoặc VRAM GTX 1050 Ti, và không khẳng định tất cả hiệu ứng video dài đều ổn.
Nó kiểm tra engine FFmpeg local hiện có, đặc biệt là vấn đề MP4 bị mất phút,
mất tiếng, hoặc không tạo ra file.

## Kiểm thử CI

    python -m unittest tests.local_studio.test_benchmark -v

Bài test CI chỉ render các video khoảng 1.5 giây, không tốn 8 phút trên
mỗi lần commit. Bài kiểm thử dài phải chạy trực tiếp trên máy Windows thực tế.
