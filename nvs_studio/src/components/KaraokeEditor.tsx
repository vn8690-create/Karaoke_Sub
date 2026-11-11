import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Play, Plus, Redo2, Save, Trash2, Undo2, Upload, Wand2 } from 'lucide-react';
import { useStudio } from '../store';
import { useKaraoke } from '../karaokeStore';
import { MOCK_TEXT } from '../adapters/mock';
import { BackendClient } from '../backend';
import { edgeGet, lEnd, lStart, lText, plainToLines, validateForBackend, wordFill, type KLine } from '../karaoke';
import { parseAny, toASS, toLRC, toSRT } from '../formats';
import { fmt } from './Preview';

const BH = 48;
const sec = (t: number) => t.toFixed(3) + ' s';
function dl(name: string, text: string) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' })); a.download = name; a.click(); }

export default function KaraokeEditor() {
  const k = useKaraoke(), m = useStudio();
  const scroller = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null), list = useRef<HTMLDivElement>(null), file = useRef<HTMLInputElement>(null);
  const drag = useRef<{ id: string; idx: number } | null>(null), seeking = useRef(false), lastNudge = useRef(0);
  const col = useRef<HTMLDivElement>(null); const [vw, setVw] = useState(800), [H, setH] = useState(170), [scroll, setScroll] = useState(0), [draft, setDraft] = useState<{ id: string; text: string } | null>(null), [add, setAdd] = useState('');
  const off = k.offset, Z = k.zoom, B1 = H - 16, B0 = B1 - BH, mid = (20 + B0 - 6) / 2, amp = Math.max(10, (B0 - 26) / 2 - 2);
  const audio = useMemo(() => { const c = m.clips.find((x) => x.kind === 'audio' && x.src); const med = c && m.media.find((x) => x.url === c.src); return c && med?.hp ? { c, hp: med.hp } : null; }, [m.clips, m.media]);
  const audioEnd = m.clips.filter((c) => c.kind === 'audio').reduce((a, c) => Math.max(a, c.start + c.dur), 0);
  const total = Math.max(10, k.lines.length ? lEnd(k.lines[k.lines.length - 1]) + off : 0, audioEnd) + 2, W = Math.ceil(total * Z);
  const X = (t: number) => t * Z - scroll;

  useEffect(() => { const el = scroller.current; if (!el) return; const f = () => { setVw(Math.max(200, el.clientWidth)); if (col.current) setH(Math.max(170, Math.min(420, col.current.clientHeight - 14 - 46))); }; const ro = new ResizeObserver(f); ro.observe(el); if (col.current) ro.observe(col.current); f(); return () => ro.disconnect(); }, []);
  useEffect(() => {
    const el = scroller.current; if (!el) return;
    const f = (e: WheelEvent) => { if (!e.ctrlKey) return; e.preventDefault(); const z = useKaraoke.getState().zoom, nz = Math.min(400, Math.max(30, z * (e.deltaY < 0 ? 1.15 : 1 / 1.15))), r = el.getBoundingClientRect(), tt = (e.clientX - r.left + el.scrollLeft) / z; useKaraoke.getState().set({ zoom: nz }); requestAnimationFrame(() => { el.scrollLeft = tt * nz - (e.clientX - r.left); }); };
    el.addEventListener('wheel', f, { passive: false }); return () => el.removeEventListener('wheel', f);
  }, []);
  useEffect(() => { if (!m.playing) return; const el = scroller.current; if (!el) return; const x = m.playhead * Z - el.scrollLeft; if (x > vw * 0.92 || x < 0) el.scrollLeft = Math.max(0, m.playhead * Z - vw * 0.3); }, [m.playhead, m.playing, Z, vw]);
  useEffect(() => { if (k.sel) list.current?.querySelector(`[data-id="${k.sel}"]`)?.scrollIntoView({ block: 'nearest' }); }, [k.sel]);

  useEffect(() => {
    const c = cv.current, g = c?.getContext('2d'); if (!c || !g) return;
    g.fillStyle = '#0b0e1a'; g.fillRect(0, 0, vw, H);
    const step = Z >= 240 ? 0.5 : Z >= 100 ? 1 : Z >= 40 ? 5 : 10; g.font = '10px sans-serif';
    for (let t = Math.floor(scroll / Z / step) * step; X(t) < vw; t += step) { const x = X(t); g.fillStyle = '#262c4a'; g.fillRect(x, 0, 1, H); g.fillStyle = '#8d94b8'; g.fillText(`${t}s`, x + 3, 11); }
    if (audio) { g.fillStyle = 'rgba(34,211,238,.55)'; const rate = 50; for (let px = 0; px < vw; px++) { const a = Math.floor(((px + scroll) / Z - audio.c.start + audio.c.off) * rate), b = Math.ceil(((px + 1 + scroll) / Z - audio.c.start + audio.c.off) * rate); let mx = 0; for (let i = Math.max(0, a); i < Math.min(audio.hp.length, Math.max(b, a + 1)); i++) if (audio.hp[i] > mx) mx = audio.hp[i]; if (mx > 0) g.fillRect(px, mid - mx * amp, 1, mx * amp * 2); } }
    else { g.fillStyle = '#8d94b8'; g.fillText('Chưa có sóng âm: nhập file nhạc vào track Nhạc để căn mốc theo âm thanh.', 10, mid); }
    const ph = m.playhead - off;
    k.lines.forEach((l) => {
      const s = X(lStart(l) + off), e = X(lEnd(l) + off); if (e < -10 || s > vw + 10) return; const sel = l.id === k.sel;
      g.fillStyle = sel ? '#33286b' : '#222749'; g.fillRect(s, B0, Math.max(1, e - s), B1 - B0);
      l.words.forEach((w, wi) => {
        const ws = X(w.start + off), we = X(w.end + off), bw = Math.max(1, we - ws - 1);
        g.fillStyle = sel ? '#6d4ad6' : '#3b4280'; g.fillRect(ws, B0 + 4, bw, B1 - B0 - 8);
        const f = wordFill(w, ph); if (f > 0) { g.fillStyle = 'rgba(34,211,238,.8)'; g.fillRect(ws, B0 + 4, bw * f, B1 - B0 - 8); }
        if (bw > 14) { g.save(); g.beginPath(); g.rect(ws, B0 + 4, bw, B1 - B0 - 8); g.clip(); g.fillStyle = '#fff'; g.font = '12px "Segoe UI","Yu Gothic UI",sans-serif'; g.fillText(w.text, ws + 3, B0 + 27); g.restore(); }
        if (sel) for (const idx of [wi * 2, wi * 2 + 1]) { const x = X(edgeGet(l, idx) + off); g.fillStyle = idx === k.selEdge ? '#ec4899' : 'rgba(232,234,246,.85)'; g.fillRect(x - 1, B0, 2, B1 - B0); }
      });
      if (l.est) { g.strokeStyle = '#f59e0b'; g.setLineDash([4, 3]); g.strokeRect(s + 0.5, B0 + 0.5, Math.max(1, e - s), B1 - B0); g.setLineDash([]); }
    });
    const px = X(m.playhead); g.fillStyle = '#ec4899'; g.fillRect(px, 0, 1.5, H);
  }, [k.lines, k.sel, k.selEdge, Z, scroll, vw, H, m.playhead, audio, off]); // eslint-disable-line react-hooks/exhaustive-deps

  const pt = (e: React.PointerEvent) => { const r = cv.current!.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const hit = (x: number, y: number) => {
    if (y < B0 - 4 || y > B1 + 4) return null; let best: { id: string; idx: number; d: number } | null = null;
    for (const l of k.lines) { if (X(lEnd(l) + off) < x - 8 || X(lStart(l) + off) > x + 8 + 0 && X(lStart(l) + off) > vw) continue; for (let i = 0; i < l.words.length * 2; i++) { const d = Math.abs(X(edgeGet(l, i) + off) - x); if (d <= 7 && (!best || d < best.d || (d === best.d && l.id === k.sel))) best = { id: l.id, idx: i, d }; } }
    return best;
  };
  const seek = (x: number) => m.set({ playhead: Math.max(0, (x + scroll) / Z) });
  const onDown = (e: React.PointerEvent) => {
    const { x, y } = pt(e), h = hit(x, y); (e.target as Element).setPointerCapture(e.pointerId); e.currentTarget.closest<HTMLElement>('[tabindex]')?.focus();
    if (h) { k.commit(); k.set({ sel: h.id, selEdge: h.idx }); drag.current = { id: h.id, idx: h.idx }; return; }
    const t = (x + scroll) / Z - off, l = y >= B0 && y <= B1 ? k.lines.find((q) => t >= lStart(q) && t <= lEnd(q)) : undefined;
    if (y >= B0 && y <= B1) k.set({ sel: l?.id, selEdge: undefined }); seeking.current = true; seek(x);
  };
  const onMove = (e: React.PointerEvent) => {
    const { x, y } = pt(e);
    if (drag.current) { const v = (x + scroll) / Z - off; k.moveEdge(drag.current.id, drag.current.idx, e.altKey ? v : Math.round(v * 100) / 100); return; }
    if (seeking.current) { seek(x); return; } cv.current!.style.cursor = hit(x, y) ? 'ew-resize' : 'default';
  };
  const onUp = () => { drag.current = null; seeking.current = false; };

  const selLine = k.lines.find((l) => l.id === k.sel), selIdx = k.lines.findIndex((l) => l.id === k.sel);
  const nudge = (d: number) => { if (!selLine || k.selEdge === undefined) return; const now = Date.now(); if (now - lastNudge.current > 700) k.commit(); lastNudge.current = now; k.moveEdge(selLine.id, k.selEdge, edgeGet(selLine, k.selEdge) + d); };
  const mark = () => {
    if (!selLine || k.selEdge === undefined) return; k.commit(); k.moveEdge(selLine.id, k.selEdge, useStudio.getState().playhead - off);
    const cur = useKaraoke.getState().lines.find((l) => l.id === selLine.id)!, n2 = cur.words.length * 2; let nx = k.selEdge + 1; while (nx < n2 && Math.abs(edgeGet(cur, nx) - edgeGet(cur, k.selEdge)) <= 0.002) nx++;
    if (nx < n2) k.set({ selEdge: nx }); else { const next = k.lines[selIdx + 1]; k.set(next ? { sel: next.id, selEdge: 0 } : { selEdge: undefined }); }
  };
  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).tagName === 'INPUT') return; const d = e.altKey ? 0.001 : e.shiftKey ? 0.1 : 0.01;
    if (e.key === 'ArrowLeft') { e.preventDefault(); nudge(-d); } else if (e.key === 'ArrowRight') { e.preventDefault(); nudge(d); }
    else if (e.key === 'm' || e.key === 'M') { e.preventDefault(); mark(); } else if ((e.key === 'Delete' || e.key === 'Backspace') && selLine && k.selEdge === undefined) { e.preventDefault(); k.remove(selLine.id); }
  };
  const audition = (l: KLine) => { m.set({ playhead: Math.max(0, lStart(l) + off - 0.3), playing: true }); k.set({ sel: l.id, auditionEnd: lEnd(l) + off + 0.2 }); };
  const onImport = async (f?: File) => {
    if (!f) return; const txt = await f.text(); if (txt.includes('\uFFFD')) m.notify('Cảnh báo: file có thể không phải UTF-8, chữ có dấu có thể lỗi.');
    const { format, lines } = parseAny(txt);
    if (lines.length) { k.load(lines, 'file', { title: f.name.replace(/\.[^.]+$/, '') }); m.notify(`Đã nhập ${lines.length} câu (${format.toUpperCase()}).${lines.some((l) => l.est) ? ' Mốc từng từ là ước lượng, hãy chỉnh trên waveform.' : ''}`); }
    else if (txt.trim()) { k.load(plainToLines(txt, audioEnd || k.duration || 180), 'file', { title: f.name.replace(/\.[^.]+$/, '') }); m.notify('File không có mốc thời gian: đã chia đều theo độ dài bài (ước lượng).'); } else m.notify('File rỗng hoặc không đọc được.');
  };
  const name = (k.title || 'karaoke').replace(/[^\w\u00C0-\u1EF9\u3040-\u9FFF-]+/g, '_');
  const exp = (kind: 'lrc' | 'elrc' | 'srt' | 'ass') => { if (!k.lines.length) { m.notify('Chưa có lời để xuất.'); return; } if (kind === 'lrc') dl(`${name}.lrc`, toLRC(k.lines, off)); else if (kind === 'elrc') dl(`${name}.enhanced.lrc`, toLRC(k.lines, off, true)); else if (kind === 'srt') dl(`${name}.srt`, toSRT(k.lines, off)); else dl(`${name}.ass`, toASS(k.lines, off, { font: 'Arial', size: 64, fill: k.style.fill, unsung: k.style.unsung, outline: k.style.outline })); };
  const save = async () => {
    const errs = validateForBackend(k.lines, k.duration, off); if (errs.length) { m.notify('Không lưu được: ' + errs[0]); return; }
    try { await new BackendClient().saveLyrics(k.projectId!, k.lines, off); k.bakeOffset(); k.markSaved(); m.notify('Đã lưu lời lên backend.'); } catch (e) { m.notify('Backend từ chối: ' + (e as Error).message); }
  };
  const btn = 'btn !py-0.5 !px-2';
  return (
    <div tabIndex={0} onKeyDown={onKey} className="flex flex-col flex-1 min-h-0 outline-none bg-pane">
      <div className="flex flex-wrap items-center gap-1.5 px-2 py-1 border-b border-line text-[12px]">
        <button className={btn} onClick={() => file.current?.click()} title="Nhập LRC, Enhanced LRC, SRT, ASS hoặc TXT"><Upload size={13} />Nhập</button>
        <input ref={file} type="file" accept=".lrc,.srt,.ass,.ssa,.txt" hidden onChange={(e) => { void onImport(e.target.files?.[0]); e.target.value = ''; }} />
        {(['lrc', 'elrc', 'srt', 'ass'] as const).map((f) => <button key={f} className={btn} disabled={!k.lines.length} onClick={() => exp(f)} title={`Xuất ${f === 'elrc' ? 'Enhanced LRC' : f.toUpperCase()}`}><Download size={13} />{f === 'elrc' ? 'LRC từng từ' : f.toUpperCase()}</button>)}
        <span className="w-px h-5 bg-line" />
        <button className={btn} disabled={!k.past.length} onClick={k.undo} title="Hoàn tác (Ctrl+Z)"><Undo2 size={13} /></button><button className={btn} disabled={!k.future.length} onClick={k.redo} title="Làm lại (Ctrl+Y)"><Redo2 size={13} /></button>
        <span className="w-px h-5 bg-line" />
        <label className="flex items-center gap-1 text-mute" title="Dương = lời hiện muộn hơn. Áp dụng cho preview và khi xuất.">Offset <input type="number" step={10} value={Math.round(off * 1000)} onChange={(e) => k.set({ offset: Number(e.target.value) / 1000 })} className="w-20 bg-ink border border-line rounded px-1 py-0.5 text-white" /> ms</label>
        <button className={btn} disabled={!off} onClick={k.bakeOffset} title="Ghi offset vào mốc thời gian (có thể hoàn tác)">Áp dụng</button>
        <label className="flex items-center gap-1 text-mute">Zoom <input type="range" min={30} max={400} value={Z} onChange={(e) => k.set({ zoom: Number(e.target.value) })} className="w-24 accent-[#8b5cf6]" /></label>
        <span className="flex-1" />
        {k.source !== 'none' && <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${k.source === 'mock' ? 'bg-amber-600' : 'bg-cyan-700'}`}>{k.source === 'mock' ? 'MOCK: DỮ LIỆU GIẢ LẬP' : k.source === 'backend' ? 'BACKEND' : 'TỪ FILE'}{k.dirty ? ' • chưa lưu' : ''}</span>}
        {k.projectId && <button className={`${btn} pri`} onClick={() => void save()} title="Lưu lời lên backend local_studio (PUT /lyrics)"><Save size={13} />Lưu backend</button>}
        <button className={btn} onClick={() => m.set({ wizard: true })}><Wand2 size={13} />Auto Karaoke</button>
      </div>
      <div className="flex flex-1 min-h-0">
        <div ref={list} className="w-72 shrink-0 overflow-auto border-r border-line">
          {!k.lines.length && <div className="p-4 text-mute leading-6">Chưa có lời.<div className="flex flex-col gap-2 mt-3">
            <button className="btn pri justify-center" onClick={() => file.current?.click()}><Upload size={14} />Nhập LRC / SRT / ASS / TXT</button>
            <button className="btn justify-center" onClick={() => m.set({ wizard: true })}><Wand2 size={14} />Auto Karaoke Wizard</button>
            <button className="btn justify-center" onClick={() => k.load(plainToLines(MOCK_TEXT.vi, audioEnd || 20), 'mock')}>Nạp dữ liệu mẫu [MOCK]</button></div></div>}
          {k.lines.map((l, i) => (
            <div key={l.id} data-id={l.id} onClick={() => k.set({ sel: l.id, selEdge: undefined })} className={`flex items-center gap-1 px-1.5 py-1 border-b border-line ${l.id === k.sel ? 'bg-[#33286b]' : 'hover:bg-pane2'}`}>
              <span className="w-5 text-right text-mute text-[10px]">{i + 1}</span>
              <button className="text-cy" title="Nghe thử câu này" onClick={(e) => { e.stopPropagation(); audition(l); }}><Play size={12} /></button>
              <input value={draft?.id === l.id ? draft.text : lText(l)} onFocus={() => { k.commit(); setDraft({ id: l.id, text: lText(l) }); }} onBlur={() => setDraft(null)}
                onChange={(e) => { setDraft({ id: l.id, text: e.target.value }); k.editText(l.id, e.target.value); }} className="flex-1 min-w-0 bg-transparent border border-transparent focus:border-vio rounded px-1" />
              {l.est && <span title="Mốc từng từ là ước lượng, hãy chỉnh trên waveform" className="text-amber-400">≈</span>}
              <span className="font-mono text-[10px] text-mute">{fmt(lStart(l) + off)}</span>
              <button className="text-mute hover:text-mag" title="Chia đều lại các từ" onClick={(e) => { e.stopPropagation(); k.distribute(l.id); }}>⇔</button>
              <button className="text-mute hover:text-mag" title="Xoá câu" onClick={(e) => { e.stopPropagation(); k.remove(l.id); }}><Trash2 size={12} /></button>
            </div>))}
          {!!k.lines.length && <div className="flex gap-1 p-1.5"><input value={add} onChange={(e) => setAdd(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && add.trim()) { k.insert(k.sel ?? k.lines.at(-1)?.id, add); setAdd(''); } }} placeholder="Thêm câu sau câu đang chọn…" className="flex-1 min-w-0 bg-ink border border-line rounded px-1.5 py-1" />
            <button className="btn !p-1" disabled={!add.trim()} onClick={() => { k.insert(k.sel ?? k.lines.at(-1)?.id, add); setAdd(''); }}><Plus size={13} /></button></div>}
        </div>
        <div ref={col} className="flex-1 min-w-0 min-h-0 flex flex-col">
          <div ref={scroller} onScroll={(e) => setScroll(e.currentTarget.scrollLeft)} className="overflow-x-auto overflow-y-hidden" style={{ height: H + 14 }}>
            <div style={{ width: W, height: H, position: 'relative' }}>
              <canvas ref={cv} width={vw} height={H} style={{ position: 'sticky', left: 0, display: 'block', touchAction: 'none' }} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} />
            </div>
          </div>
          <div className="px-2 py-1 text-[11px] text-mute leading-5">
            {selLine && k.selEdge !== undefined ? <span className="text-cy">Câu {selIdx + 1} · từ "{selLine.words[k.selEdge >> 1].text}" · {k.selEdge % 2 ? 'cuối' : 'đầu'} = {sec(edgeGet(selLine, k.selEdge) + off)}</span> : selLine ? <span>Câu {selIdx + 1} · {sec(lStart(selLine) + off)} → {sec(lEnd(selLine) + off)}</span> : <span>Chọn một câu để hiện các mép từ.</span>}
            {' '}Kéo mép từ để chỉnh (Alt = chính xác 1 ms) · ←/→ tinh chỉnh 10 ms (Shift 100 ms) · M = đánh dấu mép tại playhead rồi sang mép kế · Ctrl+cuộn = zoom · Viền cam ≈ = mốc ước lượng.
          </div>
        </div>
      </div>
    </div>
  );
}
