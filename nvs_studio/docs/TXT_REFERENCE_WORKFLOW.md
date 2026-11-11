# File TXT chuẩn và mốc Karaoke

## Khi chữ trong Editor khác lời TXT nhưng thời gian đã chuẩn

1. Vào **Karaoke Editor** và nhấn **Nhập** để chọn file TXT UTF-8.
2. Nếu số câu và số từ của TXT khớp với lời đang có, Studio chỉ **thay nội dung chữ**. Mốc thời gian bắt đầu/kết thúc của từng từ được giữ nguyên.
3. Nếu số câu/từ không khớp, Studio **không ghi đè hay chia lại thời gian**. File TXT sẽ được giữ ở trạng thái 'TXT chuẩn' và có nút **TXT chuẩn → Căn lại**.
4. Nhấn nút này, trong Auto Karaoke Wizard chọn **Backend local_studio**, chọn đúng dự án/audio, kiểm tra ngôn ngữ rồi chạy. TXT đã được điền sẵn ở bước nhập lời.
5. Cũng có thể nhập file TXT trực tiếp tại bước **Ngôn ngữ & lời** trong Wizard. Khi đó backend dùng **stable-ts forced alignment (/align)** với chính văn bản TXT, không dùng lời tự nhận diện từ Whisper (/transcribe).
6. Nếu thành công, mở Editor, nghe lại, kiểm tra và nhấn **Lưu backend**.

## Lưu ý

- Nhập TXT vào Editor mà **chưa có dữ liệu căn thời gian** chỉ tạo mốc ước lượng để chỉnh thử. Đây KHÔNG phải kết quả căn theo giọng hát.
- Chỉ xóa nhãn như [Intro], [Verse], [Chorus], [sound] và hướng dẫn trong dấu ngoặc vuông; chữ gốc có dấu được bảo toàn.
- Khi backend trả chữ khác TXT (kể cả khác dấu), frontend báo lỗi và không đẩy nội dung khác vào Editor.
- Căn lời chuẩn cần model **stable-ts** và đúng bản thu âm. Nhạc khác phiên bản hoặc lyrics bị thiếu điệp khúc có thể thất bại. Khi thất bại, hãy giữ bản lyrics đang có và kiểm tra lại file.
- File Nhật có thể cần kiểm tra cách tách từ. Không chia lại mốc chính xác theo kiểu chia đều nếu số từ không khớp.
- Những chức năng này chỉ được test logic UI/CI; độ chính xác căn lời trên bài hát thật phải được thử tại máy Windows.
