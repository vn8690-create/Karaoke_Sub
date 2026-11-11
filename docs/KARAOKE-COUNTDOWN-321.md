# Đếm ngược 3 · 2 · 1 trước câu hát

Tính năng trong giao diện Karaoke Studio gốc tại http://127.0.0.1:8776/.

1. Mở bài hát đã có mốc thời gian.
2. Ở mục **Xuất thành phẩm**, bật **🎤 Đếm ngược 3 · 2 · 1 trước câu hát**.
3. Phát/nghe thử tại **KARAOKE PREVIEW**. Khi sắp vào một câu sau khoảng trống đủ 3 giây, giữa sân khấu sẽ xuất hiện **3 → 2 → 1**.
4. Chọn **Xuất video karaoke** để đưa countdown vào MP4, hoặc **Xuất sub ASS / SRT / LRC** để đưa countdown vào ASS. SRT và LRC vẫn chỉ chứa lời bài hát.

## Quy tắc và giới hạn

- Chỉ đếm nếu có ít nhất **3 giây** từ cuối câu trước tới đầu câu kế tiếp. Đếm ngay trong **3 giây cuối** trước khi vào câu mới. Câu đầu bài cũng được đếm nếu bắt đầu từ giây 3 trở đi.
- Không chen số giữa các câu sát nhau, không đổi thời gian từng từ.
- Mặc định **tắt**. Tùy chọn xuất được lưu trong thiết lập dự án. Bật/tắt sau khi đã xuất MP4 thì cần xuất lại.
- Countdown là hình ảnh, không có tiếng bíp, không thay đổi audio.
- Các đoạn nhạc không có câu kế tiếp sẽ không có đếm ngược.
- Bản **ASS/MP4** hiển thị countdown; **SRT/LRC** không.
