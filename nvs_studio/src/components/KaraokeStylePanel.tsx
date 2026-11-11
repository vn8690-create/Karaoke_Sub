import { useKaraoke } from '../karaokeStore';
import { EFFECTS, FONTS, type Effect, type KStyle } from './karaokeDraw';

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => <label className="flex items-center gap-2 mb-2"><span className="w-20 text-mute shrink-0">{label}</span>{children}</label>;
export default function KaraokeStylePanel() {
  const { style, set } = useKaraoke(); const up = (p: Partial<KStyle>) => set({ style: { ...style, ...p } });
  return (
    <div className="mb-4 pb-3 border-b border-line">
      <h3 className="font-bold mb-3">Kiểu chữ Karaoke</h3>
      <Row label="Hiệu ứng"><select value={style.effect} onChange={(e) => up({ effect: e.target.value as Effect })} className="flex-1 min-w-0 bg-ink border border-line rounded px-1 py-1">{Object.entries(EFFECTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Row>
      <Row label="Font"><select value={style.font} onChange={(e) => up({ font: e.target.value })} className="flex-1 min-w-0 bg-ink border border-line rounded px-1 py-1">{Object.entries(FONTS).map(([k, v]) => <option key={k} value={v}>{k}</option>)}</select></Row>
      <Row label="Cỡ chữ"><input type="range" min={3} max={12} step={0.5} value={style.size} onChange={(e) => up({ size: Number(e.target.value) })} className="flex-1 accent-[#8b5cf6]" /></Row>
      <Row label="Vị trí Y"><input type="range" min={0.4} max={0.95} step={0.01} value={style.y} onChange={(e) => up({ y: Number(e.target.value) })} className="flex-1 accent-[#8b5cf6]" /></Row>
      <Row label="Màu đã hát"><input type="color" value={style.fill} onChange={(e) => up({ fill: e.target.value })} /></Row>
      <Row label="Màu chưa hát"><input type="color" value={style.unsung} onChange={(e) => up({ unsung: e.target.value })} /></Row>
      <Row label="Viền"><input type="color" value={style.outline} onChange={(e) => up({ outline: e.target.value })} /></Row>
      <Row label="Câu kế tiếp"><input type="checkbox" checked={style.next} onChange={(e) => up({ next: e.target.checked })} /></Row>
    </div>
  );
}
