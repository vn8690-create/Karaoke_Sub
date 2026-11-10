import { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, Lock, Magnet, Scissors, Trash2, Unlock, Volume2, VolumeX } from 'lucide-react';
import { snapTime, useStudio, type Clip, type Kind } from '../store';
import { fmt } from './Preview';

const ROW = 44, HEAD = 132;
const COLORS: Record<Kind, string> = { video: '#6d4ad6', audio: '#0e7490', vocal: '#be185d', lyrics: '#4f46e5', fx: '#b45309' };

function Wave({ c }: { c: Clip }) {
  const m = useStudio.getState().media.find((x) => x.url === c.src); if (!m?.peaks) return null;
  const N = m.peaks.length, a = Math.floor((c.off / m.dur) * N), b = Math.min(N, Math.ceil(((c.off + c.dur) / m.dur) * N)), sl = m.peaks.slice(a, b); if (sl.length < 2) return null;
  const up = sl.map((p, i) => `${(i / (sl.length - 1)) * 100},${20 - p * 18}`), dn = sl.map((p, i) => `${(i / (sl.length - 1)) * 100},${20 + p * 18}`).reverse();
  return <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="absolute inset-0 w-full h-full opacity-70"><polygon points={[...up, ...dn].join(' ')} fill="#67e8f9" /></svg>;
}

export default function Timeline() {
  const s = useStudio(); const rows = useRef<HTMLDivElement>(null); const [menu, setMenu] = useState<{ x: number; y: number; id: string } | null>(null);
  useEffect(() => { const close = () => setMenu(null); window.addEventListener('pointerdown', close); return () => window.removeEventListener('pointerdown', close); }, []);
  const total = Math.max(30, ...s.clips.map((c) => c.start + c.dur + 5)), width = total * s.zoom, step = s.zoom >= 100 ? 1 : s.zoom >= 40 ? 2 : s.zoom >= 20 ? 5 : 10;
  const ticks: number[] = []; for (let i = 0; i <= total; i += step) ticks.push(i);
  const seek = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect(), z = s.zoom, go = (x: number) => useStudio.getState().set({ playing: false, playhead: Math.max(0, (x - r.left) / z) }); go(e.clientX);
    const mv = (ev: PointerEvent) => go(ev.clientX), up = () => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  };
  const down = (e: React.PointerEvent, c: Clip, mode: 'move' | 'r') => {
    e.stopPropagation(); const st = useStudio.getState(); st.set({ sel: c.id }); if (st.tracks.find((t) => t.id === c.track)?.lock) return;
    st.commit(); const x0 = e.clientX, s0 = c.start, d0 = c.dur, top = rows.current?.getBoundingClientRect().top ?? 0;
    const mv = (ev: PointerEvent) => {
      const g = useStudio.getState(), dt = (ev.clientX - x0) / g.zoom, th = 8 / g.zoom;
      const tg = [g.playhead, 0, ...g.clips.filter((k) => k.id !== c.id).flatMap((k) => [k.start, k.start + k.dur])];
      if (mode === 'move') {
        let ns = Math.max(0, s0 + dt);
        if (g.snap) { const a = snapTime(ns, tg, th), b = snapTime(ns + d0, tg, th) - d0; ns = a !== ns ? a : b; }
        const tr = g.tracks[Math.floor((ev.clientY - top) / ROW)];
        g.patch(c.id, { start: Math.max(0, ns), ...(tr && tr.kind === c.kind && !tr.lock ? { track: tr.id } : {}) });
      } else { let nd = Math.max(.2, d0 + dt); if (g.snap) nd = Math.max(.2, snapTime(s0 + nd, tg, th) - s0); g.patch(c.id, { dur: nd }); }
    };
    const up = () => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  };
  const drop = (e: React.DragEvent<HTMLDivElement>, trackId: string) => {
    e.preventDefault(); const st = useStudio.getState(); const m = st.media.find((x) => x.id === e.dataTransfer.getData('text/plain')); const tr = st.tracks.find((x) => x.id === trackId); if (!m || !tr) return;
    const ok = m.kind === 'audio' ? tr.kind === 'audio' || tr.kind === 'vocal' : tr.kind === 'video'; if (!ok) { st.notify('Loại file không khớp với track này.'); return; } if (tr.lock) { st.notify('Track đang khoá.'); return; }
    const r = e.currentTarget.getBoundingClientRect(); st.addClip({ track: tr.id, start: Math.max(0, (e.clientX - r.left) / st.zoom), dur: m.dur, off: 0, label: m.name, kind: tr.kind, src: m.url, x: .5, y: .5, scale: 1, opacity: 1 });
  };
  return (
    <section style={{ height: s.tlH }} className="bg-pane border-t border-line flex flex-col shrink-0">
      <div className="flex items-center gap-2 px-2 py-1 border-b border-line">
        <button className="btn !py-0.5" title="Cắt tại playhead (S)" disabled={!s.sel} onClick={() => s.sel && s.split(s.sel, s.playhead)}><Scissors size={14} />Cắt</button>
        <button className="btn !py-0.5" title="Xoá (Delete)" disabled={!s.sel} onClick={() => s.sel && s.remove(s.sel)}><Trash2 size={14} />Xoá</button>
        <button className={`btn !py-0.5 ${s.snap ? '!border-cy' : ''}`} title="Bám mép clip và playhead" onClick={() => s.set({ snap: !s.snap })}><Magnet size={14} />Snap</button>
        <span className="font-mono text-cy">{fmt(s.playhead)}</span><span className="flex-1" /><span className="text-mute">Zoom</span>
        <input type="range" min={10} max={200} value={s.zoom} onChange={(e) => s.set({ zoom: Number(e.target.value) })} className="w-32 accent-[#8b5cf6]" aria-label="Zoom timeline" />
      </div>
      <div className="flex-1 overflow-auto">
        <div style={{ width: HEAD + width }} className="relative">
          <div className="flex sticky top-0 z-30">
            <div style={{ width: HEAD }} className="sticky left-0 bg-pane border-r border-b border-line h-6 z-30 shrink-0" />
            <div onPointerDown={seek} className="relative h-6 border-b border-line bg-pane2 cursor-text shrink-0" style={{ width }}>
              {ticks.map((t) => <span key={t} className="absolute top-0 h-full border-l border-line text-[10px] text-mute pl-1" style={{ left: t * s.zoom }}>{t}s</span>)}</div>
          </div>
          <div ref={rows}>{s.tracks.map((t) => (
            <div key={t.id} className="flex" style={{ height: ROW }}>
              <div style={{ width: HEAD }} className="sticky left-0 z-20 bg-pane border-r border-b border-line px-2 flex items-center gap-1 shrink-0">
                <span className="flex-1 truncate text-[11px]">{t.name}</span>
                <button title="Tắt tiếng" onClick={() => s.toggle(t.id, 'mute')} className={t.mute ? 'text-mag' : 'text-mute'}>{t.mute ? <VolumeX size={13} /> : <Volume2 size={13} />}</button>
                <button title="Khoá track" onClick={() => s.toggle(t.id, 'lock')} className={t.lock ? 'text-mag' : 'text-mute'}>{t.lock ? <Lock size={13} /> : <Unlock size={13} />}</button>
                <button title="Ẩn track" onClick={() => s.toggle(t.id, 'hide')} className={t.hide ? 'text-mag' : 'text-mute'}>{t.hide ? <EyeOff size={13} /> : <Eye size={13} />}</button>
              </div>
              <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => drop(e, t.id)} className={`relative border-b border-line shrink-0 ${t.hide ? 'opacity-40' : ''}`} style={{ width }}>
                {s.clips.filter((c) => c.track === t.id).map((c) => (
                  <div key={c.id} onPointerDown={(e) => down(e, c, 'move')} onContextMenu={(e) => { e.preventDefault(); useStudio.getState().set({ sel: c.id }); setMenu({ x: e.clientX, y: e.clientY, id: c.id }); }}
                    className={`absolute top-1 bottom-1 rounded-md overflow-hidden border text-[11px] px-1 leading-[34px] truncate ${t.lock ? 'cursor-not-allowed' : 'cursor-grab'} ${s.sel === c.id ? 'border-white' : 'border-black/30'}`}
                    style={{ left: c.start * s.zoom, width: Math.max(4, c.dur * s.zoom), background: COLORS[c.kind] }}>
                    <Wave c={c} /><span className="relative">{c.label}</span>
                    <div onPointerDown={(e) => down(e, c, 'r')} className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize bg-white/30" title="Kéo để đổi độ dài" /></div>))}
              </div>
            </div>))}</div>
          <div className="absolute top-0 bottom-0 w-px bg-mag pointer-events-none z-40" style={{ left: HEAD + s.playhead * s.zoom }} />
        </div>
      </div>
      {menu && <div onPointerDown={(e) => e.stopPropagation()} className="fixed z-50 bg-pane2 border border-line rounded-lg p-1 shadow-xl flex flex-col" style={{ left: menu.x, top: menu.y }}>
        <button className="btn !border-transparent" onClick={() => { s.split(menu.id, s.playhead); setMenu(null); }}><Scissors size={13} />Cắt tại playhead</button>
        <button className="btn !border-transparent" onClick={() => { s.remove(menu.id); setMenu(null); }}><Trash2 size={13} />Xoá clip</button></div>}
    </section>
  );
}
