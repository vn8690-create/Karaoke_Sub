import { useEffect } from 'react';
import { useStudio } from './store';
import { useKaraoke } from './karaokeStore';
import TopBar, { saveProject } from './components/TopBar';
import Library from './components/Library';
import Preview from './components/Preview';
import Inspector from './components/Inspector';
import Timeline from './components/Timeline';
import KaraokeEditor from './components/KaraokeEditor';
import Wizard from './components/Wizard';

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
function Resizer({ axis, onDelta }: { axis: 'x' | 'y'; onDelta: (d: number) => void }) {
  const down = (e: React.PointerEvent) => {
    e.preventDefault(); let last = axis === 'x' ? e.clientX : e.clientY;
    const mv = (ev: PointerEvent) => { const p = axis === 'x' ? ev.clientX : ev.clientY; onDelta(p - last); last = p; };
    const up = () => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  };
  return <div onPointerDown={down} className={`${axis === 'x' ? 'w-1 cursor-col-resize' : 'h-1 cursor-row-resize'} bg-line hover:bg-vio shrink-0 transition-colors`} />;
}
export default function App() {
  const s = useStudio();
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName; if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const g = useStudio.getState(), kar = g.bottomTab === 'karaoke', undo = () => (kar ? useKaraoke.getState().undo() : g.undo()), redo = () => (kar ? useKaraoke.getState().redo() : g.redo());
      if (e.code === 'Space') { e.preventDefault(); g.set({ playing: !g.playing }); }
      else if (e.ctrlKey && e.key === 'z') { e.preventDefault(); undo(); } else if (e.ctrlKey && e.key === 'y') { e.preventDefault(); redo(); }
      else if (e.ctrlKey && e.key === 's') { e.preventDefault(); saveProject(); }
      else if (!kar && (e.key === 's' || e.key === 'S') && !e.ctrlKey) { if (g.sel) g.split(g.sel, g.playhead); }
      else if (!kar && e.key === 'Delete' && g.sel) g.remove(g.sel);
    };
    window.addEventListener('keydown', key);
    // Nghe thử câu: dừng khi playhead vượt điểm kết thúc đã đặt.
    const unsub = useStudio.subscribe((st) => { const kk = useKaraoke.getState(); if (kk.auditionEnd !== undefined && st.playing && st.playhead >= kk.auditionEnd) { useStudio.setState({ playing: false }); kk.set({ auditionEnd: undefined }); } });
    return () => { window.removeEventListener('keydown', key); unsub(); };
  }, []);
  const g = () => useStudio.getState();
  const tab = (id: 'timeline' | 'karaoke') => s.set({ bottomTab: id, tlH: id === 'karaoke' ? Math.max(s.tlH, 400) : s.tlH });
  return (
    <div className="h-full flex flex-col">
      <TopBar />
      <div className="flex flex-1 min-h-0">
        <Library /><Resizer axis="x" onDelta={(d) => s.set({ leftW: clamp(g().leftW + d, 180, 480) })} />
        <Preview />
        <Resizer axis="x" onDelta={(d) => s.set({ rightW: clamp(g().rightW - d, 220, 460) })} /><Inspector />
      </div>
      <Resizer axis="y" onDelta={(d) => s.set({ tlH: clamp(g().tlH - d, 150, 560) })} />
      <div style={{ height: s.tlH }} className="flex flex-col shrink-0 min-h-0 border-t border-line">
        <div className="flex bg-pane border-b border-line">{(['timeline', 'karaoke'] as const).map((id) => <button key={id} onClick={() => tab(id)} className={`px-4 py-1.5 text-xs ${s.bottomTab === id ? 'text-cy border-b-2 border-cy' : 'text-mute'}`}>{id === 'timeline' ? 'Timeline' : 'Karaoke Editor'}</button>)}</div>
        {s.bottomTab === 'timeline' ? <Timeline /> : <KaraokeEditor />}
      </div>
      <Wizard />
      {s.toast && <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-pane2 border border-vio rounded-lg px-4 py-2 shadow-xl z-[60] max-w-[80vw]">{s.toast}</div>}
    </div>
  );
}
