# Hướng dẫn sử dụng Karaoke Sub

Sau khi chạy `windows\START.bat`, nhấn **Hướng dẫn** ở đầu giao diện để xem cách dùng ngay trong ứng dụng. Khi lời nhận diện sai, hãy dùng lời chuẩn từ TXT hoặc văn bản dán vào để căn theo giọng hát.

## Làm nhanh với lời chuẩn

1. Chọn **bài hát có giọng ca sĩ**. Có thể chọn ảnh/video có sẵn hoặc bật **Tự chọn video nền** từ thư mục/online, rồi nhấn **Tạo dự án**.
2. Trong **Lời chuẩn từ TXT**, nhấn **Chọn file TXT** hoặc dán toàn bộ lời đúng bài. Viết đủ các đoạn lặp theo đúng thứ tự trong bản nhạc.
3. Chọn **Tiếng Việt → Small · nhanh → Tự động · ưu tiên NVIDIA GPU**, giữ dấu tích **Tách giọng hát trước khi nhận diện**, rồi nhấn **Căn lời theo giọng hát**.
4. Chờ xong, nghe lại và mở **Chỉnh từng từ** để sửa những chỗ chưa khớp, rồi **Lưu lời**.
5. Chỉnh font, màu chữ, màu chạy karaoke và vị trí. Trong **Âm thanh video xuất**, chọn **Nhạc beat · không vocal**. Thử **720p · nhẹ hơn**, nhấn **Xuất video karaoke**, rồi **Tải MP4**.

**Tạo dự án chỉ nhập file, chưa tạo sub hoặc video.** Lần đầu có thể cần tải model từ Internet. Việc căn lời dùng văn bản bạn cung cấp để tìm thời điểm từng từ trong âm thanh, không chia đều lời theo độ dài cả bài. Kết quả vẫn cần nghe và rà lại trước khi xuất.

Nếu đã cài bản cũ, dừng START, cập nhật mã rồi chạy **`windows\UPDATE.bat`** một lần để thêm thư viện căn lời. Sau đó chạy START và nhấn **Ctrl+F5**; không cần SETUP lại nếu môi trường cũ đang hoạt động. Xem [cách cập nhật trên Windows](../README-WINDOWS.md#cập-nhật-bản-đã-cài-để-dùng-lời-txt).

## 1. Mở đúng ứng dụng

Nhấp đúp `windows\START.bat` trong thư mục Karaoke_Sub đã cài. Giữ cửa sổ này mở trong lúc sử dụng; nhấn `Ctrl+C` để dừng app.

Địa chỉ mặc định là **http://127.0.0.1:8776**. Nếu cổng này bận, app tự chọn cổng khác và mở trình duyệt đến đúng địa chỉ. Khi cần mở thủ công, xem dòng **`Karaoke Sub:`** trong cửa sổ START. Cover Studio có thể tiếp tục chạy ở cổng 8765.

Nếu máy chưa được cài môi trường, xem [hướng dẫn cài Windows](../README-WINDOWS.md). Các lần sử dụng sau chỉ cần START.

## 2. Nhập bài hát, nền và beat

Trong **Chọn bài hát**:

- Đặt **Tên dự án** để dễ tìm lại.
- Nhấn hoặc kéo file vào vùng **Thả bài hát vào đây**. Có thể dùng MP3, WAV, FLAC, M4A hoặc video có âm thanh như MP4. Căn theo lời chuẩn vẫn cần file có giọng hát; bản instrumental không chứa giọng để tìm vị trí từng từ.
- Chọn **Ảnh / video nền** nếu muốn ghép nền. Video ngắn lặp đủ độ dài bài hát; tiếng của video nền không đưa vào video xuất. Bỏ trống để dùng nền màu.
- Chọn **Nhạc beat có sẵn** nếu đã có bản instrumental. Dùng beat cùng phiên bản, cùng mốc bắt đầu và khớp độ dài bài gốc. Nếu chưa có, app có thể tách giọng để tạo beat.
- Nhấn **Tạo dự án** và chờ file được nhập xong.

File nền/beat nhập bằng ô tải file được chọn **trước khi nhấn Tạo dự án**. Sau khi tạo, có thể đổi nền bằng nguồn thư mục hoặc online ở **Nguồn video nền**. Lời TXT có thể nhập sau khi đã tạo hoặc mở dự án.

### Tự chọn video từ thư mục máy tính

Trong **Nguồn video nền → Lấy video từ đâu?**, chọn **Thư mục video trên máy** và nhập đường dẫn thật, ví dụ:

```text
C:\Karaoke\Backgrounds
```

Đây là thư mục trên **máy đang chạy START**, không phải địa chỉ website. Nhấn **Quét thư mục video** để xem các clip; bật **Tìm cả trong thư mục con** nếu muốn quét thêm các thư mục bên trong. Video cần nằm trên máy hoặc ổ đĩa mà tài khoản đang chạy START đọc được.

- Muốn app chọn ngẫu nhiên khi bắt đầu bài mới: chọn nguồn local, bật **Tự chọn video nền sau khi tạo dự án**, rồi **Tạo dự án**.
- Với dự án đã mở: chọn nguồn local rồi nhấn **Tự chọn & ghép nền**, hoặc chọn **Dùng nền này** ở clip mong muốn.

App sao chép clip được chọn vào dữ liệu dự án. Tự chọn hiện dùng **một video**, lặp đủ độ dài bài hát; chưa dựng montage gồm nhiều cảnh. Âm thanh clip nền không được trộn vào bài karaoke.

### Tìm video nền online

Chọn **Kho video online** trong **Nguồn video nền**, nhập chủ đề rồi nhấn **Tìm video nền**; ví dụ `rain night`, `city lights` hoặc `ocean sunset`. Có hai nguồn:

| Nguồn | Cần gì |
| --- | --- |
| **Wikimedia Commons** | Không cần API key; mỗi video có giấy phép và yêu cầu ghi nguồn riêng |
| **Pexels** | Cần API key miễn phí từ [Pexels API](https://www.pexels.com/api/), nhập vào ô mật khẩu ngay trong app local |

Với video muốn sử dụng, nhấn **Dùng nền này** để tải và ghép vào dự án. Có thể bật **Tự chọn video nền sau khi tạo dự án** để app tự chọn từ kết quả của nguồn/chủ đề đã đặt khi tạo bài mới, hoặc dùng **Tự chọn & ghép nền** cho dự án hiện tại. Tìm và quét được nguồn khi chưa có dự án; thao tác ghép cần một dự án đã tạo.

Với Pexels, mở **Cài API key Pexels (tùy chọn)**, nhập key rồi nhấn **Lưu API key**. Key chỉ nhập trên giao diện local; không dán vào chat, file lời hoặc GitHub. App tải video về máy rồi dùng bản local. Nguồn online chỉ nhận tệp HTTPS từ các nhà cung cấp được hỗ trợ, giới hạn **200 MB mỗi clip**; nguồn local giới hạn **4 GB mỗi clip**.

### Ghi nguồn cho video online

Xem tên tác giả, trang nguồn và giấy phép hiển thị cùng kết quả/dự án. Video tải miễn phí không đồng nghĩa tất cả đều thuộc public domain: các clip Commons dùng CC BY/CC BY-SA vẫn có yêu cầu ghi công và điều kiện giấy phép tương ứng. Khi xuất bản karaoke, giữ thông tin cần thiết trong mô tả hoặc phần credit theo giấy phép của clip đó.

Thông tin nguồn được lưu cùng dự án và có thể tải thành JSON riêng. App không tự chèn dòng credit vào khung hình MP4; tải MP4 không thay thế việc giữ thông tin tác giả/giấy phép.

## 3. Đưa lời chuẩn vào và căn theo giọng hát

Trong **Lời chuẩn từ TXT**:

1. Nhấn **Chọn file TXT** hoặc dán lời vào ô văn bản. Nên lưu TXT bằng **UTF-8**; app cũng đọc UTF-16 LE/BE nếu file có BOM. Tệp tối đa 200 KiB.
2. Kiểm tra nội dung theo đúng phiên bản bài hát. Mỗi dòng nên là một câu; viết lại đầy đủ điệp khúc ở mỗi vị trí nó được hát.
3. Nhấn **Lưu lời chuẩn** nếu muốn lưu văn bản và xem bản đã bỏ chỉ dẫn. Thao tác lưu văn bản chưa thay mốc thời gian của các từ trong editor; sau khi đổi lời chuẩn, cần căn lại.
4. Chọn ngôn ngữ, model và thiết bị ở phần tạo sub, rồi nhấn **Căn lời theo giọng hát**.

Cấu hình bắt đầu cho bài tiếng Việt trên RTX 3060:

| Mục | Chọn gì trước tiên |
| --- | --- |
| Ngôn ngữ | **Tiếng Việt** |
| Model Whisper | **Small · nhanh** |
| Thiết bị xử lý | **Tự động · ưu tiên NVIDIA GPU** |
| Tách giọng hát trước khi nhận diện | Bật để căn trên giọng tách và tạo beat khi chưa có |

App dùng stable-ts/Whisper để căn văn bản chuẩn vào âm thanh giọng hát. Nội dung lời đến từ TXT bạn nhập; model tìm thời gian các từ được hát. Theo dõi tiến độ và chờ xong trước khi chỉnh lời hoặc xuất video.

Lần đầu cần Internet để tải model chưa có trong cache. Model `medium` dùng nhiều VRAM hơn; thử `small` trước, giảm xuống `base` hoặc chọn **CPU** nếu hết bộ nhớ. Nếu tự động dùng CPU dù có RTX 3060, chạy `windows\CHECK.bat` để kiểm tra CUDA và driver.

### Nhãn đoạn và chỉ dẫn âm thanh

Có thể nhập lời như sau:

```text
[Intro]
[Sound of rain pouring, slow acoustic blues guitar]
[Verse 1]
Rót thêm một chén... chén này ta tự lau nước mắt
[Chorus]
Chén đắng nhân gian này, ta nếm đủ rồi người ơi!
[Chorus]
Chén đắng nhân gian này, ta nếm đủ rồi người ơi!
```

App bỏ phần chỉ dẫn trong ngoặc vuông như `[Intro]`, `[Verse 1]`, `[Chorus]`, `[Beat stops]` hoặc `[End]`; các câu hát được giữ lại. Intro chỉ có tiếng mưa/guitar không cần lời chạy. Dấu `...` là dấu câu, không phải mốc thời gian cố định.

Điệp khúc được hát hai lần thì cần viết **đầy đủ lời hai lần**, như ví dụ trên. Đừng chỉ ghi `[Lặp điệp khúc]` hoặc `[Chorus x2]`: nhãn này không chứa lời để căn. Bỏ khỏi văn bản những câu không xuất hiện trong bản nhạc thực tế.

### Nếu kết quả căn chưa khớp

Nghe kỹ phần intro dài, ngân nga, giọng bè và các đoạn điệp khúc lặp. Lời khác phiên bản, thiếu đoạn hoặc thêm đoạn có thể làm thời gian lệch. Nếu app báo phần lời không khớp hoặc đưa ra cảnh báo, kiểm tra lại văn bản và đoạn âm thanh đó; không coi toàn bộ mốc thời gian là chính xác chỉ vì đã chạy xong.

### Khi chưa có lời chuẩn

Vẫn có thể dùng **Tạo lời & canh thời gian** để Whisper tự nhận diện lời từ âm thanh như trước. Chọn đúng ngôn ngữ, bật tách giọng nếu phù hợp, rồi nghe và sửa từ nhận sai. Nếu đã có TXT đúng bài, ưu tiên **Căn lời theo giọng hát** để tránh model tự đoán sai nội dung.

Nếu chỉ muốn lấy beat mà chưa làm lời, dùng **Chỉ tách vocal / tạo nhạc beat**. Tách bằng AI có thể vẫn để lại giọng bè hoặc một phần giọng ca sĩ.

## 4. Nghe, chỉnh mốc và sửa lệch thời gian

Sau khi căn hoặc nhận diện xong, các câu xuất hiện trong **Lời & thời gian**:

1. Nhấn vào nội dung một câu để nghe từ vị trí đó.
2. Mở **Chỉnh từng từ** bên dưới câu.
3. Sửa lời và mốc **BẮT ĐẦU (s)**, **KẾT THÚC (s)**. Đơn vị là giây; `12.50` là 12 giây rưỡi.
4. Nghe lại rồi nhấn **Lưu lời**.

Thời gian kết thúc mỗi từ phải lớn hơn bắt đầu. Các từ và câu cần đi đúng thứ tự, không chồng thời gian và không vượt độ dài bài hát. Ví dụ hợp lệ: từ đầu `1.20 → 1.65`, từ tiếp theo `1.80 → 2.30`.

### Dịch cả bài khi chữ lệch đều

Nếu tất cả chữ cùng sớm hoặc cùng muộn, dùng **Dịch thời gian toàn bài (giây)** rồi **Áp dụng**:

| Hiện tượng | Giá trị thử |
| --- | --- |
| Chữ xuất hiện sớm hơn giọng khoảng 0,3 giây | `+0.3` để chữ xuất hiện muộn hơn |
| Chữ xuất hiện muộn hơn giọng khoảng 0,3 giây | `-0.3` để chữ xuất hiện sớm hơn |

Offset áp dụng lên mốc thực của từng từ, ảnh hưởng cả preview và file xuất. Giá trị là lượng dịch thêm mỗi lần bấm, không phải một thiết lập chỉ dùng để nghe thử. Nếu app từ chối vì lời ra trước giây 0 hoặc vượt cuối bài, dùng lượng dịch nhỏ hơn hay sửa riêng câu bị lệch.

Nếu chỉ một đoạn lệch hoặc mức lệch tăng dần theo bài, đừng dịch cả bài để chữa: kiểm tra đúng phiên bản nhạc/lời, căn lại hoặc sửa mốc riêng. Sau khi thay mốc, xuất lại video/phụ đề để file tải xuống khớp nội dung mới.

Dùng **＋ Thêm câu** cho câu bị thiếu. Chức năng thêm câu thủ công chia đều thời gian cho các từ làm mốc ban đầu; cần nghe và chỉnh lại. Đây là thao tác khác với **Căn lời theo giọng hát**.

Nhấn **Lưu lời** trước khi đóng trang. App lưu lời đã chỉnh trước khi xuất, nhưng không tự lưu liên tục sau mỗi lần gõ.

## 5. Hát thử và kiểm tra Mute

Ở khung **KARAOKE PREVIEW**, nhấn **▶** để phát; kéo thanh thời gian để kiểm tra đoạn cần nghe. Chữ đang hát đổi màu theo thời gian từng từ.

| Chế độ nghe thử | Tác dụng |
| --- | --- |
| **Nghe bản gốc** | Nghe bài có giọng ca sĩ để đối chiếu lời |
| **Hát với nhạc beat** | Nghe instrumental đã tách hoặc beat đã nhập để hát theo |
| **Không tiếng** | Xem lời chạy mà không phát âm thanh |
| **Mute** | Bật/tắt toàn bộ tiếng nghe thử; không tách giọng ca sĩ |

Nhấn **⛶** để xem sân khấu toàn màn hình; nhấn `Esc` để thoát. **Space** phát/tạm dừng và **M** bật/tắt Mute khi con trỏ không ở ô nhập, nút hoặc hộp chọn. Nếu phím chưa tác dụng, nhấn vùng trống của trang trước.

## 6. Chỉnh kiểu chữ, xuất video và tải phụ đề

### Chọn kiểu sub karaoke

Trong **Xuất thành phẩm**, có thể chỉnh:

| Mục | Cách dùng |
| --- | --- |
| **Font chữ** | Arial, Tahoma, Segoe UI hoặc Times New Roman; dùng font có trên máy để preview và video khớp nhau |
| **Cỡ chữ** | Từ 24 đến 100, bắt đầu với `54` và xem thử ở khung preview |
| **Màu chữ chưa hát** | Màu phần lời chưa được hát |
| **Màu chữ đang hát** | Màu chạy qua từ đang hát |
| **Vị trí lời** | Phía trên, chính giữa hoặc phía dưới khung hình |
| **Lề trên/dưới (%)** | Từ 5 đến 25% để điều chỉnh khoảng cách lời với mép ở vị trí trên/dưới |

Các thay đổi được xem trong preview và dùng khi xuất MP4/ASS. **SRT/LRC không lưu đầy đủ font, màu và bố cục karaoke**; cách hiển thị hai định dạng này còn tùy trình phát. Khi thay kiểu chữ sau lần xuất trước, xuất lại để nhận file mới.

### Xuất thành phẩm

Trong **Xuất thành phẩm**:

1. Chọn **720p · nhẹ hơn** để thử hoặc **1080p · Full HD** cho bản hoàn chỉnh.
2. Chọn **Cỡ chữ**; có thể bắt đầu với `54`.
3. Chọn **Âm thanh video xuất**: **Bài hát gốc** giữ tiếng ca sĩ, **Nhạc beat · không vocal** dùng instrumental, **Không âm thanh** xuất video không tiếng.
4. Nhấn **Xuất video karaoke**, chờ hoàn tất rồi **Tải MP4** trong **Video đã xuất**.

**Mute và chế độ nghe thử không tự thay đổi âm thanh video xuất.** Đang nghe Mute nhưng xuất **Bài hát gốc** thì MP4 vẫn có tiếng. Muốn MP4 không tiếng, chọn **Không âm thanh** trong mục xuất.

Dùng **Xuất sub ASS / SRT / LRC** nếu chỉ cần phụ đề:

| File | Dùng khi nào |
| --- | --- |
| **MP4** | Video đã ghép nền, âm thanh đã chọn và chữ karaoke |
| **ASS** | Phụ đề giữ hiệu ứng karaoke theo từ cho phần mềm hỗ trợ ASS |
| **SRT** | Phụ đề theo câu; không giữ hiệu ứng chạy màu karaoke |
| **LRC** | Lời có thời gian theo dòng và từ; cách hiển thị tùy trình phát |
| **Dự án JSON** | Thông tin dự án và lời có thời gian; không chứa nhạc, nền hay video |
| **Nguồn video nền (JSON)** | Tác giả, trang nguồn và giấy phép của nền đã chọn để lưu hoặc ghi credit |

## Mở lại và sao lưu dự án

Lần sau chạy START, dùng hộp **DỰ ÁN CỦA BẠN** ở đầu trang để chọn bài đã làm. Nhấn **＋** bên cạnh để bắt đầu bài mới. Lời chuẩn đã lưu đi cùng dự án; sửa văn bản chuẩn rồi căn lại khi muốn tìm mốc mới.

App lưu file và dữ liệu trong **`.local-data/projects`**, trừ khi bạn đã đặt thư mục dữ liệu riêng. Để chuyển máy hoặc sao lưu, giữ cả thư mục này. JSON tải riêng không thay thế media; giao diện hiện chưa có nút nhập lại JSON.

Giữ `.local-data` và `.venv-local` khi cập nhật mã để tiếp tục dùng dữ liệu và môi trường cũ. Chỉ cần UPDATE khi phiên bản mới thêm hoặc thay thư viện; không phải chạy trước mỗi lần START.

## Khi nút bị mờ hoặc xử lý chưa xong

| Tình huống | Cách xử lý |
| --- | --- |
| **Căn lời theo giọng hát** bị mờ | Chọn/tạo dự án, nhập lời chuẩn và chờ tác vụ hiện tại hoàn tất. |
| Báo thiếu stable-ts hoặc không thấy mục TXT | Cập nhật mã, chạy **UPDATE.bat**, sau đó START và Ctrl+F5. |
| **Tạo lời & canh thời gian** bị mờ | Tạo/chọn dự án trước; nếu đang xử lý, chờ xong. |
| **Xuất video karaoke** bị mờ | Cần có lời có thời gian từ căn lời, nhận diện hoặc thêm thủ công. |
| Không chọn được beat | Tách vocal hoặc tạo dự án mới và nhập beat có sẵn. |
| **Lưu lời** bị mờ | Chưa có thay đổi, chưa chọn dự án hoặc đang xử lý. |
| Model tải lâu | Kiểm tra Internet, dung lượng trống và cửa sổ START; lần đầu cần tải trọng số. |
| Báo hết VRAM | Giảm xuống `small`/`base`, đóng ứng dụng chiếm GPU hoặc chọn CPU. |
| Lời sai hoặc lệch | Kiểm tra TXT đúng bản nhạc, viết đầy đủ đoạn lặp; nghe và sửa mốc trước khi xuất. |
| Dịch thời gian bị từ chối | Giá trị đẩy lời ra ngoài độ dài bài. Dùng lượng nhỏ hơn hoặc chỉnh riêng đoạn lệch. |
| Quét thư mục không thấy clip | Kiểm tra đường dẫn trên máy đang chạy START, quyền đọc và định dạng video. |
| Không tìm/tải được video online | Kiểm tra mạng, từ khóa, nguồn đã chọn và API key khi dùng Pexels; thử clip nhỏ hơn giới hạn tải. |
| Video nền không có tiếng | Đây là cách ghép nền: âm thanh karaoke lấy từ bài gốc/beat đã chọn. |
| Font hoặc vị trí không như mong muốn | Chọn font có trên máy, xem lại preview và xuất lại sau khi đổi kiểu chữ. |
| Trang mở Cover Studio | Dùng địa chỉ sau dòng **Karaoke Sub:** trong START; mặc định mới là 8776. |

Các lỗi Python, FFmpeg và CUDA được giải thích thêm trong [README-WINDOWS.md](../README-WINDOWS.md).
