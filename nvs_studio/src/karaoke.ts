// Mô hình lời Karaoke: mỗi câu gồm các từ có (start, end) riêng, giống cấu trúc segments/words của backend local_studio.
export interface KWord { text: string; start: number; end: number }
export interface KLine { id: string; words: KWord[]; sep: string; est?: boolean }
export const MIN = 0.02;
let seq = 0;
export const lid = () => `L${Date.now().toString(36)}${(++seq).toString(36)}`;
export const r3 = (x: number) => Math.round(x * 1000) / 1000;
export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
export const lStart = (l: KLine) => l.words[0].start;
export const lEnd = (l: KLine) => l.words[l.words.length - 1].end;
export const lText = (l: KLine) => l.words.map((w) => w.text).join(l.sep);
const CJK = /[\u3040-\u30ff\u3400-\u9fff]/;
export const guessSep = (words: string[]) => (words.length > 0 && words.every((w) => CJK.test(w)) ? '' : ' ');

export function splitWords(text: string, lang = 'ja'): { words: string[]; sep: string } {
  const s = text.trim().replace(/\s+/g, ' ');
  if (!s) return { words: [], sep: ' ' };
  if (s.includes(' ')) return { words: s.split(' '), sep: ' ' };
  const out: string[] = [];
  if (typeof Intl !== 'undefined' && 'Segmenter' in Intl) {
    for (const x of new Intl.Segmenter(lang, { granularity: 'word' }).segment(s)) { if (!x.isWordLike && out.length) out[out.length - 1] += x.segment; else out.push(x.segment); }
  } else out.push(...Array.from(s));
  return { words: out.length ? out : [s], sep: '' };
}
const weight = (w: string) => Math.max(1, Array.from(w).length);
export function evenWords(texts: string[], start: number, end: number): KWord[] {
  const span = Math.max(end - start, MIN * texts.length), total = texts.reduce((a, t) => a + weight(t), 0); let acc = 0;
  return texts.map((text) => { const a = start + (span * acc) / total; acc += weight(text); return { text, start: r3(a), end: r3(start + (span * acc) / total) }; });
}
export function makeLine(text: string, start: number, end: number, lang?: string): KLine | null {
  const { words, sep } = splitWords(text, lang); if (!words.length) return null;
  return { id: lid(), words: evenWords(words, start, end), sep, est: true };
}
/** Return only sung TXT lines. Preserve visible spelling, accents and punctuation.
 * Bracketed [Verse]/[Chorus]/[sound] directions are not lyrics, even inline.
 */
export function referenceRows(text: string): string[] {
  return text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').split('\n').flatMap((row) => {
    let depth = 0, visible = '';
    for (const c of row.replace(/\\+\s*$/, '')) {
      if (c === '[') { if (depth++ === 0) visible += ' '; }
      else if (c === ']' && depth > 0) depth--;
      else if (depth === 0) visible += c;
    }
    const cleaned = visible.trim().replace(/\s+/g, ' ');
    return cleaned && /[\p{L}\p{N}]/u.test(cleaned) ? [cleaned] : [];
  });
}
/** Use only to check if AI returned exactly the same lyrics, ignoring spacing/tokenization. */
export function canonicalReference(text: string): string {
  return referenceRows(text).join('').normalize('NFC').replace(/\s+/g, '');
}
export type ReferenceMatch = { ok: true; lines: KLine[] } | { ok: false; message: string };
/** Correct Whisper spelling without sacrificing trusted word timestamps.
 * Refuse mismatched line/word counts; forcing timing by equal spacing would silently
 * replace accurate manual timing with fabricated timing.
 */
export function overlayReferenceText(timed: KLine[], reference: string, language?: string): ReferenceMatch {
  const rows = referenceRows(reference);
  if (!rows.length) return { ok: false, message: 'TXT không có câu hát hợp lệ.' };
  if (rows.length !== timed.length)
    return { ok: false, message: 'TXT có ' + rows.length + ' câu, nhưng bản căn thời gian có ' + timed.length + ' câu. Hãy căn lại bằng Auto Karaoke → TXT chuẩn.' };
  const mapped: KLine[] = [];
  for (let i = 0; i < rows.length; i++) {
    const tokens = splitWords(rows[i], language);
    const original = timed[i];
    if (tokens.words.length !== original.words.length)
      return { ok: false, message: 'Câu ' + (i + 1) + ': TXT có ' + tokens.words.length +
        ' từ, nhưng mốc hiện tại có ' + original.words.length +
        ' từ. Để giữ đúng thời gian, hãy dùng Auto Karaoke → TXT chuẩn để căn lại.' };
    mapped.push({
      ...original, sep: tokens.sep,
      words: original.words.map((w, j) => ({ ...w, text: tokens.words[j] })),
    });
  }
  return { ok: true, lines: mapped };
}
export function plainToLines(text: string, duration: number, lang?: string): KLine[] {
  const rows = referenceRows(text);
  const wt = rows.map(weight), total = wt.reduce((a, b) => a + b, 0) || 1; let acc = 0;
  return rows.flatMap((r, i) => { const a = (duration * acc) / total; acc += wt[i]; const l = makeLine(r, a, (duration * acc) / total, lang); return l ? [l] : []; });
}

// ---- chỉnh sửa (hàm thuần, trả về mảng mới) ----
export const edgeGet = (l: KLine, idx: number) => (idx % 2 === 0 ? l.words[idx / 2].start : l.words[(idx - 1) / 2].end);
/** Kéo một mép: idx chẵn = đầu từ i/2, idx lẻ = cuối từ (idx-1)/2. Hai mép trùng nhau (≤2ms) được kéo cùng nhau. */
export function moveEdge(lines: KLine[], id: string, idx: number, v: number): KLine[] {
  const k = lines.findIndex((l) => l.id === id); if (k < 0) return lines;
  const l = lines[k], n2 = l.words.length * 2; if (idx < 0 || idx >= n2) return lines;
  const E = Array.from({ length: n2 }, (_, i) => edgeGet(l, i)); let a = idx, b = idx;
  if (idx % 2 === 1 && idx + 1 < n2 && Math.abs(E[idx + 1] - E[idx]) <= 0.002) b = idx + 1;
  else if (idx % 2 === 0 && idx > 0 && Math.abs(E[idx] - E[idx - 1]) <= 0.002) a = idx - 1;
  const lo = a > 0 ? E[a - 1] + ((a - 1) % 2 === 0 ? MIN : 0) : k > 0 ? lEnd(lines[k - 1]) : 0;
  const hi = b < n2 - 1 ? E[b + 1] - ((b + 1) % 2 === 1 ? MIN : 0) : k < lines.length - 1 ? lStart(lines[k + 1]) : Infinity;
  if (hi < lo) return lines;
  const nv = r3(clamp(v, lo, hi)), words = l.words.map((w) => ({ ...w }));
  for (let i = a; i <= b; i++) { if (i % 2 === 0) words[i >> 1].start = nv; else words[i >> 1].end = nv; }
  return lines.map((x, j) => (j === k ? { ...x, words, est: false } : x));
}
export function shiftLine(lines: KLine[], id: string, dt: number): KLine[] {
  const k = lines.findIndex((l) => l.id === id); if (k < 0) return lines; const l = lines[k];
  const lo = (k > 0 ? lEnd(lines[k - 1]) : 0) - lStart(l), hi = (k < lines.length - 1 ? lStart(lines[k + 1]) : Infinity) - lEnd(l);
  if (hi < lo) return lines; const d = clamp(dt, lo, hi);
  return lines.map((x, j) => (j === k ? { ...x, words: x.words.map((w) => ({ ...w, start: r3(w.start + d), end: r3(w.end + d) })) } : x));
}
export const shiftAll = (lines: KLine[], dt: number): KLine[] => {
  const d = lines.length ? Math.max(dt, -lStart(lines[0])) : 0;
  return lines.map((l) => ({ ...l, words: l.words.map((w) => ({ ...w, start: r3(w.start + d), end: r3(w.end + d) })) }));
};
export function editText(lines: KLine[], id: string, text: string, lang?: string): KLine[] {
  const k = lines.findIndex((l) => l.id === id); if (k < 0) return lines; const l = lines[k], { words, sep } = splitWords(text, lang); if (!words.length) return lines;
  const nw = words.length === l.words.length ? l.words.map((w, i) => ({ ...w, text: words[i] })) : evenWords(words, lStart(l), lEnd(l));
  return lines.map((x, j) => (j === k ? { ...x, words: nw, sep, est: words.length === l.words.length ? x.est : true } : x));
}
export function distribute(lines: KLine[], id: string): KLine[] {
  return lines.map((l) => (l.id === id ? { ...l, words: evenWords(l.words.map((w) => w.text), lStart(l), lEnd(l)), est: true } : l));
}
export const removeLine = (lines: KLine[], id: string) => lines.filter((l) => l.id !== id);
export function insertAfter(lines: KLine[], afterId: string | undefined, text: string, lang?: string): { lines: KLine[]; id?: string } {
  const k = afterId ? lines.findIndex((l) => l.id === afterId) : lines.length - 1;
  const start = k >= 0 ? lEnd(lines[k]) + 0.1 : 0, next = lines[k + 1], end = Math.min(start + 3, next ? lStart(next) - 0.02 : Infinity);
  if (end - start < MIN * 2) return { lines };
  const nl = makeLine(text, start, end, lang); if (!nl) return { lines };
  return { lines: [...lines.slice(0, k + 1), nl, ...lines.slice(k + 1)], id: nl.id };
}
/** Câu đang hiển thị tại thời điểm t (có chờ trước 0,4s và giữ sau 0,25s). */
export function lineAt(lines: KLine[], t: number): number {
  let best = -1; for (let i = 0; i < lines.length; i++) { if (lStart(lines[i]) - 0.4 <= t && t <= lEnd(lines[i]) + 0.25) best = i; else if (lStart(lines[i]) - 0.4 > t) break; }
  return best;
}
export const wordFill = (w: KWord, t: number) => clamp((t - w.start) / Math.max(w.end - w.start, 0.001), 0, 1);

// ---- cầu nối với backend local_studio: segments[{start,end,words[{text,start,end}]}] ----
export interface Segment { start: number; end: number; words: { text: string; start: number; end: number }[] }
export const fromSegments = (segs: Segment[]): KLine[] => segs.filter((s) => s.words?.length).map((s) => {
  const texts = s.words.map((w) => w.text); return { id: lid(), sep: guessSep(texts), words: s.words.map((w) => ({ text: w.text, start: w.start, end: w.end })) };
});
export const toSegments = (lines: KLine[], offset = 0): Segment[] => lines.map((l) => ({
  start: r3(Math.max(0, lStart(l) + offset)), end: r3(lEnd(l) + offset), words: l.words.map((w) => ({ text: w.text, start: r3(Math.max(0, w.start + offset)), end: r3(Math.max(0, w.end + offset)) })),
}));
/** Kiểm tra giống luật của backend trước khi lưu, trả về danh sách lỗi tiếng Việt. */
export function validateForBackend(lines: KLine[], duration?: number, offset = 0): string[] {
  const errs: string[] = []; let cursor = 0;
  lines.forEach((l, i) => {
    const n = `Câu ${i + 1}`; let c = lStart(l) + offset;
    if (lStart(l) + offset < -0.0005) errs.push(`${n}: bắt đầu trước 0 giây.`);
    if (lStart(l) + offset < cursor - 0.001) errs.push(`${n}: chồng thời gian với câu trước.`);
    for (const w of l.words) { if (w.end <= w.start) errs.push(`${n}: từ "${w.text}" có thời gian kết thúc không lớn hơn bắt đầu.`); if (w.start + offset < c - 0.001) errs.push(`${n}: từ "${w.text}" chồng từ trước.`); c = w.end + offset; }
    cursor = lEnd(l) + offset;
  });
  if (duration && lines.length && cursor > duration + 0.1) errs.push('Lời vượt quá thời lượng bài hát.');
  return [...new Set(errs)];
}
