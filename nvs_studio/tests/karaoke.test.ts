import { describe, expect, it } from 'vitest';
import { distribute, editText, fromSegments, insertAfter, lEnd, lStart, lineAt, makeLine, moveEdge, plainToLines, referenceRows, canonicalReference, overlayReferenceText, shiftAll, shiftLine, splitWords, toSegments, validateForBackend, type KLine } from '../src/karaoke';
import { detectFormat, parseAny, parseASS, parseLRC, parseSRT, toASS, toLRC, toSRT } from '../src/formats';

const mk = (text: string, a: number, b: number) => makeLine(text, a, b)!;
const close = (x: number, y: number, tol = 0.011) => expect(Math.abs(x - y)).toBeLessThanOrEqual(tol);
const same = (a: KLine[], b: KLine[], tol = 0.011) => { expect(b.length).toBe(a.length); a.forEach((l, i) => { expect(b[i].words.map((w) => w.text)).toEqual(l.words.map((w) => w.text)); l.words.forEach((w, j) => { close(b[i].words[j].start, w.start, tol); close(b[i].words[j].end, w.end, tol); }); }); };
const demo = () => [mk('Xin chào các bạn', 1, 5), mk('Tạm biệt nhé', 6, 9)];

describe('chỉnh sửa thời gian', () => {
  it('kéo mép chung của hai từ liền nhau làm cả hai đổi, và không vượt từ kế', () => {
    const L = demo(); const mid = L[0].words[1].end; const out = moveEdge(L, L[0].id, 3, mid + 0.1);
    close(out[0].words[1].end, mid + 0.1, 0.001); close(out[0].words[2].start, mid + 0.1, 0.001);
    const far = moveEdge(L, L[0].id, 1, 99); expect(far[0].words[0].end).toBeLessThan(far[0].words[1].end);
  });
  it('không cho đầu câu lùi vào câu trước và cuối câu lấn câu sau', () => {
    const L = demo(); expect(moveEdge(L, L[1].id, 0, 0)[1].words[0].start).toBeCloseTo(lEnd(L[0]), 3);
    expect(moveEdge(L, L[0].id, L[0].words.length * 2 - 1, 100)[0].words.at(-1)!.end).toBeCloseTo(lStart(L[1]), 3);
  });
  it('luôn giữ mỗi từ dài ≥ 20ms', () => {
    const L = demo(); const out = moveEdge(L, L[0].id, 0, 4.99); expect(out[0].words[0].end - out[0].words[0].start).toBeGreaterThanOrEqual(0.0199);
  });
  it('dịch câu bị chặn bởi câu kề; dịch cả bài không âm', () => {
    const L = demo(); expect(lEnd(shiftLine(L, L[0].id, 10)[0])).toBeLessThanOrEqual(lStart(L[1]) + 1e-6); expect(lStart(shiftAll(L, -50)[0])).toBe(0);
  });
  it('sửa chữ giữ mốc nếu cùng số từ, chia lại nếu khác', () => {
    const L = demo(); const a = editText(L, L[0].id, 'A B C D'); expect(a[0].words.map((w) => w.start)).toEqual(L[0].words.map((w) => w.start));
    const b = editText(L, L[0].id, 'chỉ hai'); expect(b[0].words).toHaveLength(2); expect(b[0].est).toBe(true); expect(lStart(b[0])).toBeCloseTo(lStart(L[0]), 3);
  });
  it('chia đều lại từ, thêm câu mới vào khoảng trống, tìm câu theo thời gian', () => {
    const L = demo(); expect(distribute(moveEdge(L, L[0].id, 1, 2), L[0].id)[0].est).toBe(true);
    const r = insertAfter(L, L[0].id, 'Câu thêm'); expect(r.lines).toHaveLength(3); expect(lStart(r.lines[1])).toBeGreaterThan(lEnd(L[0])); expect(lEnd(r.lines[1])).toBeLessThanOrEqual(lStart(L[1]));
    expect(lineAt(L, 3)).toBe(0); expect(lineAt(L, 5.7)).toBe(1); expect(lineAt(L, 20)).toBe(-1);
  });
  it('tách từ tiếng Nhật và giữ nguyên chữ', () => { const r = splitWords('お母さんは怖いですね'); expect(r.sep).toBe(''); expect(r.words.length).toBeGreaterThan(2); expect(r.words.join('')).toBe('お母さんは怖いですね'); });
  it('văn bản thường chia đều theo độ dài và bỏ nhãn [Verse]', () => { const L = plainToLines('[Verse]\nMột hai ba\nBốn năm', 20); expect(L).toHaveLength(2); expect(lEnd(L[1])).toBeCloseTo(20, 1); });
});
describe('TXT chuẩn bảo vệ lời gốc và mốc thời gian đã chỉnh', () => {
  it('bỏ hướng dẫn nhạc nhưng giữ chính xác dấu và chữ Unicode', () => {
    const text = '\uFEFF[Intro]\\\n[Verse 1]\\\nXin [đệm] chào...\n[Chorus]\nNGƯỜI ơi!';
    expect(referenceRows(text)).toEqual(['Xin chào...', 'NGƯỜI ơi!']);
    expect(canonicalReference(text)).toBe(canonicalReference('Xin chào...\nNGƯỜI ơi!'));
    expect(canonicalReference('Xin chao')).not.toBe(canonicalReference('Xin chào'));
  });
  it('thay chữ theo TXT khi số câu và từ bằng nhau, giữ từng mốc chính xác', () => {
    const before = [mk('Xin chao cac ban', 1, 4), mk('Tam biet nhe', 5, 9)];
    before[0].words[1].start = 1.777;
    before[1].words[1].end = 7.333;
    const r = overlayReferenceText(before, '[Verse]\nXin chào các bạn\nTạm biệt nhé');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lines.map((l) => l.words.map((w) => w.text))).toEqual([['Xin', 'chào', 'các', 'bạn'], ['Tạm', 'biệt', 'nhé']]);
    expect(r.lines[0].words[1].start).toBe(1.777);
    expect(r.lines[1].words[1].end).toBe(7.333);
    expect(before[0].words[1].text).toBe('chao');
    expect(r.lines[0].id).toBe(before[0].id);
  });
  it('khác số câu/từ thì không sửa lời và không giả lập thời gian', () => {
    const before = [mk('Xin chao ban', 1, 3), mk('Tam biet', 4, 6)];
    const beforeJson = JSON.stringify(before);
    const rows = overlayReferenceText(before, 'Xin chào bạn!\nMột câu thừa\nTạm biệt');
    expect(rows.ok).toBe(false);
    if (!rows.ok) expect(rows.message).toContain('3 câu');
    const words = overlayReferenceText(before, 'Xin chào\nTạm biệt');
    expect(words.ok).toBe(false);
    if (!words.ok) expect(words.message).toContain('Câu 1');
    expect(JSON.stringify(before)).toBe(beforeJson);
  });
  it('TXT Nhật giữ chữ gốc nếu phân tách trùng với timestamp cũ', () => {
    const source = 'お母さんは怖いですね';
    const line = mk(source, 2, 7);
    const replaced = overlayReferenceText([line], source, 'ja');
    expect(replaced.ok).toBe(true);
    if (replaced.ok) {
      expect(replaced.lines[0].words.map((w) => w.text).join('')).toBe(source);
      expect(replaced.lines[0].words.map((w) => [w.start, w.end]))
        .toEqual(line.words.map((w) => [w.start, w.end]));
    }
  });
});

describe('định dạng', () => {
  it('Enhanced LRC khứ hồi, kể cả khoảng lặng giữa các từ', () => {
    const L = demo(); L[0].words[1].end -= 0.3; same(L, parseLRC(toLRC(L, 0, true)));
  });
  it('LRC thường khứ hồi giữ đầu/cuối câu nhờ mốc kết thúc', () => { const L = demo(); const back = parseLRC(toLRC(L)); expect(back).toHaveLength(2); close(lStart(back[0]), lStart(L[0])); close(lEnd(back[0]), lEnd(L[0])); expect(back[0].est).toBe(true); });
  it('SRT khứ hồi theo từng câu', () => { const L = demo(); const back = parseSRT(toSRT(L)); expect(back).toHaveLength(2); close(lStart(back[1]), lStart(L[1]), 0.002); close(lEnd(back[1]), lEnd(L[1]), 0.002); });
  it('ASS karaoke \\k khứ hồi (Việt và Nhật)', () => {
    const jp = makeLine('お母さんは怖いですね', 2, 6)!; const L = [...demo(), jp]; same(L, parseASS(toASS(L)));
  });
  it('đọc ASS từ trình khác (\\kf, \\ko, tag lạ, dấu phẩy trong chữ)', () => {
    const src = '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\an2\\k50}Xin, {\\ko50}chào\nComment: 0,0:00:09.00,0:00:10.00,Default,,0,0,0,,bỏ qua';
    const L = parseASS(src); expect(L).toHaveLength(1); expect(L[0].words.map((w) => w.text)).toEqual(['Xin,', 'chào']); close(L[0].words[1].end, 2);
  });
  it('nhận diện định dạng và xử lý đầu vào xấu mà không lỗi', () => {
    expect(detectFormat('[Events]\nDialogue: 0')).toBe('ass'); expect(detectFormat('1\n00:00:01,000 --> 00:00:02,000\na')).toBe('srt'); expect(detectFormat('[00:01.00]a')).toBe('lrc'); expect(detectFormat('chỉ là chữ')).toBe('plain');
    for (const bad of ['', '[00:xx]', '--> -->', '[Events]\nDialogue: x', '\uFEFF']) expect(() => parseAny(bad)).not.toThrow();
  });
  it('xuất áp dụng offset và không ra thời gian âm', () => { const L = demo(); expect(toSRT(L, -10)).toContain('00:00:00,000'); expect(toLRC(L, 2)).toContain('[00:03.00]'); });
});
describe('cầu nối backend', () => {
  it('segments khứ hồi và kiểm tra luật như backend', () => {
    const L = demo(); same(L, fromSegments(toSegments(L)), 0.001); expect(validateForBackend(L, 100)).toEqual([]);
    expect(validateForBackend(L, 8).join()).toMatch(/vượt/); const bad = structuredClone(L); bad[1].words[0].start = 4; expect(validateForBackend(bad, 100).length).toBeGreaterThan(0);
    expect(validateForBackend(L, 100, -5).join()).toMatch(/trước 0/);
  });
});
