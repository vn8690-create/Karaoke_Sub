# Karaoke Editor + Auto Karaoke Wizard: tài liệu kỹ thuật

## Mô hình dữ liệu (`src/karaoke.ts`)
`KLine { id, words: { text, start, end }[], sep, est? }`. Giống `segments[].words[]` của backend `local_studio`: mỗi từ có mốc riêng, được phép có khoảng lặng giữa các từ. `sep` là ký tự nối khi hiển thị (`' '` cho tiếng Việt/Anh, `''` cho tiếng Nhật). `est = true` nghĩa là mốc từng từ chỉ là ước lượng (chia đều theo độ dài chữ): xuất hiện khi nhập SRT/LRC thường/TXT hoặc khi sửa chữ làm đổi số từ.
Mọi thao tác sửa là hàm thuần (`moveEdge`, `shiftLine`, `shiftAll`, `editText`, `distribute`, `insertAfter`, `removeLine`) nên test được không cần giao diện.

## Kéo mép trên waveform
Mỗi từ có 2 mép (đầu, cuối). Mép của hai từ liền nhau (≤ 2 ms) được coi là một mép chung, kéo cùng nhau. Ràng buộc: mỗi từ ≥ 20 ms, không vượt mép từ kế, mép đầu câu không lùi vào câu trước, mép cuối câu không lấn câu sau. Kéo bằng chuột làm tròn 10 ms; giữ Alt để chính xác 1 ms.
Phím: ←/→ ±10 ms (Shift ±100 ms, Alt ±1 ms) · M đánh dấu mép đang chọn tại playhead rồi sang mép kế (đánh dấu theo bài đang phát) · Ctrl+cuộn zoom · Delete xoá câu · Ctrl+Z/Y hoàn tác/làm lại (tối đa 200 bước, riêng cho lời, tách khỏi undo của timeline) · Space phát/dừng.
Quy ước thời gian: thời gian lời = thời gian dự án; clip nhạc phải bắt đầu ở 0 s. Offset toàn bài (ms) là thao tác không phá huỷ cho preview và khi xuất; nút "Áp dụng" ghi vào dữ liệu.

## Định dạng (`src/formats.ts`)
| Định dạng | Đọc | Ghi | Ghi chú |
|---|---|---|---|
| LRC | có | có | Mốc kết thúc câu lưu bằng dòng `[mm:ss.xx]` rỗng khi có khoảng trống. |
| Enhanced LRC | có | có | `<mm:ss.xx>` trước từng từ; khoảng lặng giữa từ lưu bằng mốc rỗng. |
| SRT | có | có | Chỉ mức câu; mốc từ khi đọc là ước lượng. |
| ASS | có (`\k`, `\kf`, `\ko`) | có (`\kf`, khoảng lặng bằng `\k` rỗng) | Style mặc định Arial 64, màu theo kiểu chữ trong Inspector. Tag khác bị bỏ qua. |
Mã hoá UTF-8 không BOM. Khứ hồi (xuất rồi đọc lại) được kiểm thử trong ±10 ms.

## Hiệu ứng chữ (`src/components/karaokeDraw.ts`)
6 hiệu ứng: tô quét theo từ, từ đang hát phóng to, phát sáng, từ nhún, hiện dần như gõ chữ, câu mờ vào/ra. Chọn font, cỡ, vị trí, 3 màu, hiện câu kế tiếp. Tô màu tính theo `start/end` của từng từ, kiểm thử bằng canvas giả (`tests/draw.test.ts`).
Chỉ ảnh hưởng preview. Khi xuất video bằng backend, kiểu này chưa được truyền sang: xem "API còn thiếu".

## Wizard
4 bước: Nguồn → Ngôn ngữ & lời → Xử lý → Kết quả. Hai engine:
- **MOCK** (`adapters/mock.ts`): tiến trình giả lập, lời của bạn chia đều theo thời lượng. Mọi nơi dùng đều gắn nhãn MOCK.
- **Backend local_studio** (`adapters/backend.ts`): có lời → `POST /api/projects/{id}/align`; không lời → `POST .../transcribe`; hỏi `GET /api/projects/{id}` mỗi giây tới `ready`/`error`. Mở kết quả sẽ tải file nhạc của dự án vào timeline.
Trạng thái hiển thị: chưa tải model, đang tải model, đang phân tích, đang nhận diện, đang căn thời gian, thành công, lỗi, đã hủy. Hai trạng thái đầu chưa được backend báo nên giao diện chưa dùng tới.

## API backend đã dùng (không sửa backend)
`GET /api/health`, `GET /api/projects`, `GET /api/projects/{id}`, `PUT /api/projects/{id}/lyrics`, `POST .../align`, `POST .../transcribe`, `POST .../timing` (có trong client, nút chưa dùng), `GET .../files/{name}`. Dev: Vite proxy `/api` → `127.0.0.1:8776`.
Kiểm thử client bằng **máy chủ giả** mô phỏng hình dạng API đọc từ `local_studio/app.py`; **chưa chạy với backend thật**.

## API còn thiếu / cần người phụ trách backend quyết định
1. Tiếng Nhật: `language` chỉ nhận `vi|en|auto`. Wizard chặn `ja` với backend.
2. Hủy job align/transcribe: Wizard hiện chỉ dừng theo dõi, chưa hủy việc đang chạy ở backend.
3. Chạy bản build của NVS: dev dùng Vite proxy; bản build cần backend phục vụ tĩnh `nvs_studio/dist` hoặc bật CORS.
4. Tạo dự án / tải nhạc lên từ NVS: chưa nối (NVS mới mở dự án đã có).
5. Truyền kiểu chữ Karaoke (hiệu ứng, màu, font) sang bước render/ASS của backend.
6. Báo trạng thái "tải model" trong `message`/`status` để Wizard hiện đúng.

## Giới hạn đã biết
- Xuất video, hàng đợi render, kiểm tra MP4, backup ZIP: do người khác phụ trách, chưa nối.
- Preview video (khung hình) chưa hỗ trợ; chỉ phát âm thanh.
- Nghe thử câu dùng playhead dự án: nhạc phải ở track Nhạc, bắt đầu 0 s.
- Đã kiểm thử trên Chromium headless; chưa thử trên Safari/Firefox/màn hình cảm ứng.
