import { Scissors, Trash2 } from 'lucide-react';
import { useStudio, type Clip } from '../store';
import { useKaraoke } from '../karaokeStore';
import KaraokeStylePanel from './KaraokeStylePanel';

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => <label className="flex items-center gap-2 mb-2"><span className="w-20 text-mute shrink-0">{label}</span>{children}</label>;
export default function Inspector() {
  const s = useStudio(); const hasK = useKaraoke((x) => x.lines.length > 0); const c = s.clips.find((x) => x.id === s.sel);
  const num = (k: 'start' | 'dur' | 'x' | 'y' | 'scale' | 'opacity', min: number, max: number, step: number, range?: boolean) => (c &&
    <input type={range ? 'range' : 'number'} min={min} max={max} step={step} value={Number(c[k].toFixed(3))} className="flex-1 min-w-0 bg-ink border border-line rounded px-1 py-0.5 accent-[#8b5cf6]"
      onPointerDown={() => s.commit()} onFocus={() => s.commit()} onChange={(e) => s.patch(c.id, { [k]: Math.min(max, Math.max(min, Number(e.target.value))) } as Partial<Clip>)} />);
  return (
    <aside style={{ width: s.rightW }} className="bg-pane border-l border-line overflow-auto p-3 shrink-0">
      {hasK && <KaraokeStylePanel />}
      <h3 className="font-bold mb-3">Thuộc tính</h3>
      {!c ? <p className="text-mute">Chọn một clip trên timeline để chỉnh thuộc tính.</p> : (<>
        <div className="mb-3 truncate text-cy" title={c.label}>{c.label}</div>
        {c.kind === 'lyrics' && <Row label="Nội dung"><input value={c.text ?? ''} onFocus={() => s.commit()} onChange={(e) => s.patch(c.id, { text: e.target.value, label: e.target.value })} className="flex-1 min-w-0 bg-ink border border-line rounded px-1 py-0.5" /></Row>}
        <Row label="Bắt đầu (s)">{num('start', 0, 3600, .1)}</Row><Row label="Dài (s)">{num('dur', .2, 3600, .1)}</Row>
        <Row label="Vị trí X">{num('x', 0, 1, .01, true)}</Row><Row label="Vị trí Y">{num('y', 0, 1, .01, true)}</Row>
        <Row label="Tỉ lệ">{num('scale', .3, 3, .05, true)}</Row><Row label="Độ mờ">{num('opacity', 0, 1, .01, true)}</Row>
        <div className="flex gap-2 mt-3"><button className="btn" onClick={() => s.split(c.id, s.playhead)}><Scissors size={14} />Cắt</button><button className="btn" onClick={() => s.remove(c.id)}><Trash2 size={14} />Xoá</button></div></>)}
      <h4 className="font-bold mt-5 mb-1 text-mute">Chưa hỗ trợ (cần backend)</h4>
      <p className="text-mute text-[11px] leading-5">Font/viền/bóng, glow, gradient, keyframe, blend mode, âm lượng và fade, hiệu ứng tô từng từ theo timestamp AI.</p>
    </aside>
  );
}
