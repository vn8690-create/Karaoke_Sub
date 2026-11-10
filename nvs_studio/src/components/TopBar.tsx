import { useRef, useState } from 'react';
import { Cpu, Download, FilePlus, FolderOpen, Redo2, Save, Settings, Undo2, Wand2 } from 'lucide-react';
import { useStudio, type Clip, type Track } from '../store';
import { t } from '../i18n';

function gpuName() {
  try { const g = document.createElement('canvas').getContext('webgl'); const e = g?.getExtension('WEBGL_debug_renderer_info'); return e && g ? String(g.getParameter(e.UNMASKED_RENDERER_WEBGL)) : 'không rõ'; } catch { return 'không rõ'; }
}
export function saveProject() {
  const s = useStudio.getState();
  const data = { version: 1, tracks: s.tracks, clips: s.clips.map(({ src: _s, peaks: _p, ...rest }) => rest) };
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' })); a.download = 'du-an.nvs.json'; a.click();
  s.notify('Đã lưu cấu trúc dự án (file media cần nhập lại khi mở).');
}
export default function TopBar() {
  const s = useStudio(); const open = useRef<HTMLInputElement>(null); const [gpu] = useState(gpuName);
  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  const nope = (what: string) => s.notify(`${what}: ${t('unsupported')}`);
  const onOpen = async (f?: File) => {
    if (!f) return;
    try { const d = JSON.parse(await f.text()) as { tracks: Track[]; clips: Clip[] };
      if (!Array.isArray(d.tracks) || !Array.isArray(d.clips)) throw new Error('sai định dạng');
      s.set({ tracks: d.tracks, clips: d.clips, past: [], future: [], playhead: 0, playing: false, sel: undefined }); s.notify('Đã mở dự án. Hãy nhập lại file media rồi kéo vào timeline.');
    } catch { s.notify('Không mở được file dự án này.'); }
  };
  return (
    <header className="flex items-center gap-2 px-3 h-12 bg-pane border-b border-line">
      <div className="flex items-center gap-2 mr-3"><div className="w-7 h-7 rounded-lg bg-gradient-to-br from-vio to-mag grid place-items-center font-black text-xs">N</div>
        <div className="leading-tight"><b className="tracking-wide">NVS Karaoke Studio</b> <span className="text-cy text-[10px] font-bold">PRO</span></div></div>
      <button className="btn" title="Dự án mới" onClick={() => { s.reset(); s.notify('Đã tạo dự án mới.'); }}><FilePlus size={15} />{t('tb.new')}</button>
      <button className="btn" title="Mở dự án (.nvs.json)" onClick={() => open.current?.click()}><FolderOpen size={15} />{t('tb.open')}</button>
      <input ref={open} type="file" accept=".json" hidden onChange={(e) => { void onOpen(e.target.files?.[0]); e.target.value = ''; }} />
      <button className="btn" title="Lưu (Ctrl+S)" onClick={saveProject}><Save size={15} />{t('tb.save')}</button>
      <span className="w-px h-6 bg-line mx-1" />
      <button className="btn" title="Hoàn tác (Ctrl+Z)" disabled={!s.past.length} onClick={s.undo}><Undo2 size={15} /></button>
      <button className="btn" title="Làm lại (Ctrl+Y)" disabled={!s.future.length} onClick={s.redo}><Redo2 size={15} /></button>
      <span className="w-px h-6 bg-line mx-1" />
      <button className="btn" title="Cần AI backend" onClick={() => nope('Auto Karaoke')}><Wand2 size={15} />{t('tb.auto')}</button>
      <div className="flex-1" />
      <div className="flex items-center gap-1 text-mute text-[11px]" title="Thông tin do trình duyệt báo cáo. Chưa đo VRAM/RAM thật (cần backend)."><Cpu size={14} />GPU: {gpu.slice(0, 38)} · {navigator.hardwareConcurrency} luồng CPU{mem ? ` · ≥${mem} GB RAM` : ''}</div>
      <button className="btn" title="Cần RenderAdapter + FFmpeg" onClick={() => nope('Xuất video')}><Download size={15} />{t('tb.export')}</button>
      <button className="btn" title="Cài đặt" onClick={() => nope('Cài đặt')}><Settings size={15} /></button>
    </header>
  );
}
