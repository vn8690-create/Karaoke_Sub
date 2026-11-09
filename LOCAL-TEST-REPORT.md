# Báo cáo kiểm thử Local Studio

Ngày kiểm thử: **2026-11-09**. Nguồn upstream: `d59b5bf3bd05a434563e38bb8bd18ee856cc4ac6`.

## Đã xác minh

- **GitHub Actions trên Windows và Linux đều đạt**: [run kiểm thử](https://github.com/vn8690-create/Karaoke_Sub/actions/runs/42636885984), gồm API, xuất video bằng FFmpeg thật và kiểm tra cú pháp Windows PowerShell. Không tải model AI trong CI.
- **16 bài unittest đạt** với `python -m unittest discover -s tests/local_studio -v`.
- API: nhập file, lưu dự án, tải file, sửa lời/thời gian, chặn timeline sai, chặn sửa khi đang xử lý, lưu lỗi và cho chạy lại, xóa export cũ sau khi sửa lời.
- Phụ đề: UTF-8 tiếng Việt; ASS chạy màu theo từ, giữ khoảng nghỉ giữa các từ, xử lý làm tròn mốc thời gian; SRT và LRC.
- **FFmpeg thật**: MP4 720p có tiếng gốc, không tiếng, nền video ngắn lặp đủ bài, nền ảnh PNG; đường dẫn có dấu tiếng Việt và dấu nháy. Kiểm tra stream và thời lượng bằng ffprobe.
- **Whisper tiny thật trên CPU**: nhận diện mẫu tiếng Anh JFK 11 giây từ bộ fixture công khai của OpenAI Whisper, cho ra 22 từ có mốc thời gian. Có hồi quy cho timestamp chồng giữa các câu và timestamp vượt độ dài audio.
- **Demucs htdemucs thật trên CPU**: tách mẫu 5 giây thành hai WAV vocal/instrumental, kiểm tra được thời lượng bằng ffprobe.
- **Trình duyệt Chromium/Playwright**: upload file, gọi Whisper và Demucs thật qua UI, sửa/lưu từ, Play, bật/tắt Mute, chuyển nhạc instrumental, xuất MP4 720p, tải MP4 và SRT, mở lại dự án. Không có lỗi JavaScript. MP4 tải từ trình duyệt có video 1280×720 + audio, dài 11 giây.
- Giao diện ở viewport desktop 1440 px và mobile 390 px; có kiểm tra không tràn ngang trang.
- Script Windows: phân tích cú pháp bằng PowerShell 7 thật trên Linux; kiểm tra helper truyền mã lỗi lệnh và đường dẫn cache.
- Bộ thư viện `requirements-local.txt` đã cài được và chạy suy luận thật trên Python 3.12/Linux với PyTorch/torchaudio 2.5.1 CPU. Bộ cài Windows chọn Python 3.11 và wheel CUDA 12.1 nếu có NVIDIA.

## Giới hạn còn lại

Suy luận AI và kiểm thử trình duyệt được chạy trên **Linux CPU**; bộ unittest cũng đã qua trên **Windows runner** của GitHub Actions, cùng kiểm tra cú pháp PowerShell. Chưa chạy trọn bộ cài trên PC Windows của người dùng, GPU RTX 3060 hoặc CUDA. Script `windows/CHECK.bat` kiểm tra các điều kiện đó trên máy thật. Không khẳng định tốc độ/VRAM hay chất lượng nhận diện lời hát tiếng Việt dựa trên mẫu tiếng Anh ngắn; cần nghe và rà lại từng bài trước khi xuất.

Các bài unittest dùng media tổng hợp và mock ASR ở lớp API để ổn định; phần suy luận Whisper/Demucs thật ở trên đã chạy riêng, không bị thay bằng mock. CI mẫu không tải model nhiều GB. Không đưa model, media thử hoặc dữ liệu người dùng vào repo.
