# Karaoke Sub — chạy local trên Windows + RTX 3060

Chế độ **Local Studio** bổ sung giao diện tiếng Việt để làm karaoke trên máy của bạn: tạo lời theo từng từ, sửa lời và mốc thời gian, tách vocal để lấy beat, hát thử, ghép video/ảnh nền và xuất MP4 hoặc phụ đề. Phần này chạy độc lập với backend cloud của dự án gốc, không cần tài khoản hay API key.

**Đã mở được app và muốn làm bài đầu tiên?** Xem [hướng dẫn sử dụng từng bước](docs/LOCAL-USAGE.md), hoặc nhấn **Hướng dẫn** ở đầu giao diện. Trang này tập trung vào cài đặt và xử lý lỗi trên Windows.

## 1. Chuẩn bị

- Windows 10/11 64-bit; Python **3.11 64-bit** từ [python.org](https://www.python.org/downloads/windows/). Khi cài, bật Python Launcher; có thể dùng `winget install --id Python.Python.3.11 --exact`.
- Driver NVIDIA cập nhật cho RTX 3060. Không cần cài CUDA Toolkit riêng: bộ cài dùng PyTorch CUDA 12.1 đã kèm thư viện runtime. Driver phải hỗ trợ CUDA 12.1; kiểm tra bằng `nvidia-smi`.
- Kết nối Internet khi cài thư viện và tải model lần đầu. Các lần sau dùng model đã lưu trên máy.
- Dung lượng trống khoảng **15 GB trở lên**, cộng thêm dung lượng bài hát và video xuất. Tách vocal và xuất video tạo nhiều file trung gian.
- FFmpeg và ffprobe có bộ lọc `ass`. Bộ cài tự thử cài **Gyan.FFmpeg** bằng winget nếu chưa có. Nếu máy không có winget, tải FFmpeg từ [Gyan](https://www.gyan.dev/ffmpeg/builds/), giải nén và thêm thư mục `bin` vào PATH.

RTX 3060 có bản 6 GB và 12 GB VRAM. Bắt đầu với Whisper **small** và tiếng Việt (`vi`). Model **medium** thường nhận lời tốt hơn nhưng cần nhiều VRAM; hãy giảm model hoặc chọn CPU nếu hết bộ nhớ. Đóng game và ứng dụng GPU khác khi xử lý bài hát.

## 2. Cài và chạy

1. Tải repo dưới dạng ZIP bằng **Code → Download ZIP**, rồi giải nén. Chạy từ thư mục đã giải nén, không mở file ngay bên trong ZIP.
2. Mở thư mục `windows`, nhấp đúp **SETUP.bat**. Bước này tạo `.venv-local`, cài thư viện, chọn CUDA nếu nhận diện được NVIDIA, và kiểm tra FFmpeg. Quá trình tải PyTorch/model có thể lâu tùy mạng; để cửa sổ chạy đến khi báo hoàn tất.
3. Nhấp đúp **START.bat**. Cổng mặc định là **http://127.0.0.1:8776** để tránh trùng Cover Studio ở cổng 8765. Nếu cổng 8776 cũng đang dùng, app tự chọn cổng trống khác, in địa chỉ thực trong cửa sổ START và mở đúng ứng dụng Karaoke Sub.
4. Giữ cửa sổ chạy app mở trong lúc làm karaoke. Nhấn `Ctrl+C` để dừng.

Không cần cài Node.js, Docker, Poetry, Google Cloud hay toàn bộ dependency trong `pyproject.toml` cho Local Studio. Mã cloud và CLI gốc vẫn được giữ để tham khảo.

Cài theo chế độ CPU nếu chưa dùng được GPU:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\setup.ps1 -CpuOnly
```

Chạy **CHECK.bat** để kiểm tra Python, PyTorch, CUDA, tên GPU, VRAM, FFmpeg và xung đột thư viện. Kiểm tra này không thay thế việc chạy thử một bài hát.

### Cập nhật bản đã cài để dùng lời TXT

1. Dừng cửa sổ START bằng `Ctrl+C`.
2. Cập nhật mã hoặc giải nén gói cập nhật đè vào thư mục Karaoke_Sub đang dùng. Giữ nguyên `.venv-local` và `.local-data`.
3. Nhấp đúp **`windows\UPDATE.bat`** và đợi thông báo hoàn tất. Script dùng môi trường Python hiện có, cài thư viện còn thiếu/cần cập nhật trong `requirements-local.txt` (bao gồm stable-ts), rồi kiểm tra phụ thuộc; không tạo lại môi trường hoặc ép cài lại PyTorch.
4. Chạy **`windows\START.bat`**, nhấn **Ctrl+F5** trong trình duyệt. Bạn sẽ thấy mục **Lời chuẩn từ TXT**.

Không cần chạy lại SETUP khi môi trường cũ đang hoạt động. UPDATE cần Internet để lấy thư viện mới; nếu chưa từng SETUP thì chạy SETUP trước. Căn lời lần đầu có thể cần tải model Whisper nếu model đã chọn chưa có trong cache.

## 3. Làm một bài karaoke

1. **Tạo dự án**: chọn nhạc/video có tiếng hát. Có thể tải nền/beat riêng, hoặc đặt **Nguồn video nền** là thư mục máy tính/online và bật **Tự chọn video nền**. Dùng tên bài dễ nhận biết.
2. **Dùng lời chuẩn**: chọn TXT hoặc dán lời vào **Lời chuẩn từ TXT**, chọn Tiếng Việt, model `small`, thiết bị `auto`, rồi nhấn **Căn lời theo giọng hát**. Có thể bật tách vocal để căn trên giọng và tạo nhạc không lời. Khi chưa có lời chuẩn, dùng **Tạo lời & canh thời gian** để nhận diện như trước.
3. **Kiểm tra thời gian**: nghe và sửa mốc từng từ, nhất là intro dài, bè, ngân nga và điệp khúc lặp. Lời TXT phải đúng phiên bản đang hát và viết đầy đủ mọi đoạn lặp. Nếu cả bài lệch cùng một lượng, dùng **Dịch thời gian toàn bài (giây)** rồi **Áp dụng**; số dương làm chữ muộn hơn, số âm làm chữ sớm hơn. Lưu lời và xuất lại video sau khi chỉnh.
4. **Hát thử**: chọn âm thanh gốc để nghe mẫu; chuyển sang beat/instrumental để hát. Chữ đang hát được tô màu theo thời gian.
5. **Ghép nền và xuất**: có thể đổi nền bằng **Tự chọn & ghép nền** hoặc **Dùng nền này**. Chỉnh font/màu/vị trí/lề, chọn 720p/1080p và âm thanh xuất, rồi xuất MP4. Có thể tải riêng ASS, SRT, LRC và JSON nguồn video nền.

**Mute** tắt toàn bộ âm thanh khi nghe thử. Để chỉ bỏ giọng ca sĩ và giữ nhạc, chọn **tách vocal / instrumental** hoặc đưa beat riêng vào dự án. Khi xuất, chọn rõ **âm gốc**, **instrumental** hoặc **không tiếng**; nút Mute nghe thử không tự thay đổi lựa chọn âm thanh của file xuất.

- **ASS**: giữ hiệu ứng karaoke tô chữ theo từng từ.
- **SRT**: lời theo câu; định dạng này không giữ hiệu ứng chạy màu karaoke.
- **LRC**: lời có mốc thời gian theo dòng cho trình phát hỗ trợ.
- **MP4**: chữ được ghép cố định vào khung hình; phát trên thiết bị thông thường.

### Nguồn video nền và kiểu chữ

- **Thư mục local**: nhập đường dẫn trên máy đang chạy START, ví dụ `C:\Karaoke\Backgrounds`. App quét video và có thể chọn ngẫu nhiên một clip để ghép; clip được sao chép vào dự án.
- **Online**: Commons không cần key. Pexels cần API key miễn phí, nhập vào ô mật khẩu trên giao diện local; không ghi key vào repo hoặc gửi qua chat. Video online được tải về máy, tối đa 200 MB mỗi clip; clip local tối đa 4 GB.
- **Ghi nguồn**: xem tác giả, trang nguồn và giấy phép của clip. Với Commons CC BY/CC BY-SA, giữ credit/điều kiện tương ứng khi xuất bản. App lưu metadata nguồn trong dự án/JSON riêng, không tự ghi credit lên hình MP4.
- **Kiểu chữ**: chọn Arial, Tahoma, Segoe UI hoặc Times New Roman; cỡ 24–100; màu chữ/màu karaoke; vị trí trên/giữa/dưới và lề 5–25%. Font cần có trên máy. Preview và MP4/ASS dùng kiểu đã chọn; SRT/LRC không giữ toàn bộ định dạng này.

Xem [hướng dẫn nguồn nền và xuất video](docs/LOCAL-USAGE.md) để làm từng bước.

Video/ảnh nền được dùng làm hình ảnh, âm thanh của video nền được bỏ. Tự chọn hiện ghép một clip, không dựng nhiều cảnh; video nền ngắn được lặp cho đủ bài. Khi không chọn nền, app dùng nền màu. Xuất MP4 hiện dùng FFmpeg `libx264` trên CPU để tương thích; RTX 3060 được dùng cho nhận diện lời/tách vocal, không có yêu cầu NVENC.

## 4. Dữ liệu và model

- `.venv-local/`: môi trường Python riêng, tạo lại bằng SETUP nếu cần.
- `.local-data/models/`: cache model của Whisper/PyTorch khi chạy qua START.bat. Giữ thư mục này để tránh tải lại model.
- `.local-data/projects/`: dự án, âm thanh trung gian, phụ đề và video xuất. Giao diện cho phép mở lại dự án đã tạo. Có thể đặt biến `KARAOKE_DATA_DIR` để chuyển thư mục dữ liệu; `KARAOKE_MODEL_DIR` để chuyển cache model khi chạy bằng Python trực tiếp.
- Local Studio chỉ lắng nghe `127.0.0.1`, dùng trên chính máy đang chạy. Không cần mở cổng/router.
- Tải model dùng Internet; xử lý âm thanh và video của Local Studio diễn ra trên máy. Các tích hợp cloud của mã gốc không được dùng trong luồng này.

Không đưa `.venv-local`, `.local-data`, model, file bài hát hoặc video xuất lên GitHub. Nếu chuyển máy, sao lưu thư mục dữ liệu dự án trước.

## 5. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không tìm thấy Python 3.11 | Cài đúng bản 64-bit, bật Python Launcher, mở lại terminal rồi chạy SETUP. Python 3.13/3.14 không dùng cho môi trường này. |
| Không tìm thấy FFmpeg/ffprobe hoặc thiếu ASS | Chạy lại SETUP; kiểm tra PATH hoặc cài bản Gyan đầy đủ. Sau khi cài thủ công, mở lại cửa sổ chạy. |
| Có RTX 3060 nhưng CUDA báo `False` | Cập nhật driver, kiểm tra `nvidia-smi`, chạy lại SETUP. App có thể dùng CPU trong lúc xử lý lỗi GPU. |
| `CUDA out of memory` | Giảm model xuống `small`/`base`, tắt ứng dụng GPU khác; chọn CPU nếu cần. |
| Tải model lỗi hoặc chưa có mạng | Kiểm tra Internet và dung lượng trống rồi thử lại. Không có model đã cache thì chưa thể chạy AI offline. |
| Lời lệch/nhận sai | Dùng lời TXT đúng bài và **Căn lời theo giọng hát**, chọn đúng ngôn ngữ, thử tách vocal trước. Nghe và sửa từng từ; nếu lệch đều, dùng dịch thời gian toàn bài. |
| Không thấy mục TXT hoặc báo thiếu stable-ts | Cập nhật mã, chạy **UPDATE.bat**, rồi START và Ctrl+F5. Không cần SETUP lại nếu môi trường cũ đã hoạt động. |
| Dịch thời gian bị từ chối | Offset đang đưa lời ra trước giây 0 hoặc vượt cuối bài. Chọn lượng dịch nhỏ hơn hoặc chỉnh riêng những câu bị lệch. |
| Beat vẫn còn giọng bè | Tách vocal bằng AI không đảm bảo loại bỏ hết giọng. Beat riêng thường cho kết quả tốt hơn. |
| Không thấy video trong thư mục | Nhập đúng đường dẫn trên máy đang chạy START và kiểm tra quyền đọc/định dạng clip. |
| Pexels tìm/tải lỗi | Kiểm tra key đã nhập trong giao diện local, mạng và giới hạn 200 MB; có thể chọn Commons để tìm không cần key. |
| Không mở được trang | Kiểm tra cửa sổ START còn chạy và mở đúng địa chỉ sau dòng `Karaoke Sub:` (mặc định `http://127.0.0.1:8776`, có thể đổi khi cổng bị chiếm). Nếu đang thấy Cover Studio ở 8765, tải bản Karaoke Sub mới rồi chạy START; không cần đóng Cover Studio. |
| Xuất video lâu | libx264 dùng CPU; thử 720p và video nền nhỏ hơn. Theo dõi tiến trình trong app. |

## Nguồn và phạm vi kiểm thử

Dựa trên [nomadkaraoke/karaoke-gen](https://github.com/nomadkaraoke/karaoke-gen), snapshot nguồn `d59b5bf`, giấy phép MIT của Nomad Karaoke LLC được giữ trong [LICENSE](LICENSE). Local Studio là phần bổ sung cho cách dùng local.

Kết quả chi tiết nằm ở [LOCAL-TEST-REPORT.md](LOCAL-TEST-REPORT.md). Bộ kiểm thử API/xuất video đã qua trên cả Windows và Linux trong GitHub Actions; Whisper/Demucs thật đã chạy thử trên Linux CPU. Chưa chạy trọn bộ cài trên PC Windows của người dùng hoặc suy luận CUDA trên RTX 3060 thật. **CHECK.bat** giúp xác minh môi trường thực sau khi cài; nên thử bài ngắn trước khi xử lý cả thư viện.
