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

## 3. Làm một bài karaoke

1. **Tạo dự án**: chọn file nhạc hoặc video có tiếng hát. Có thể chọn thêm video/ảnh nền và beat riêng nếu đã có. Dùng tên bài hát dễ nhận biết.
2. **Tạo sub tự động**: chọn ngôn ngữ Việt, model `small`, thiết bị `auto`. Có thể bật tách vocal để nhận diện trên giọng hát và tạo nhạc không lời. Lần đầu model cần được tải về.
3. **Kiểm tra lời**: nghe và sửa từ sai, thời gian bắt đầu/kết thúc của từng từ. AI nhận diện lời hát không hoàn hảo, nhất là nhạc nền lớn, bè hoặc giọng xử lý nhiều hiệu ứng.
4. **Hát thử**: chọn âm thanh gốc để nghe mẫu; chuyển sang beat/instrumental để hát. Chữ đang hát được tô màu theo thời gian.
5. **Ghép nền và xuất**: chọn độ phân giải 720p/1080p, cỡ chữ và âm thanh xuất, rồi xuất MP4. Có thể tải riêng ASS, SRT, LRC và dữ liệu lời của dự án.

**Mute** tắt toàn bộ âm thanh khi nghe thử. Để chỉ bỏ giọng ca sĩ và giữ nhạc, chọn **tách vocal / instrumental** hoặc đưa beat riêng vào dự án. Khi xuất, chọn rõ **âm gốc**, **instrumental** hoặc **không tiếng**; nút Mute nghe thử không tự thay đổi lựa chọn âm thanh của file xuất.

- **ASS**: giữ hiệu ứng karaoke tô chữ theo từng từ.
- **SRT**: lời theo câu; định dạng này không giữ hiệu ứng chạy màu karaoke.
- **LRC**: lời có mốc thời gian theo dòng cho trình phát hỗ trợ.
- **MP4**: chữ được ghép cố định vào khung hình; phát trên thiết bị thông thường.

Video/ảnh nền được dùng làm hình ảnh, âm thanh của video nền được bỏ. Video nền ngắn được lặp cho đủ bài. Khi không chọn nền, app dùng nền màu. Xuất MP4 hiện dùng FFmpeg `libx264` trên CPU để tương thích; RTX 3060 được dùng cho nhận diện lời/tách vocal, không có yêu cầu NVENC.

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
| Lời lệch/nhận sai | Chọn đúng ngôn ngữ, thử nhận diện sau tách vocal, sửa từ/mốc thời gian trước xuất. |
| Beat vẫn còn giọng bè | Tách vocal bằng AI không đảm bảo loại bỏ hết giọng. Beat riêng thường cho kết quả tốt hơn. |
| Không mở được trang | Kiểm tra cửa sổ START còn chạy và mở đúng địa chỉ sau dòng `Karaoke Sub:` (mặc định `http://127.0.0.1:8776`, có thể đổi khi cổng bị chiếm). Nếu đang thấy Cover Studio ở 8765, tải bản Karaoke Sub mới rồi chạy START; không cần đóng Cover Studio. |
| Xuất video lâu | libx264 dùng CPU; thử 720p và video nền nhỏ hơn. Theo dõi tiến trình trong app. |

## Nguồn và phạm vi kiểm thử

Dựa trên [nomadkaraoke/karaoke-gen](https://github.com/nomadkaraoke/karaoke-gen), snapshot nguồn `d59b5bf`, giấy phép MIT của Nomad Karaoke LLC được giữ trong [LICENSE](LICENSE). Local Studio là phần bổ sung cho cách dùng local.

Kết quả chi tiết nằm ở [LOCAL-TEST-REPORT.md](LOCAL-TEST-REPORT.md). Bộ kiểm thử API/xuất video đã qua trên cả Windows và Linux trong GitHub Actions; Whisper/Demucs thật đã chạy thử trên Linux CPU. Chưa chạy trọn bộ cài trên PC Windows của người dùng hoặc suy luận CUDA trên RTX 3060 thật. **CHECK.bat** giúp xác minh môi trường thực sau khi cài; nên thử bài ngắn trước khi xử lý cả thư viện.
