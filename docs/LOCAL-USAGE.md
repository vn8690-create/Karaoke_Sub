# Hướng dẫn sử dụng Karaoke Sub

Sau khi chạy `windows\START.bat`, nhấn **Hướng dẫn** ở đầu giao diện để xem lại cách dùng ngay trong ứng dụng. Trang này giải thích chi tiết từng thao tác.

## Làm nhanh bài karaoke đầu tiên

1. Chọn **bài hát có giọng ca sĩ**, thêm ảnh/video nền nếu muốn, rồi nhấn **Tạo dự án**.
2. Chọn **Tiếng Việt → Small · nhanh → Tự động · ưu tiên NVIDIA GPU**. Giữ dấu tích **Tách giọng hát trước khi nhận diện**, rồi nhấn **Tạo lời & canh thời gian**.
3. Chờ xử lý xong; nghe lại, mở **Chỉnh từng từ** để sửa chỗ sai, rồi nhấn **Lưu lời**.
4. Trong mục **Âm thanh video xuất**, chọn **Nhạc beat · không vocal**. Thử **720p · nhẹ hơn**, nhấn **Xuất video karaoke**, rồi **Tải MP4**.

**Tạo dự án chỉ nhập các file, chưa tạo sub hoặc video.** Bạn cần tiếp tục bước nhận diện lời và xuất thành phẩm.

Lần đầu, app cần tải model từ Internet. Bạn có thể thử một đoạn hát ngắn trước khi làm cả bài; AI vẫn cần được nghe và rà lại lời.

## 1. Mở đúng ứng dụng

Nhấp đúp `windows\START.bat` trong thư mục Karaoke_Sub đã cài. Giữ cửa sổ này mở trong lúc sử dụng; nhấn `Ctrl+C` để dừng app.

Địa chỉ mặc định là **http://127.0.0.1:8776**. Nếu cổng này bận, app tự chọn cổng khác và mở trình duyệt đến đúng địa chỉ. Khi cần mở thủ công, xem dòng **`Karaoke Sub:`** trong cửa sổ START. Cover Studio có thể tiếp tục chạy ở cổng 8765.

Nếu máy chưa được cài môi trường, xem [hướng dẫn cài Windows](../README-WINDOWS.md). Các lần sử dụng sau chỉ cần START, không cần chạy lại SETUP.

## 2. Nhập bài hát, nền và beat

Trong **Chọn bài hát**:

- Đặt **Tên dự án** để dễ tìm lại.
- Nhấn hoặc kéo file vào vùng **Thả bài hát vào đây**. Có thể dùng MP3, WAV, FLAC, M4A hoặc video có âm thanh như MP4. Để tạo lời tự động, file nguồn cần có tiếng hát; nhạc không lời không chứa lời để AI nhận diện.
- Chọn **Ảnh / video nền** nếu muốn ghép nền. Video ngắn sẽ được lặp đủ độ dài bài hát; tiếng của video nền không được đưa vào video xuất. Bỏ trống để dùng nền màu.
- Chọn **Nhạc beat có sẵn** nếu đã có bản instrumental. Dùng beat cùng phiên bản với bài gốc, cùng mốc bắt đầu và độ dài để lời không bị lệch. Nếu chưa có beat, bước tiếp theo có thể tách giọng từ bài gốc.
- Nhấn **Tạo dự án** và chờ file được nhập xong.

Chọn nền và beat **trước khi nhấn Tạo dự án**. Giao diện hiện tại chưa có chức năng thay hai file này trong dự án đã tạo; muốn đổi, tạo dự án mới với các file mong muốn.

## 3. Tạo sub và nhạc không giọng

Trong **Tạo sub tự động**, bắt đầu với cấu hình này cho bài tiếng Việt trên RTX 3060:

| Mục | Chọn gì trước tiên |
| --- | --- |
| Ngôn ngữ | **Tiếng Việt** |
| Model Whisper | **Small · nhanh** |
| Thiết bị xử lý | **Tự động · ưu tiên NVIDIA GPU** |
| Tách giọng hát trước khi nhận diện | Bật nếu muốn tạo beat từ bài gốc |

Nhấn **Tạo lời & canh thời gian**. Khi bật tách giọng, app dùng Demucs để tạo phần nhạc và giọng hát; Whisper nhận diện lời và mốc thời gian từng từ. Chờ trạng thái xử lý hoàn tất trước khi chỉnh lời hoặc xuất video.

Nếu đã nhập beat riêng, bạn có thể bỏ dấu tích tách giọng và chỉ nhận diện lời từ bài gốc. Nếu chỉ muốn lấy beat mà chưa tạo lời, dùng **Chỉ tách vocal / tạo nhạc beat**.

Lần đầu tải model có thể lâu tùy mạng. Giữ cửa sổ START mở và theo dõi thông báo tiến độ. Khi model đã lưu trên máy, các lần sau dùng lại cache.

Model `medium` có thể cho kết quả khác nhưng dùng nhiều VRAM hơn. Hãy thử `small` trước; nếu hết VRAM, chuyển xuống `base` hoặc chọn **CPU**. Nếu tự động dùng CPU dù có RTX 3060, chạy `windows\CHECK.bat` để kiểm tra CUDA và driver.

### Lời viết sẵn có [Intro], [Verse], [Chorus]

Lời bài hát có thể đi kèm cấu trúc và chỉ dẫn, ví dụ:

```text
[Intro]
[Sound of rain pouring, slow acoustic blues guitar]
[Verse 1]
Rót thêm một chén... chén này ta tự lau nước mắt
[Chorus]
Chén đắng nhân gian này, ta nếm đủ rồi người ơi!
```

Khi làm sub hát, bỏ những dòng chỉ dẫn trong ngoặc vuông như `[Verse 1]`, `[Chorus]`, `[Beat stops]` hoặc `[End]`; chỉ giữ những câu thực sự được hát. Đoạn intro chỉ có tiếng mưa/guitar thì không cần lời chạy trên màn hình. Dấu `...` là cách viết ngắt câu; thời gian kéo dài và khoảng nghỉ cần khớp giọng hát trong file nhạc.

Bản hiện tại **nhận diện lời từ âm thanh**, chưa có chức năng dán toàn bộ lời viết sẵn rồi tự căn thời gian theo bài. Dùng văn bản này để đối chiếu, sửa trong **Chỉnh từng từ** hoặc **Thêm câu** cho đoạn thiếu, rồi nghe và chỉnh thời gian. Không đưa nguyên dòng mô tả âm thanh vào câu hát.

## 4. Nghe, sửa lời và canh từng từ

Sau khi nhận diện xong, các câu xuất hiện trong **Lời & thời gian**:

1. Nhấn vào nội dung một câu để nghe từ vị trí đó.
2. Mở **Chỉnh từng từ** bên dưới câu.
3. Sửa từ nhận sai và mốc **BẮT ĐẦU (s)**, **KẾT THÚC (s)**. Đơn vị là giây; ví dụ `12.50` là 12 giây rưỡi.
4. Nghe lại rồi nhấn **Lưu lời**.

Thời gian kết thúc mỗi từ phải lớn hơn bắt đầu. Các từ và câu cần đi theo thứ tự, không chồng thời gian và không vượt độ dài bài hát. Ví dụ hợp lệ: từ đầu `1.20 → 1.65`, từ tiếp theo `1.80 → 2.30`.

Dùng **＋ Thêm câu** để nhập thủ công phần AI bỏ sót. Khi thêm câu, app chia đều thời gian cho các từ; đây là mốc ban đầu để bạn nghe và chỉnh lại. Có thể thêm/xóa từ trong câu hoặc dùng dấu **×** ở dòng câu để xóa câu.

Nhấn **Lưu lời** trước khi đóng trang. App cũng lưu lời đã chỉnh trước khi xuất, nhưng không tự lưu liên tục sau mỗi lần gõ. Sau khi thay lời, hãy xuất lại video/phụ đề để bản tải xuống khớp nội dung mới.

## 5. Hát thử và kiểm tra Mute

Ở khung **KARAOKE PREVIEW**, nhấn **▶** để phát; kéo thanh thời gian để nghe đoạn cần kiểm tra. Chữ đang hát đổi màu theo thời gian của từng từ.

| Chế độ nghe thử | Tác dụng |
| --- | --- |
| **Nghe bản gốc** | Nghe bài có giọng ca sĩ để đối chiếu lời |
| **Hát với nhạc beat** | Nghe instrumental đã tách hoặc beat đã nhập để bạn hát theo |
| **Không tiếng** | Xem lời chạy mà không phát âm thanh |
| **Mute** | Bật/tắt toàn bộ âm thanh nghe thử; không tách giọng ca sĩ |

Muốn giữ nhạc và bỏ giọng ca sĩ, dùng **Hát với nhạc beat** sau khi tách vocal hoặc nhập beat. AI tách giọng có thể vẫn để lại giọng bè hay một phần giọng hát.

Nhấn **⛶** để xem sân khấu toàn màn hình; nhấn `Esc` để thoát. Phím **Space** phát/tạm dừng và **M** bật/tắt Mute khi con trỏ không ở ô nhập, nút hoặc hộp chọn. Nếu phím chưa tác dụng, nhấn vùng trống của trang trước.

## 6. Xuất video và tải phụ đề

Trong **Xuất thành phẩm**:

1. Chọn **720p · nhẹ hơn** để thử nhanh hoặc **1080p · Full HD** cho bản hoàn chỉnh.
2. Chọn **Cỡ chữ**; có thể bắt đầu với `54`.
3. Chọn rõ **Âm thanh video xuất**:
   - **Bài hát gốc**: giữ tiếng hát và nhạc từ file nguồn.
   - **Nhạc beat · không vocal**: dùng instrumental để hát karaoke.
   - **Không âm thanh**: xuất video hoàn toàn không tiếng.
4. Nhấn **Xuất video karaoke**, chờ hoàn tất, rồi nhấn **Tải MP4** trong **Video đã xuất**.

**Mute và chế độ nghe thử không tự thay đổi âm thanh video xuất.** Ví dụ bạn đang nghe Mute nhưng xuất **Bài hát gốc** thì MP4 vẫn có tiếng. Muốn MP4 không tiếng, chọn **Không âm thanh** trong mục xuất.

Để chỉ lấy phụ đề, nhấn **Xuất sub ASS / SRT / LRC** rồi chọn file cần tải:

| File | Dùng khi nào |
| --- | --- |
| **MP4** | Video đã ghép nền, âm thanh đã chọn và chữ karaoke; mở bằng trình phát video thông thường |
| **ASS** | Phụ đề giữ hiệu ứng karaoke chạy màu theo từ cho phần mềm hỗ trợ ASS |
| **SRT** | Phụ đề theo câu; không giữ hiệu ứng chạy màu karaoke |
| **LRC** | Lời có thời gian theo dòng và từ; cách hiển thị tùy trình phát hỗ trợ |
| **Dự án JSON** | Thông tin dự án và lời có thời gian; không chứa file nhạc, nền hay video |

## Mở lại và sao lưu dự án

Lần sau chạy START, dùng hộp **DỰ ÁN CỦA BẠN** ở đầu trang để chọn bài đã làm. Nhấn **＋** bên cạnh để bắt đầu bài mới.

App lưu file và dữ liệu dự án trong **`.local-data/projects`** bên trong thư mục Karaoke_Sub, trừ khi bạn đã đặt thư mục dữ liệu riêng. Để chuyển máy hoặc sao lưu, giữ cả thư mục này. File JSON tải riêng không thay thế bản sao các file media; giao diện hiện chưa có nút nhập lại JSON.

Bạn không cần tài khoản dịch vụ cloud. Hãy giữ `.local-data` và `.venv-local` khi cập nhật mã nguồn để tiếp tục dùng dữ liệu và môi trường đã cài.

## Khi nút bị mờ hoặc xử lý chưa xong

| Tình huống | Cách xử lý |
| --- | --- |
| **Tạo lời & canh thời gian** bị mờ | Chọn file rồi nhấn **Tạo dự án**, hoặc chọn dự án đã lưu. Nếu đang xử lý, chờ tác vụ hoàn tất. |
| **Xuất video karaoke** bị mờ | Cần có lời trước: tạo lời tự động hoặc thêm câu thủ công. Nếu app đang bận, chờ xử lý xong. |
| Không chọn được nhạc beat | Nhấn **Chỉ tách vocal / tạo nhạc beat**, hoặc tạo dự án mới và nhập beat có sẵn. |
| **Lưu lời** bị mờ | Chưa có thay đổi cần lưu, chưa chọn dự án hoặc dự án đang xử lý. |
| Model đang tải lâu | Kiểm tra Internet, dung lượng trống và thông báo trong cửa sổ START; lần đầu cần tải trọng số model. |
| Báo hết VRAM | Giảm model từ `medium`/`large` xuống `small`/`base`, đóng ứng dụng chiếm GPU hoặc chọn CPU. |
| Nhận sai hoặc lệch lời | Chọn đúng ngôn ngữ, thử nhận diện sau tách giọng; nghe và sửa từng từ trước khi xuất. |
| Trang mở ra Cover Studio | Dùng bản Karaoke Sub mới và địa chỉ sau dòng **Karaoke Sub:** trong cửa sổ START; mặc định mới là cổng 8776. |

Các lỗi cài Python, FFmpeg hoặc CUDA được giải thích thêm trong [README-WINDOWS.md](../README-WINDOWS.md).
