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

## Bản sửa trùng cổng — 2026-11-10

- Đổi cổng ưu tiên sang **8776**, không dùng cổng 8765 của Cover Studio nữa. Nếu cổng ưu tiên bận, chọn và giữ một socket trống để tránh xung đột giữa lúc kiểm tra và khởi động server.
- Trình duyệt chỉ mở khi health check khớp cả mã ứng dụng và mã phiên khởi động. Phản hồi từ Cover Studio, app khác hoặc phiên cũ không làm trình duyệt mở nhầm.
- **23 bài unittest đạt**, gồm 7 hồi quy mới về trùng cổng, socket, health check và tiến trình Uvicorn thật.
- Kiểm thử Chromium với dịch vụ giả lập chiếm cổng 8776: Karaoke Sub chạy tại **8777**, tải đúng giao diện; dịch vụ giả lập vẫn trả lời bình thường. Không dừng tiến trình hoặc đóng ứng dụng đang chiếm cổng.

## Hướng dẫn trong ứng dụng — 2026-11-10

- Nút **Hướng dẫn** và liên kết **Lần đầu sử dụng?** mở mục hướng dẫn 6 bước ngay trong giao diện, dùng được khi không có mạng. Hướng dẫn tự hiện khi chưa có dự án.
- Chromium/Playwright đã kiểm tra mở/đóng, nút bắt đầu đưa con trỏ tới tên dự án, trạng thái `aria-expanded`, bàn phím Enter và phần hỏi đáp.
- Mở hướng dẫn không làm mất tên/file đang chọn hoặc lời chưa lưu. Đã thử tạo dự án, thêm câu thủ công và lưu lời sau khi mở/đóng hướng dẫn.
- Đã kiểm tra ở chiều rộng **1440, 390 và 320 px**, không tràn ngang trang hoặc khung hướng dẫn, không lỗi JavaScript. Các hướng dẫn không thay đổi luồng xử lý AI hay xuất video.


## Lời chuẩn, nguồn nền và sửa sub — 2026-11-10

- **66 bài unittest đạt**: thêm căn lời chuẩn, làm sạch nhãn đoạn, giữ đủ chữ/câu lặp, xử lý thất bại không thay thời gian cũ, dịch mốc và từ chối vượt bài, giữ beat riêng khi tách vocal, nguồn video và API settings.
- **Forced alignment thật bằng stable-ts trên CPU**: 22 từ trong ba câu; thêm 2 giây im lặng khiến mốc từ đầu đổi **0,32 → 2,32 giây**, trung vị các mốc dịch đúng 2 giây (khoảng 1,94–2,06). Model còn cảnh báo một từ cần nghe lại; kết quả không được coi là chính xác tuyệt đối.
- Cài toàn bộ `requirements-local.txt` trong môi trường Python sạch với PyTorch/torchaudio 2.5.1 CPU: **kiểm tra dependency tương thích đạt** và chạy lại forced alignment thật đạt. Không sử dụng phụ thuộc cloud của upstream.
- **Chromium/Playwright**: nhập TXT UTF-16 có BOM trước khi tạo dự án, tự chọn nền từ thư mục, tự lưu lời chuẩn, căn model thật, sửa mốc toàn bài, màu/font/vị trí, xuất MP4 thật và khôi phục thiết lập khi mở lại. Đã thử 1440/390/320 px, không tràn ngang, không lỗi JavaScript.
- **Nguồn online thật**: tìm bằng API Commons, tải video WebM có thông tin giấy phép, kiểm tra bằng ffprobe, gắn vào dự án và xuất MP4 bằng môi trường sạch. Đổi nền không làm mất lời; bản video cũ được bỏ khỏi danh sách tải để xuất lại với nền mới. Pexels được kiểm tra bằng dữ liệu/API mô phỏng; chưa kiểm tra key Pexels thật.
- Kiểm tra pixel MP4 xác nhận màu chạy tôn trọng mốc từng từ và khoảng nghỉ; landmark âm thanh sau mã hóa AAC lệch không quá 40 ms trong mẫu tổng hợp. Kiểm tra vị trí trên/dưới bằng pixel và giới hạn kiểu chữ chống chèn ASS.
- Windows UPDATE được kiểm tra cú pháp bằng PowerShell thật; các phép thử helper cập nhật/mã lỗi chạy trên Linux. Bộ cài không ép cài lại PyTorch và không thay dữ liệu/model đã có.

Các phép thử model thật dùng tiếng nói tiếng Anh trên Linux CPU, **chưa đo độ chính xác trên bản thu karaoke tiếng Việt của người dùng hoặc GPU RTX 3060**. Lời TXT phải khớp đúng phiên bản, đủ đoạn lặp; cần nghe lại từ kéo dài/không rõ. Nền online hiện dùng một clip lặp, chưa tự dựng nhiều cảnh theo nội dung bài hát.
