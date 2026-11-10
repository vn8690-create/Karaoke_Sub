import { clamp, lEnd, lStart, wordFill, type KLine } from '../karaoke';
const c01 = (x: number) => clamp(x, 0, 1);
export type Effect = 'sweep' | 'pop' | 'glow' | 'bounce' | 'type' | 'fade';
export interface KStyle { font: string; size: number; fill: string; unsung: string; outline: string; y: number; effect: Effect; next: boolean }
export const FONTS: Record<string, string> = { 'Mặc định': '"Segoe UI","Yu Gothic UI","Noto Sans",sans-serif', 'Bo tròn': '"Trebuchet MS","Hiragino Maru Gothic ProN",Verdana,sans-serif', 'Có chân': 'Georgia,"Hiragino Mincho ProN","Times New Roman",serif', 'Đậm mạnh': '"Arial Black","Arial Rounded MT Bold",Arial,sans-serif' };
export const EFFECTS: Record<Effect, string> = { sweep: 'Tô quét theo từ', pop: 'Từ đang hát phóng to', glow: 'Phát sáng', bounce: 'Từ đang hát nhún', type: 'Hiện dần như gõ chữ', fade: 'Câu mờ vào/ra' };
export const DEFAULT_STYLE: KStyle = { font: FONTS['Mặc định'], size: 7, fill: '#22d3ee', unsung: '#ffffff', outline: '#000000', y: 0.82, effect: 'sweep', next: true };

/** Vẽ một câu Karaoke tại thời điểm t: mỗi từ được tô đúng theo start/end của chính nó. */
export function drawKaraoke(g: CanvasRenderingContext2D, lines: KLine[], idx: number, t: number, w: number, h: number, st: KStyle) {
  if (idx < 0 || !lines[idx]) return;
  const l = lines[idx]; let fs = (h * st.size) / 100;
  const measure = (size: number) => { g.font = `700 ${size}px ${st.font}`; const sp = l.sep ? g.measureText(l.sep).width : 0; const ws = l.words.map((x) => g.measureText(x.text).width); return { sp, ws, total: ws.reduce((a, b) => a + b, 0) + sp * (l.words.length - 1) }; };
  let m = measure(fs); if (m.total > w * 0.92) { fs *= (w * 0.92) / m.total; m = measure(fs); }
  const alpha = st.effect === 'fade' ? c01((t - (lStart(l) - 0.4)) / 0.3) * c01((lEnd(l) + 0.25 - t) / 0.25) : 1;
  g.save(); g.globalAlpha = alpha; g.textBaseline = 'middle'; g.textAlign = 'center'; g.lineJoin = 'round'; g.lineWidth = fs / 7; g.strokeStyle = st.outline;
  let x = (w - m.total) / 2; const y = h * st.y;
  l.words.forEach((wd, i) => {
    const ww = m.ws[i], f = wordFill(wd, t), singing = t >= wd.start && t < wd.end; const cx = x + ww / 2; x += ww + m.sp;
    if (st.effect === 'type' && t < wd.start) return;
    const k = st.effect === 'pop' && singing ? 1 + 0.25 * Math.sin(f * Math.PI) : 1, dy = st.effect === 'bounce' && singing ? -Math.sin(f * Math.PI) * fs * 0.18 : 0;
    g.save(); g.translate(cx, y + dy); g.scale(k, k); g.font = `700 ${fs}px ${st.font}`;
    g.strokeText(wd.text, 0, 0); g.fillStyle = st.unsung; g.fillText(wd.text, 0, 0);
    if (f > 0) { g.save(); g.beginPath(); g.rect(-ww / 2 - fs * 0.1, -fs, (ww + fs * 0.2) * (f >= 1 ? 1 : f), fs * 2); g.clip(); if (st.effect === 'glow') { g.shadowColor = st.fill; g.shadowBlur = fs * 0.5; } g.fillStyle = st.fill; g.fillText(wd.text, 0, 0); g.restore(); }
    g.restore();
  });
  const nx = lines[idx + 1];
  if (st.next && nx && st.effect !== 'type') { const s2 = fs * 0.6; g.font = `600 ${s2}px ${st.font}`; g.globalAlpha = alpha * 0.75; g.lineWidth = s2 / 7; const tx = nx.words.map((q) => q.text).join(nx.sep), yy = Math.min(h - s2, y + fs * 1.25); g.strokeText(tx, w / 2, yy, w * 0.9); g.fillStyle = st.unsung; g.fillText(tx, w / 2, yy, w * 0.9); }
  g.restore();
}
