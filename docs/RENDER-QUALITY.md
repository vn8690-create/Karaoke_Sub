# Kiểm tra chất lượng MP4 sau khi xuất

Chức năng backend độc lập, không chỉnh giao diện Claude.

## Giải quyết vấn đề gì?

Với video dài, không nên báo "Hoàn thành" chỉ vì FFmpeg trả về exit code 0.
Bộ kiểm tra mới dùng FFprobe kiểm tra độ dài MP4, độ dài luồng hình,
codec H.264, độ phân giải, sự hiện diện của audio (nếu đã chọn nhạc),
codec AAC, thời lượng audio và lệch mốc bắt đầu audio/video.

- Sau mỗi lệnh render, kiểm tra MP4 trước khi đổi tên từ rendering.mp4 sang karaoke.mp4.
- Nếu file hỏng, thiếu phút, mất âm thanh hoặc sai độ phân giải:
  đánh dấu render lỗi và không công bố file kết quả mới.
- Người dùng có thể kiểm tra lại video đã xuất bằng:
  GET /api/projects/{project_id}/quality
  Trả JSON gồm ok, actual_duration, expected_duration, codecs, resolution và issues.

## Kiểm thử

    python -m unittest tests.local_studio.test_render_quality -v
    python -m unittest discover -s tests/local_studio -v

Chạy CI Windows và Linux trước khi merge.

## Giới hạn

Đây là kiểm tra metadata của MP4, không phải AI đánh giá nội dung. Nó không
phát hiện lời sai, tiếng méo, frame bị giật, hay chữ bị lệch màu. Để kiểm
chứng các vấn đề đó vẫn cần thử bằng mắt và tai trên video thật.
