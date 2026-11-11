// Đọc/ghi LRC, Enhanced LRC, SRT, ASS (có \k). Chỉ dùng mô hình KLine, không phụ thuộc giao diện.
import { MIN, guessSep, lEnd, lid, lStart, makeLine, r3, type KLine, type KWord } from './karaoke';

const p2 = (n: number) => String(n).padStart(2, '0');
export const fmtLRC = (t: number) => { const cs = Math.round(Math.max(0, t) * 100); return `${p2(Math.floor(cs / 6000))}:${p2(Math.floor(cs / 100) % 60)}.${p2(cs % 100)}`; };
export const fmtSRT = (t: number) => { const ms = Math.round(Math.max(0, t) * 1000); return `${p2(Math.floor(ms / 3600000))}:${p2(Math.floor(ms / 60000) % 60)}:${p2(Math.floor(ms / 1000) % 60)},${String(ms % 1000).padStart(3, '0')}`; };
export const fmtASS = (cs: number) => `${Math.floor(cs / 360000)}:${p2(Math.floor(cs / 6000) % 60)}:${p2(Math.floor(cs / 100) % 60)}.${p2(cs % 100)}`;
const frac = (f?: string) => (f ? Number(f.padEnd(3, '0').slice(0, 3)) / 1000 : 0);
const clean = (s: string) => s.replace(/^\uFEFF/, '');
export type Format = 'ass' | 'srt' | 'lrc' | 'plain';
const LRC_TS = /\[(\d+):(\d{1,2})(?:[.:](\d{1,3}))?\]/g, MARK = /<(\d+):(\d{1,2})(?:[.:](\d{1,3}))?>/;
export function detectFormat(src: string): Format {
  if (/^\s*\[(Script Info|Events|V4\+? Styles)\]/im.test(src)) return 'ass';
  if (/\d+:\d{2}:\d{2}[,.]\d{1,3}\s*-->/.test(src)) return 'srt';
  if (/\[\d+:\d{1,2}(?:[.:]\d{1,3})?\]/.test(src)) return 'lrc';
  return 'plain';
}

export function parseLRC(src: string): KLine[] {
  const rows: { t: number; text: string }[] = [];
  for (const row of clean(src).split(/\r?\n/)) {
    const stamps = [...row.matchAll(LRC_TS)]; if (!stamps.length) continue;
    const text = row.replace(LRC_TS, '');
    for (const m of (MARK.test(text) ? stamps.slice(0, 1) : stamps)) rows.push({ t: Number(m[1]) * 60 + Number(m[2]) + frac(m[3]), text });
  }
  rows.sort((a, b) => a.t - b.t); const out: KLine[] = [];
  rows.forEach((r, i) => {
    if (!r.text.trim()) return;
    const nextStart = rows[i + 1]?.t, fallbackEnd = Math.min(nextStart ?? Infinity, r.t + Math.min(8, Math.max(2, Array.from(r.text).length * 0.3)));
    if (!MARK.test(r.text)) { const l = makeLine(r.text, r.t, fallbackEnd); if (l) out.push(l); return; }
    const parts = r.text.split(/<(\d+:\d{1,2}(?:[.:]\d{1,3})?)>/), entries: { time: number; text: string }[] = [];
    if (parts[0].trim()) entries.push({ time: r.t, text: parts[0] });
    for (let j = 1; j < parts.length; j += 2) { const m = /(\d+):(\d{1,2})(?:[.:](\d{1,3}))?/.exec(parts[j])!; entries.push({ time: Number(m[1]) * 60 + Number(m[2]) + frac(m[3]), text: parts[j + 1] ?? '' }); }
    const words: (Omit<KWord, 'end'> & { end?: number })[] = []; let spaced = false;
    for (const e of entries) {
      if (/^\s|\s$/.test(e.text) && e.text.trim()) spaced = true;
      if (!e.text.trim()) { const last = words.at(-1); if (last && last.end === undefined) last.end = e.time; continue; }
      const last = words.at(-1); if (last && last.end === undefined) last.end = e.time;
      words.push({ text: e.text.trim(), start: e.time });
    }
    if (!words.length) return;
    const lastW = words.at(-1)!; if (lastW.end === undefined) lastW.end = Math.max(fallbackEnd, lastW.start + MIN);
    const fixed = words.map((w) => ({ text: w.text, start: r3(w.start), end: r3(Math.max(w.end!, w.start + 0.001)) }));
    out.push({ id: lid(), words: fixed, sep: spaced ? ' ' : guessSep(fixed.map((w) => w.text)) });
  });
  return out;
}
export function parseSRT(src: string): KLine[] {
  const out: KLine[] = [];
  for (const block of clean(src).replace(/\r/g, '').split(/\n{2,}/)) {
    const rows = block.split('\n'), i = rows.findIndex((r) => r.includes('-->')); if (i < 0) continue;
    const m = /(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})/.exec(rows[i]); if (!m) continue;
    const a = Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) + frac(m[4]), b = Number(m[5]) * 3600 + Number(m[6]) * 60 + Number(m[7]) + frac(m[8]);
    const l = makeLine(rows.slice(i + 1).join(' ').replace(/<[^>]+>/g, ''), a, Math.max(b, a + MIN)); if (l) out.push(l);
  }
  return out;
}
export function parseASS(src: string): KLine[] {
  let fmt: string[] = [], inEvents = false; const out: KLine[] = [];
  const cs = (s: string) => { const m = /(\d+):(\d{2}):(\d{2})[.](\d{1,2})/.exec(s.trim()); return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) + Number(m[4].padEnd(2, '0')) / 100 : NaN; };
  for (const row of clean(src).split(/\r?\n/)) {
    const t = row.trim(); if (/^\[.*\]$/.test(t)) { inEvents = /^\[events\]$/i.test(t); continue; } if (!inEvents) continue;
    if (/^format:/i.test(t)) { fmt = t.slice(7).split(',').map((s) => s.trim().toLowerCase()); continue; }
    if (!/^dialogue:/i.test(t)) continue;
    const n = fmt.length || 10, parts: string[] = []; let rest = t.slice(9).trimStart();
    for (let i = 0; i < n - 1; i++) { const c = rest.indexOf(','); if (c < 0) break; parts.push(rest.slice(0, c)); rest = rest.slice(c + 1); } parts.push(rest);
    const s0 = cs(parts[fmt.length ? fmt.indexOf('start') : 1] ?? ''), e0 = cs(parts[fmt.length ? fmt.indexOf('end') : 2] ?? ''); if (Number.isNaN(s0) || Number.isNaN(e0)) continue;
    const text = parts[parts.length - 1], blocks = text.split(/(\{[^}]*\})/); let dur: number | null = null, cursor = s0, spaced = false, hasK = false; const words: KWord[] = [];
    for (const b of blocks) {
      if (b.startsWith('{')) { const km = [...b.matchAll(/\\(?:k[fo]?|K)(\d+)/g)].at(-1); if (km) { dur = Number(km[1]) / 100; hasK = true; } continue; }
      const piece = b.replace(/\\[Nnh]/g, ' '); if (dur === null) continue;
      if (/^\s|\s$/.test(piece) && piece.trim()) spaced = true;
      if (!piece.trim()) cursor += dur; else { words.push({ text: piece.trim(), start: r3(cursor), end: r3(cursor + Math.max(dur, 0.01)) }); cursor += Math.max(dur, 0.01); }
      dur = null;
    }
    if (hasK && words.length) out.push({ id: lid(), words, sep: spaced ? ' ' : guessSep(words.map((w) => w.text)) });
    else { const l = makeLine(text.replace(/\{[^}]*\}/g, '').replace(/\\[Nnh]/g, ' '), s0, Math.max(e0, s0 + MIN)); if (l) out.push(l); }
  }
  return out;
}
export function parseAny(src: string): { format: Format; lines: KLine[] } {
  const format = detectFormat(src);
  return { format, lines: format === 'ass' ? parseASS(src) : format === 'srt' ? parseSRT(src) : format === 'lrc' ? parseLRC(src) : [] };
}

// ---- xuất ----
const text = (l: KLine) => l.words.map((w) => w.text).join(l.sep);
export function toLRC(lines: KLine[], offset = 0, enhanced = false): string {
  const T = (t: number) => fmtLRC(t + offset), out: string[] = [];
  lines.forEach((l, i) => {
    if (!enhanced) out.push(`[${T(lStart(l))}]${text(l)}`);
    else { let s = `[${T(lStart(l))}]`; l.words.forEach((w, j) => { if (j > 0 && w.start - l.words[j - 1].end >= 0.01) s += `<${T(l.words[j - 1].end)}>`; s += `<${T(w.start)}>${w.text}${j < l.words.length - 1 ? l.sep : ''}`; }); out.push(`${s}<${T(lEnd(l))}>`); }
    const next = lines[i + 1]; if (!enhanced && (!next || lStart(next) - lEnd(l) > 0.3)) out.push(`[${T(lEnd(l))}]`);
  });
  return out.join('\n') + '\n';
}
export function toSRT(lines: KLine[], offset = 0): string {
  return lines.map((l, i) => { const a = Math.max(0, lStart(l) + offset); let b = lEnd(l) + offset; if (b <= a) b = a + 0.001; return `${i + 1}\n${fmtSRT(a)} --> ${fmtSRT(b)}\n${text(l)}\n`; }).join('\n');
}
export const hexToASS = (hex: string) => { const h = hex.replace('#', ''); return `&H00${h.slice(4, 6)}${h.slice(2, 4)}${h.slice(0, 2)}`.toUpperCase(); };
export interface AssStyle { font: string; size: number; fill: string; unsung: string; outline: string }
export const DEFAULT_ASS: AssStyle = { font: 'Arial', size: 64, fill: '#22D3EE', unsung: '#FFFFFF', outline: '#000000' };
export function toASS(lines: KLine[], offset = 0, st: AssStyle = DEFAULT_ASS): string {
  const C = (t: number) => Math.round(Math.max(0, t + offset) * 100), rows = lines.map((l) => {
    let cur = C(lStart(l)); const start = cur; let body = '';
    l.words.forEach((w, i) => { const a = C(w.start), b = Math.max(a + 1, C(w.end)); if (a > cur) body += `{\\k${a - cur}}`; body += `{\\kf${b - a}}${w.text.replace(/[{}]/g, '')}${i < l.words.length - 1 ? l.sep : ''}`; cur = b; });
    return `Dialogue: 0,${fmtASS(start)},${fmtASS(cur)},Default,,0,0,0,karaoke,${body}`;
  });
  return `[Script Info]\nTitle: NVS Karaoke Studio PRO\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,${st.font},${st.size},${hexToASS(st.fill)},${hexToASS(st.unsung)},${hexToASS(st.outline)},&H64000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,80,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n${rows.join('\n')}\n`;
}
