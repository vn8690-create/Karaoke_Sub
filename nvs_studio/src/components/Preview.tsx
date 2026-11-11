import { useEffect, useRef, useState } from 'react';
import { Grid3x3, Maximize, Pause, Play, SkipBack, StepBack, StepForward, Square } from 'lucide-react';
import { useStudio, type Clip } from '../store';
import { syncAudio } from '../media';
import { useKaraoke } from '../karaokeStore';
import { lineAt } from '../karaoke';
import { drawKaraoke } from './karaokeDraw';

const SIZES: Record<string, [number, number]> = { '16:9': [960, 540], '9:16': [304, 540], '1:1': [540, 540], '4:3': [720, 540] };
const cache = new Map<string, HTMLImageElement>();
const getImg = (src: string, redraw: () => void) => { let i = cache.get(src); if (!i) { i = new Image(); i.onload = redraw; i.src = src; cache.set(src, i); } return i.complete && i.naturalWidth ? i : null; };
export const fmt = (t: number) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}.${String(Math.floor((t % 1) * 100)).padStart(2, '0')}`;
const end = () => Math.max(0, ...useStudio.getState().clips.map((c) => c.start + c.dur));

export default function Preview() {
  const s = useStudio(); const kl = useKaraoke(); const ref = useRef<HTMLCanvasElement>(null); const wrap = useRef<HTMLDivElement>(null); const [avail, setAvail] = useState({ w: 600, h: 300 }); const [tick, setTick] = useState(0); const [w, h] = SIZES[s.aspect] ?? SIZES['16:9'];
  useEffect(() => {
    const cv = ref.current; const ctx = cv?.getContext('2d'); if (!cv || !ctx) return;
    cv.width = w; cv.height = h; ctx.fillStyle = '#000'; ctx.fillRect(0, 0, w, h);
    const hidden = (c: Clip) => s.tracks.find((t) => t.id === c.track)?.hide; const live = (c: Clip) => !hidden(c) && s.playhead >= c.start && s.playhead < c.start + c.dur;
    for (const c of s.clips.filter((x) => x.kind === 'video' && live(x))) {
      const m = s.media.find((x) => x.url === c.src); const im = m?.kind === 'image' && c.src ? getImg(c.src, () => setTick((n) => n + 1)) : null;
      if (im) { const r = Math.max(w / im.width, h / im.height) * c.scale; ctx.globalAlpha = c.opacity; ctx.drawImage(im, w * c.x - im.width * r / 2, h * c.y - im.height * r / 2, im.width * r, im.height * r); ctx.globalAlpha = 1; }
      else { ctx.fillStyle = '#9aa0c8'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center'; ctx.fillText('Video: xem trước khung hình chưa hỗ trợ ở bản này', w / 2, h / 2); }
    }
    if (kl.lines.length) drawKaraoke(ctx, kl.lines, lineAt(kl.lines, s.playhead - kl.offset), s.playhead - kl.offset, w, h, kl.style);
    const L = kl.lines.length ? undefined : s.clips.find((c) => c.kind === 'lyrics' && c.text && live(c));
    if (L?.text) {
      const p = (s.playhead - L.start) / L.dur, fs = h * .07 * L.scale; ctx.font = `700 ${fs}px "Segoe UI","Yu Gothic UI",sans-serif`; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      const tw = ctx.measureText(L.text).width, x = w * L.x - tw / 2, y = h * L.y; ctx.globalAlpha = L.opacity; ctx.lineWidth = fs / 6; ctx.strokeStyle = '#000'; ctx.strokeText(L.text, x, y);
      ctx.fillStyle = '#fff'; ctx.fillText(L.text, x, y); ctx.save(); ctx.beginPath(); ctx.rect(x, y - fs, tw * Math.min(1, Math.max(0, p)), fs * 2); ctx.clip(); ctx.fillStyle = '#22d3ee'; ctx.fillText(L.text, x, y); ctx.restore(); ctx.globalAlpha = 1;
    }
    ctx.strokeStyle = 'rgba(255,255,255,.25)'; ctx.lineWidth = 1;
    if (s.grid) for (let i = 1; i < 3; i++) { ctx.beginPath(); ctx.moveTo(w * i / 3, 0); ctx.lineTo(w * i / 3, h); ctx.moveTo(0, h * i / 3); ctx.lineTo(w, h * i / 3); ctx.stroke(); }
    if (s.safe) { ctx.setLineDash([6, 4]); ctx.strokeRect(w * .05, h * .05, w * .9, h * .9); ctx.setLineDash([]); }
  }, [s.playhead, s.clips, s.tracks, s.media, s.aspect, s.grid, s.safe, tick, w, h, kl.lines, kl.offset, kl.style]);
  useEffect(() => { const el = wrap.current; if (!el) return; const f = () => setAvail({ w: Math.max(60, el.clientWidth - 24), h: Math.max(60, el.clientHeight - 24) }); const ro = new ResizeObserver(f); ro.observe(el); f(); return () => ro.disconnect(); }, []);
  const sc = Math.max(0.05, Math.min(avail.w / w, avail.h / h));
  useEffect(() => {
    if (!s.playing) { syncAudio(false, 0); return; }
    let last = performance.now(), id = 0;
    const loop = (now: number) => { const st = useStudio.getState(), tt = st.playhead + (now - last) / 1000; last = now;
      if (tt >= end()) { st.set({ playhead: end(), playing: false }); return; } st.set({ playhead: tt }); syncAudio(true, tt); id = requestAnimationFrame(loop); };
    id = requestAnimationFrame(loop); return () => cancelAnimationFrame(id);
  }, [s.playing]);
  const seek = (t: number) => s.set({ playhead: Math.max(0, Math.min(end(), t)), playing: false });
  return (
    <section className="flex-1 min-w-0 flex flex-col bg-ink">
      <div className="flex items-center gap-1 px-2 py-1 border-b border-line">
        {Object.keys(SIZES).map((a) => <button key={a} className={`btn !py-0.5 ${s.aspect === a ? '!border-vio' : ''}`} onClick={() => s.set({ aspect: a })}>{a}</button>)}
        <span className="flex-1" />
        <button className={`btn !py-0.5 ${s.grid ? '!border-cy' : ''}`} title="Lưới 3x3" onClick={() => s.set({ grid: !s.grid })}><Grid3x3 size={14} /></button>
        <button className={`btn !py-0.5 ${s.safe ? '!border-cy' : ''}`} title="Vùng an toàn" onClick={() => s.set({ safe: !s.safe })}><Square size={14} /></button>
        <button className="btn !py-0.5" title="Toàn màn hình" onClick={() => void ref.current?.requestFullscreen()}><Maximize size={14} /></button>
      </div>
      <div ref={wrap} className="flex-1 min-h-0 grid place-items-center p-3 overflow-hidden"><canvas ref={ref} className="rounded-md border border-line" style={{ width: w * sc, height: h * sc }} /></div>
      <div className="flex items-center justify-center gap-2 py-2 border-t border-line">
        <button className="btn" title="Về đầu" onClick={() => seek(0)}><SkipBack size={15} /></button>
        <button className="btn" title="Lùi 1 khung" onClick={() => seek(s.playhead - 1 / 30)}><StepBack size={15} /></button>
        <button className="btn pri" title="Phát / Dừng (Space)" onClick={() => s.set({ playing: !s.playing })}>{s.playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <button className="btn" title="Tiến 1 khung" onClick={() => seek(s.playhead + 1 / 30)}><StepForward size={15} /></button>
        <span className="font-mono text-cy w-24 text-center">{fmt(s.playhead)}</span>
      </div>
    </section>
  );
}
