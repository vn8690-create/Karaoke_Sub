# Sửa lỗi PyTorchStreamReader / failed finding central directory

**Dấu hiệu:** khi nhấn *Căn lời theo giọng hát*, AI báo
\`PytorchStreamReader failed reading zip archive: failed finding central directory\`.
Đây thường là một checkpoint PyTorch (.pt/.th) tải thiếu hoặc bị hỏng,
không phải lỗi TXT hay phụ đề.

## Cơ chế mới

- Căn lời với stable-ts/Whisper và nhận diện bằng whisper-timestamped dùng chung
  bộ kiểm tra checkpoint. Nếu PyTorch báo model Whisper hỏng, chương trình
  **chỉ xóa file .pt của model đã chọn trong cache Whisper** rồi gọi tải lại
  đúng một lần. Các bản nhạc, lời TXT và project JSON không bị động tới.
- Nếu lỗi xảy ra ở bước tách giọng Demucs, thông báo chỉ rõ thư mục
  \`.local-data/models/torch/hub/checkpoints\`. Không tự động xóa các model
  Demucs khác vì chưa xác định checkpoint nào hỏng.

## Chẩn đoán trên Windows (PowerShell)

Chạy trong thư mục gốc Karaoke_Sub (không phải nvs_studio):

    $cache = Join-Path (Get-Location) ".local-data\models"
    Get-ChildItem -LiteralPath (Join-Path $cache "whisper") -Filter "*.pt" -Recurse -File -ErrorAction SilentlyContinue | Select-Object FullName, Length
    Get-ChildItem -LiteralPath (Join-Path $cache "torch\hub\checkpoints") -Filter "*.th" -File -ErrorAction SilentlyContinue | Select-Object FullName, Length

- Nếu báo lỗi **Whisper**, thử căn lại một lần. App tự xóa và tải lại
  riêng checkpoint bị hỏng khi xác định chắc chắn.
- Nếu báo lỗi **Demucs**, đóng app, xác nhận tất cả file .th trong thư mục
  checkpoint đều là model được tải về. Có thể xóa các checkpoint Demucs bị
  hỏng trong \`.local-data\models\torch\hub\checkpoints\` để tải lại.
  Không xóa cả \`.local-data\`, \`.venv-local\` hoặc tệp âm thanh.
- Nếu tải lại thất bại, kiểm tra mạng và dung lượng ổ đĩa. Với GPU 4GB
  nếu báo \`CUDA out of memory\` là lỗi khác, không phải lỗi cache.

Unit test cho nhánh này sử dụng loader giả, không tải model AI.
Muốn xác nhận thật, thử lại trên máy Windows với nhạc của mình.
