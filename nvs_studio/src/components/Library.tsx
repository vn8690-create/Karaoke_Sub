import { useRef, useState } from 'react';
import { Film, Image as ImageIcon, Music2, Plus, Upload } from 'lucide-react';
import { defaultTrack, useStudio, type Media } from '../store';
import { importFiles } from '../media';
import { t } from '../i18n';

type Tab = 'media' | 'audio' | 'text' | 'fx' | 'tpl';
const TABS: [Tab, 'lib.media' | 'lib.audio' | 'lib.text' | 'lib.fx' | 'lib.tpl'][] = [['media', 'lib.media'], ['audio', 'lib.audio'], ['text', 'lib.text'], ['fx', 'lib.fx'], ['tpl', 'lib.tpl']];
const Icon = ({ k }: { k: Media['kind'] }) => (k === 'audio' ? <Music2 size={16} /> : k === 'video' ? <Film size={16} /> : <ImageIcon size={16} />);

export default function Library() {
  const s = useStudio(); const [tab, setTab] = useState<Tab>('media'); const [text, setText] = useState(''); const file = useRef<HTMLInputElement>(null); const [q, setQ] = useState('');
  const list = s.media.filter((m) => (tab === 'audio' ? m.kind === 'audio' : true) && m.name.toLowerCase().includes(q.toLowerCase()));
  const add = (m: Media) => { s.addClip({ track: defaultTrack(m.kind), start: s.playhead, dur: m.dur, off: 0, label: m.name, kind: m.kind === 'audio' ? 'audio' : 'video', src: m.url, x: .5, y: .5, scale: 1, opacity: 1 }); };
  return (
    <aside style={{ width: s.leftW }} className="bg-pane flex flex-col min-h-0 border-r border-line shrink-0">
      <div className="flex border-b border-line">{TABS.map(([id, k]) => (
        <button key={id} onClick={() => setTab(id)} className={`flex-1 py-2 text-[11px] ${tab === id ? 'text-cy border-b-2 border-cy' : 'text-mute'}`}>{t(k)}</button>))}</div>
      {(tab === 'media' || tab === 'audio') && (<div className="p-2 flex flex-col gap-2 min-h-0 flex-1">
        <button className="btn pri justify-center" onClick={() => file.current?.click()}><Upload size={15} />{t('lib.import')}</button>
        <input ref={file} type="file" multiple hidden accept="audio/*,video/*,image/*" onChange={(e) => { void importFiles([...(e.target.files ?? [])]); e.target.value = ''; }} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm kiếm…" className="bg-ink border border-line rounded-lg px-2 py-1.5" />
        <div className="overflow-auto flex-1 flex flex-col gap-1.5">
          {!list.length && <p className="text-mute text-center mt-6 px-3">Chưa có file. Bấm "Nhập file" (MP3, WAV, FLAC, MP4, MOV, PNG, JPG tuỳ trình duyệt hỗ trợ), rồi kéo vào timeline.</p>}
          {list.map((m) => (<div key={m.id} draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', m.id)} className="flex items-center gap-2 p-1.5 rounded-lg bg-pane2 border border-line hover:border-vio cursor-grab">
            <div className="w-11 h-11 rounded-md bg-ink grid place-items-center overflow-hidden text-mute shrink-0">{m.kind === 'image' ? <img src={m.url} alt="" className="w-full h-full object-cover" /> : <Icon k={m.kind} />}</div>
            <div className="min-w-0 flex-1"><div className="truncate">{m.name}</div><div className="text-mute text-[11px]">{m.kind} · {m.dur.toFixed(1)}s</div></div>
            <button className="btn !p-1" title="Thêm vào timeline tại playhead" onClick={() => add(m)}><Plus size={14} /></button></div>))}
        </div></div>)}
      {tab === 'text' && (<div className="p-2 flex flex-col gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Nhập một dòng lời (Việt / 日本語)" className="bg-ink border border-line rounded-lg px-2 py-1.5" />
        <button className="btn pri justify-center" disabled={!text.trim()} onClick={() => { s.addClip({ track: 'LYR', start: s.playhead, dur: 3.5, off: 0, label: text, kind: 'lyrics', text, x: .5, y: .82, scale: 1, opacity: 1 }); setText(''); }}>Thêm lời vào timeline</button>
        <p className="text-mute">Lời nhập tay chạy thật trong preview: chữ tô màu theo tiến độ. Tự căn từng từ cần AI backend.</p></div>)}
      {(tab === 'fx' || tab === 'tpl') && <p className="p-4 text-mute">{t('unsupported')}</p>}
    </aside>
  );
}
