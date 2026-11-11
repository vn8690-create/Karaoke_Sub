# Smart Lyrics Sync: dùng lời TXT chuẩn, giữ mốc hát từ Whisper

Dùng trên giao diện **Karaoke Sub gốc** tại http://127.0.0.1:8776/
(không phải trình React thử nghiệm /nvs/).

## Làm theo 6 bước

1. Mở dự án bài hát đã căn mốc thời gian bằng Whisper hoặc đã sửa tay.
2. Tại **Lời chuẩn từ TXT**, chọn file TXT UTF-8, nhìn lại nội dung và
   nhấn **Lưu lời chuẩn**. Cần nhập đủ các câu hát và các điệp khúc lặp,
   mỗi câu một dòng. Không thêm chữ không được hát vào lời.
3. Nhấn **✦ Smart Lyrics Sync · So khớp lời TXT**.
4. Xem bảng đối chiếu ở khung **Lời & thời gian**. Có thể nhấn ▶ để nghe
   tại đầu đoạn.
   - **Xanh:** thay chữ, giữ nguyên thời gian mỗi từ. Tự tích chọn, nhưng
     chỉ được áp dụng sau khi nhấn nút xác nhận.
   - **Vàng:** cần kiểm tra nội dung hoặc một vài mốc từ được ước lượng.
     Chỉ áp dụng nếu tự chọn ô kiểm và xác nhận.
   - **Đỏ:** AI bịa lời ở nhạc dạo, thiếu câu trong TXT, hoặc không thể
     ghép an toàn. Không tự xóa, không tự tạo mốc giả. Mở trình chỉnh
     từng từ ở phía dưới để xử lý thủ công.
5. Nhấn **Áp dụng câu đã chọn**, nghe lại các câu vàng. Không sửa câu
   đỏ trừ khi tự thao tác trong trình biên tập.
6. Nếu chưa đúng, nhấn **↶ Hoàn tác lần ghép gần nhất**. Chỉ thực hiện
   được nếu chưa sửa lời thủ công sau khi áp dụng.

## Khác với nút cũ

- **Căn lời theo giọng hát (AI)** dùng âm thanh và có thể tải model.
- **Áp dụng chữ TXT với thời gian cũ** cũ đòi số câu/từ trùng khớp,
  hoặc ước lượng cả dòng/bài.
- **Smart Lyrics Sync** đối chiếu từng câu và từ, bỏ qua những đoạn
  Whisper bịa ở nhạc dạo, chỉ thay một số câu bạn duyệt, ưu tiên
  giữ mốc đã căn chính xác.

## Quy tắc an toàn

- Smart Sync **không** tạo hoặc sửa chính bộ nhận diện Whisper.
- Kết quả ghép từ thêm/bớt có chữ và mốc **ước lượng**. Những mốc đó
  không được gọi là căn lời chuẩn theo giọng hát.
- Smart Sync không tự xóa lời mà nó không chắc chắn. Câu thiếu mốc
  thời gian cần chỉnh thủ công hoặc dùng AI.
- Server bảo vệ chống lưu từ một bản xem trước đã cũ: khi TXT/mốc
  đã thay, ứng dụng yêu cầu **xem trước lại**.
- Trước mỗi lượt áp dụng, backend lưu lời+mốc cũ vào:
  \`.local-data/projects/<project_id>/lyrics-before-smart-sync.json\`.
  Hoàn tác chỉ dành cho lượt áp dụng gần nhất và từ chối ghi đè nếu
  bạn chỉnh tay tiếp sau đó.
- Khi áp dụng lời mới, phụ đề/video cũ bị đánh dấu cần tạo lại.
  Xuất lại SRT/ASS/LRC/MP4 sau khi duyệt nội dung.

## Phạm vi và giới hạn thử nghiệm

Bản này giới hạn 240 câu cho mỗi lần ghép, không chạy AI và không
cần internet. Ghép chữ dùng độ tương đồng văn bản cùng thứ tự câu;
nếu lời TXT quá khác hoặc thiếu nhiều đoạn so với bản Whisper,
câu sẽ được đánh dấu đỏ. Đặc biệt hát luyến, điệp khúc lặp và
bài có nhiều nhạc dạo vẫn nên nghe kiểm tra bằng tai người.

GitHub CI kiểm tra API và trình duyệt với dữ liệu âm thanh giả.
**Chưa bảo đảm độ chính xác của mọi bài hát thực tế**.
