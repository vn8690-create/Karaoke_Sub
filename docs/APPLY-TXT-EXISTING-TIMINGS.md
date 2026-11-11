# Dùng lời TXT với mốc thời gian Karaoke đã có (không cần AI)

Áp dụng cho giao diện **Karaoke Sub** tại http://127.0.0.1:8776/
(thay vì NVS React tại /nvs/).

## Khi TXT đúng nhưng dòng chạy vẫn là lời Whisper sai

1. Chọn đúng dự án âm thanh ở đầu trang. Không cần tạo dự án mới.
2. Tại **Lời chuẩn từ TXT**, nhấn **Chọn file TXT** và kiểm tra chữ có dấu hiển thị đúng trong ô văn bản.
3. Nhấn **Lưu lời chuẩn**, sau đó bấm **Áp dụng chữ TXT với thời gian cũ**.
4. Nếu số câu và số từ bằng dữ liệu cũ, mọi mốc start/end cũ được giữ 100%, chỉ thay chữ. Không chạy Whisper, stable-ts, Demucs.
5. Nếu báo số câu/từ không khớp, có hai lựa chọn:
   - **Căn lời theo giọng hát (AI)** khi đã sửa xong cache model, để tạo mốc thời gian chính xác cho TXT.
   - Bật **Cho phép ước lượng lại mốc từ** rồi bấm Áp dụng một lần nữa. App dựa vào vùng hát đã có, phân bố lại thời gian chữ gần đúng, giữ các khoảng lặng khi có thể. **Đây là ước lượng, không phải kết quả AI.** Nghe kiểm tra từng câu trước khi xuất.
6. Xem chữ mới ở **Lời & thời gian** và preview. Tạo lại phụ đề/MP4 nếu đã xuất bản cũ.

App giữ một snapshot lời trước khi thay tại
\`.local-data/projects/<project_id>/lyrics-before-txt.json\`.
Không xóa dự án, không cài lại PyTorch, không xóa WAV/MP3.

### Hạn chế

- Nếu AI ban đầu nhận diện sai rất nhiều, ước lượng theo thời gian cũ có thể bị lệch, đặc biệt ở các đoạn lặp/điệp khúc, câu dài và những chỗ nhạc dạo.
- Khi mốc từng từ thực sự phải khớp từng âm tiết, chỉ forced alignment với TXT trên audio/vocal đúng phiên bản hoặc chỉnh tay mới có thể xác nhận.
- File TXT nên có **mỗi câu hát một dòng**, đủ cả điệp khúc lặp. Dòng [Intro], [Verse], [Chorus] và chỉ dẫn trong ngoặc vuông sẽ được bỏ tự động.
