import { useEffect } from 'react';
import { useStudio } from './store';
import TopBar, { saveProject } from './components/TopBar';
import Library from './components/Library';
import Preview from './components/Preview';
import Inspector from './components/Inspector';
import Timeline from './components/Timeline';

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
      const tag = (e.target as HTMLElement).tagName; if (tag === 'INPUT' || tag === 'TEXTAREA') return; const g = useStudio.getState();
      if (e.code === 'Space') { e.preventDefault(); g.set({ playing: !g.playing }); }
      else if ((e.key === 's' || e.key === 'S') && !e.ctrlKey) { if (g.sel) g.split(g.sel, g.playhead); }
      else if (e.key === 'Delete' && g.sel) g.remove(g.sel);
      else if (e.ctrlKey && e.key === 'z') { e.preventDefault(); g.undo(); }
      else if (e.ctrlKey && e.key === 'y') { e.preventDefault(); g.redo(); }
      else if (e.ctrlKey && e.key === 's') { e.preventDefault(); saveProject(); }
    };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, []);
  const g = () => useStudio.getState();
  return (
    <div className="h-full flex flex-col">
      <TopBar />
      <div className="flex flex-1 min-h-0">
        <Library /><Resizer axis="x" onDelta={(d) => s.set({ leftW: clamp(g().leftW + d, 180, 480) })} />
        <Preview />
        <Resizer axis="x" onDelta={(d) => s.set({ rightW: clamp(g().rightW - d, 220, 460) })} /><Inspector />
      </div>
      <Resizer axis="y" onDelta={(d) => s.set({ tlH: clamp(g().tlH - d, 150, 520) })} />
      <Timeline />
      {s.toast && <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-pane2 border border-vio rounded-lg px-4 py-2 shadow-xl z-50">{s.toast}</div>}
    </div>
  );
}
