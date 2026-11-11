import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Loader2, X } from 'lucide-react';
import { BackendClient, type BackendProject, type RenderOptions, type SubtitleOptions } from '../backend';
import { useKaraoke } from '../karaokeStore';
import { useStudio } from '../store';

export default function RenderDialog() {
  const studio = useStudio(), karaoke = useKaraoke(), client = useMemo(() => new BackendClient(), []);
  const [project, setProject] = useState<BackendProject | null>(null);
  const [resolution, setResolution] = useState<'720p' | '1080p'>('1080p');
  const [mode, setMode] = useState<'original' | 'instrumental' | 'silent'>('original');
  const [busy, setBusy] = useState(false), [rendering, setRendering] = useState(false), [error, setError] = useState('');
  const [progress, setProgress] = useState(0), [message, setMessage] = useState('');
  const [completed, setCompleted] = useState(false);
  const control = useRef<AbortController | null>(null);
  const pid = karaoke.projectId;

  useEffect(() => {
    if (!studio.renderDialog || !pid) return;
    setError(''); setCompleted(false); setProgress(0); setMessage('Đang kiểm tra dự án backend…');
    client.project(pid).then((p) => {
      setProject(p); setMessage(p.status === 'ready' ? 'Đã kết nối backend.' : (p.message || p.status));
      setMode(p.files.instrumental ? 'instrumental' : 'original');
    }).catch((e) => setError((e as Error).message));
  }, [client, pid, studio.renderDialog]);

  if (!studio.renderDialog) return null;

  const styleOptions = (): SubtitleOptions => ({
    resolution,
    font_size: 54, font_family: 'Arial',
    text_color: karaoke.style.unsung, highlight_color: karaoke.style.fill,
    position: karaoke.style.y <= 0.38 ? 'top' : karaoke.style.y < 0.63 ? 'center' : 'bottom',
    margin_percent: 9,
  });

  const check = () => {
    if (!pid) throw new Error('Chưa có dự án backend. Mở Auto Karaoke → Backend để tạo hoặc chọn bài hát trước.');
    if (karaoke.source === 'mock') throw new Error('Lời đang là MOCK. Không thể xuất video từ dữ liệu AI giả lập.');
    if (karaoke.dirty || karaoke.offset !== 0) throw new Error('Hãy bấm Lưu backend trong Karaoke Editor trước khi xuất video.');
    if (!karaoke.lines.length) throw new Error('Dự án chưa có lời Karaoke. Hãy căn lời hoặc nhập lời rồi lưu backend.');
    if (!project?.files.audio) throw new Error('Dự án backend không có file audio.');
    return pid;
  };

  const render = async () => {
    setError(''); setCompleted(false); setProgress(0);
    try {
      const id = check();
      setBusy(true); setRendering(true); control.current = new AbortController();
      setMessage('Gửi yêu cầu xuất MP4…');
      await client.render(id, { ...styleOptions(), audio_mode: mode });
      const result = await client.wait(id, (p) => {
        setProgress(Math.round(p.progress || 0));
        setMessage(p.message || p.status);
      }, control.current.signal, 600);
      setProject(result);
      if (!result.files.video) throw new Error('Backend báo hoàn tất nhưng không có file MP4.');
      const quality = await client.quality(id);
      if (!quality.ok) throw new Error('Video cần kiểm tra: ' + quality.issues.map((i) => i.message).join('; '));
      setCompleted(true); setMessage('Đã xuất MP4 và kiểm tra chất lượng thành công.');
    } catch (e) {
      setError((e as Error).name === 'AbortError' ? 'Đã dừng theo dõi tác vụ.' : (e as Error).message);
    } finally { setBusy(false); setRendering(false); control.current = null; }
  };

  const subtitles = async () => {
    setError(''); setCompleted(false);
    try {
      const id = check();
      setBusy(true); setMessage('Đang tạo LRC, SRT, ASS…');
      const p = await client.subtitles(id, styleOptions());
      setProject(p); setMessage('Đã xuất phụ đề trên backend.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!pid || !rendering) return;
    try {
      setMessage('Đang gửi lệnh hủy FFmpeg…');
      await client.cancelRender(pid);
      // Keep polling until backend reports cancelled, then allow retry.
    } catch (e) { setError((e as Error).message); }
  };

  const close = () => {
    if (busy) { setError('Đang xử lý. Hãy hủy render hoặc đợi hoàn tất trước khi đóng.'); return; }
    studio.set({ renderDialog: false });
  };
  const url = (name?: string) => pid && name ? client.fileUrl(pid, name) : undefined;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-label="Xuất video từ backend" className="w-[640px] max-w-full bg-pane border border-line rounded-xl shadow-2xl p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between"><h2 className="font-bold text-lg">Xuất Karaoke bằng FFmpeg thật</h2><button className="btn" onClick={close} disabled={busy} title="Đóng"><X size={15}/></button></div>
        {!pid && <p role="alert" className="text-amber-400">Chưa mở dự án backend. Nhấn Auto Karaoke, chọn Backend local_studio và tạo/mở dự án trước.</p>}
        {pid && <p className="text-xs text-mute">Dự án: {project?.title || karaoke.title || pid} · {project?.duration?.toFixed(1) || '?'} giây · {project?.status || 'đang kiểm tra'}</p>}
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-xs">Độ phân giải<select className="bg-ink border border-line rounded p-2" disabled={busy} value={resolution} onChange={(e) => setResolution(e.target.value as '720p' | '1080p')}><option value="720p">1280×720</option><option value="1080p">1920×1080</option></select></label>
          <label className="flex flex-col gap-1 text-xs">Âm thanh<select className="bg-ink border border-line rounded p-2" disabled={busy} value={mode} onChange={(e) => setMode(e.target.value as RenderOptions['audio_mode'])}><option value="original">Nhạc gốc</option><option value="instrumental" disabled={!project?.files.instrumental}>Nhạc beat đã tách</option><option value="silent">Không tiếng</option></select></label>
        </div>
        <p className="text-xs text-mute">Backend hiện xuất chữ Karaoke tô quét theo từng từ (ASS). Các hiệu ứng phóng to, nhún và glow trên canvas chưa được kết xuất vào MP4.</p>
        <div className="h-2 rounded bg-ink"><div className="h-2 rounded bg-gradient-to-r from-vio to-mag" style={{width: String(progress) + '%'}} /></div>
        <div className="min-h-6 text-xs flex items-center gap-2">{busy && <Loader2 size={15} className="animate-spin" />}{message}</div>
        {error && <p role="alert" className="text-pink-300 text-xs">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <button className="btn pri" disabled={busy || !pid} onClick={() => void render()}>Xuất MP4</button>
          <button className="btn" disabled={busy || !pid} onClick={() => void subtitles()}>Tạo LRC / SRT / ASS</button>
          {rendering && <button className="btn" onClick={() => void cancel()}>Hủy render</button>}
          {completed && project?.files.video && <a className="btn pri" href={url(project.files.video)} download><Download size={14}/> Tải MP4</a>}
        </div>
        {!!project && <div className="flex flex-wrap gap-2 text-xs">
          {(['ass', 'srt', 'lrc'] as const).map((kind) => project.files[kind] && <a key={kind} className="btn" href={url(project.files[kind])} download>Tải {kind.toUpperCase()}</a>)}
          <a className="btn" href={client.backupUrl(project.id)} download>Tải ZIP dự án</a>
        </div>}
      </section>
    </div>
  );
}
