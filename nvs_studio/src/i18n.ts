// Khung i18n: thêm ngôn ngữ bằng cách thêm một bảng khác và đổi `lang`.
const vi = {
  'tb.new': 'Dự án mới', 'tb.open': 'Mở', 'tb.save': 'Lưu', 'tb.undo': 'Hoàn tác', 'tb.redo': 'Làm lại', 'tb.auto': 'Auto Karaoke', 'tb.export': 'Xuất video',
  'lib.media': 'Media', 'lib.audio': 'Âm thanh', 'lib.text': 'Chữ', 'lib.fx': 'Hiệu ứng', 'lib.tpl': 'Mẫu', 'lib.import': 'Nhập file',
  'unsupported': 'Chưa hỗ trợ trong bản giao diện này (cần backend).',
} as const;
type Key = keyof typeof vi;
const tables: Record<string, Record<Key, string>> = { vi };
export const lang = 'vi';
export const t = (k: Key) => tables[lang][k];
