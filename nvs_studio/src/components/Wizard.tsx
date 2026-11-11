import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { useStudio } from '../store';
import { useKaraoke } from '../karaokeStore';
import { BackendClient, type BackendProject } from '../backend';
import { MockAIAdapter } from '../adapters/mock';
import { BackendAIAdapter } from '../adapters/backend';
import { guessSep, lid } from '../karaoke';
import { importFiles } from '../media';
import type { AIAdapter, AlignRequest, AlignResult, JobProgress, JobState } from '../contracts';

const STEPS = ['Nguồn', 'Ngôn ngữ & lời', 'Xử lý', 'Kết quả'];
const LABEL: Record<JobState, string> = { idle: 'Chưa chạy', 'model-missing': 'Chưa tải model', 'downloading-model': 'Đang tải model', analyzing: 'Đang phân tích', recognizing: 'Đang nhận diện lời', aligning: 'Đang căn thời gian', done: 'Thành công', error: 'Lỗi', cancelled: 'Đã hủy' };

async function attachAudio(client: BackendClient, p: BackendProject) {
  const name = p.files.audio; const st = useStudio.getState(); if (!name) return;
  const r = await fetch(client.fileUrl(p.id, name)); if (!r.ok) throw new Error('Không tải được file nhạc từ backend.');
  const blob = await r.blob(), before = st.media.length; await importFiles([new File([blob], name, { type: blob.type || 'audio/mpeg' })]);
  const med = useStudio.getState().media[before]; if (med) { const st2 = useStudio.getState(); st2.set({ clips: st2.clips.filter((c) => !(c.track === 'A1' && c.kind === 'audio')), playhead: 0, playing: false }); st2.addClip({ track: 'A1', start: 0, dur: med.dur, off: 0, label: med.name, kind: 'audio', src: med.url, x: 0.5, y: 0.5, scale: 1, opacity: 1 }); }
}
export default function Wizard() {
  const m = useStudio(), k = useKaraoke(); const client = useMemo(() => new BackendClient(), []); const ctl = useRef<AbortController | null>(null);
  const [step, setStep] = useState(0), [engine, setEngine] = useState<'mock' | 'backend'>('mock'), [lang, setLang] = useState<'vi' | 'ja' | 'en' | 'auto'>('vi'), [lyrics, setLyrics] = useState('');
  const [audioId, setAudioId] = useState(''), [projects, setProjects] = useState<BackendProject[]>([]), [pid, setPid] = useState(''), [health, setHealth] = useState<'checking' | 'ok' | 'down'>('checking');
  const [uploadFile, setUploadFile] = useState<File | null>(null), [uploading, setUploading] = useState(false), [uploadError, setUploadError] = useState('');
  const [prog, setProg] = useState<JobProgress | null>(null), [err, setErr] = useState(''), [result, setResult] = useState<AlignResult | null>(null);
  useEffect(() => { if (!m.wizard) return; setHealth('checking'); client.health().then(() => client.projects()).then((p) => { setProjects(p); setHealth('ok'); }).catch(() => setHealth('down')); }, [m.wizard, client]);
  if (!m.wizard) return null;
  const proj = projects.find((p) => p.id === pid), media = m.media.find((x) => x.id === audioId), audios = m.media.filter((x) => x.kind === 'audio');
  const createProject = async () => {
    if (!uploadFile || uploading) return;
    setUploading(true); setUploadError('');
    try {
      const p = await client.createProject(uploadFile);
      setProjects(await client.projects()); setPid(p.id); setUploadFile(null);
      m.notify('Đã tạo dự án backend: ' + (p.title || p.id));
    } catch (e) { setUploadError((e as Error).message); }
    finally { setUploading(false); }
  };
  const openExisting = async () => {
    if (!pid) return;
    setUploadError(''); setUploading(true);
    try {
      const p = await client.project(pid);
      k.load(client.linesOf(p), 'backend', { projectId: p.id, duration: p.duration, title: p.title });
      await attachAudio(client, p);
      m.set({ wizard: false, bottomTab: 'karaoke', tlH: Math.max(m.tlH, 400) });
      setStep(0);
      m.notify('Dự án backend đã mở. Có thể chỉnh lời hoặc chạy Auto Karaoke.');
    } catch (e) { setUploadError((e as Error).message); }
    finally { setUploading(false); }
  };
  const run = async () => {
    setErr(''); setResult(null); setProg({ jobId: '', state: 'analyzing', percent: 0 }); setStep(2); ctl.current = new AbortController();
    const req: AlignRequest = { audioPath: media?.name ?? proj?.title ?? '', language: lang, lyrics: lyrics.trim() || undefined, engine, durationSec: media?.dur ?? proj?.duration ?? 60, projectId: pid || undefined };
    const ad: AIAdapter = engine === 'mock' ? new MockAIAdapter() : new BackendAIAdapter(client);
    try { const r = await ad.align(req, setProg, ctl.current.signal); setResult(r); setStep(3); }
    catch (e) { const ab = (e as Error).name === 'AbortError'; setProg((p) => ({ jobId: p?.jobId ?? '', state: ab ? 'cancelled' : 'error', percent: p?.percent ?? 0 })); setErr(ab ? 'Đã hủy xử lý.' : (e as Error).message); }
  };
  const open = async () => {
    if (!result) return;
    const lines = result.lines.map((l) => ({ id: lid(), sep: guessSep(l.words.map((w) => w.text)), words: l.words.map((w) => ({ ...w })) }));
    k.load(lines, result.mock ? 'mock' : 'backend', { projectId: engine === 'backend' ? pid : undefined, duration: proj?.duration ?? media?.dur, title: proj?.title });
    if (engine === 'backend' && proj) { try { await attachAudio(client, proj); } catch (e) { m.notify((e as Error).message); } }
    m.set({ wizard: false, bottomTab: 'karaoke', tlH: Math.max(m.tlH, 400) }); setStep(0); setProg(null); setErr(''); setResult(null);
  };
  const close = () => { ctl.current?.abort(); m.set({ wizard: false }); setStep(0); setProg(null); setErr(''); setResult(null); };
  const canNext = step === 0 ? (engine === 'mock' || (health === 'ok' && !!pid && !uploading)) : true;
  const busy = step === 2 && !err && prog?.state !== 'done';
  return (
    <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4">
      <div className="w-[720px] max-w-full bg-pane border border-line rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-line"><b className="text-base">Auto Karaoke Wizard</b><span className="flex-1" /><button className="btn !p-1" onClick={close} title="Đóng"><X size={16} /></button></div>
        <div className="flex px-4 pt-3 gap-2">{STEPS.map((s, i) => <div key={s} className={`flex-1 text-center text-[11px] py-1 rounded-full border ${i === step ? 'border-vio text-white bg-[#33286b]' : i < step ? 'border-cy text-cy' : 'border-line text-mute'}`}>{i < step ? '✓ ' : `${i + 1}. `}{s}</div>)}</div>
        <div className="p-4 overflow-auto min-h-[260px]">
          {step === 0 && <div className="flex flex-col gap-3">
            <button onClick={() => setEngine('mock')} className={`text-left p-3 rounded-xl border ${engine === 'mock' ? 'border-vio bg-[#241c4a]' : 'border-line'}`}><b>MOCK</b> <span className="text-[10px] bg-amber-600 rounded px-1.5 ml-1">GIẢ LẬP</span><div className="text-mute mt-1">Tiến trình và kết quả giả lập để thử giao diện. Lời bạn nhập được chia đều theo thời lượng, không nhận diện giọng thật.</div></button>
            <button onClick={() => setEngine('backend')} className={`text-left p-3 rounded-xl border ${engine === 'backend' ? 'border-vio bg-[#241c4a]' : 'border-line'}`}><b>Backend local_studio</b> <span className={`text-[10px] rounded px-1.5 ml-1 ${health === 'ok' ? 'bg-emerald-700' : 'bg-slate-600'}`}>{health === 'checking' ? 'đang kiểm tra…' : health === 'ok' ? 'đã kết nối' : 'chưa chạy'}</span>
              <div className="text-mute mt-1">Whisper + căn lời thật (stable-ts) qua API sẵn có. {health === 'down' && 'Hãy chạy windows\\start.bat (cổng 8776) rồi mở lại Wizard.'}</div></button>
            {engine === 'backend' && health === 'ok' && <div className="flex flex-col gap-2 rounded-lg border border-line p-3">
              <label>Dự án backend<select value={pid} onChange={(e) => setPid(e.target.value)} className="w-full mt-1 bg-ink border border-line rounded px-2 py-1.5"><option value="">— chọn —</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title || p.id} · {p.duration?.toFixed(0)}s</option>)}</select></label>
              <label className="text-mute">Hoặc tải nhạc MP3/WAV/FLAC lên để tạo dự án mới<input type="file" accept=".mp3,.wav,.flac,.m4a,.aac,.ogg,.opus,.wma" className="block w-full mt-1 text-white text-xs" onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)} /></label>
              <div className="flex flex-wrap gap-2">
                <button className="btn pri" disabled={!uploadFile || uploading} onClick={() => void createProject()}>{uploading ? 'Đang xử lý…' : 'Tạo dự án từ file nhạc'}</button>
                <button className="btn" disabled={!pid || uploading} onClick={() => void openExisting()}>Mở Editor không chạy AI</button>
              </div>
              {uploadError && <div role="alert" className="text-pink-300 text-xs">{uploadError}</div>}
              <p className="text-mute text-[11px]">Dùng Local Studio thật trên máy này. Cần FFmpeg và backend Windows đang chạy.</p>
            </div>}
            {engine === 'mock' && <label className="block">Nhạc dùng để lấy thời lượng (tuỳ chọn)<select value={audioId} onChange={(e) => setAudioId(e.target.value)} className="w-full mt-1 bg-ink border border-line rounded px-2 py-1.5"><option value="">60 giây mặc định</option>{audios.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.dur.toFixed(0)}s</option>)}</select></label>}
          </div>}
          {step === 1 && <div className="flex flex-col gap-3">
            <div className="flex gap-2">{(['vi', 'ja', 'en', 'auto'] as const).map((l) => <button key={l} onClick={() => setLang(l)} className={`btn ${lang === l ? '!border-vio' : ''}`}>{{ vi: 'Tiếng Việt', ja: '日本語', en: 'English', auto: 'Tự nhận' }[l]}</button>)}</div>
            <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)} placeholder="Dán lời chuẩn (mỗi câu một dòng). Để trống = nhận diện lời bằng Whisper (chỉ backend)." className="h-40 bg-ink border border-line rounded-lg p-2" />
            <p className="text-mute text-[11px]">{engine === 'backend' ? 'Có lời → căn lời theo giọng hát (giữ nguyên lời bạn nhập). Không có lời → Whisper nhận diện. Backend hỗ trợ vi/en/ja/auto.' : 'MOCK: nếu để trống sẽ dùng vài dòng lời mẫu.'}</p></div>}
          {step >= 2 && <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">{busy ? <Loader2 className="animate-spin text-cy" size={18} /> : prog?.state === 'done' ? <Check className="text-emerald-400" size={18} /> : null}<b>{prog ? LABEL[prog.state] : ''}</b>{engine === 'mock' && <span className="text-[10px] bg-amber-600 rounded px-1.5">MOCK</span>}</div>
            <div className="h-2 bg-ink rounded"><div className="h-2 rounded bg-gradient-to-r from-vio to-mag transition-all" style={{ width: `${prog?.percent ?? 0}%` }} /></div>
            <div className="text-mute min-h-5">{prog?.message}</div>
            {err && <div className="p-3 rounded-lg border border-mag text-pink-200">{err}</div>}
            {result && <div className="p-3 rounded-lg border border-line"><b>{result.lines.length} câu · {result.lines.reduce((a, l) => a + l.words.length, 0)} từ</b> <span className="text-mute">({result.engine})</span>
              {result.mock && <div className="text-amber-400 mt-1">Đây là DỮ LIỆU GIẢ LẬP (MOCK), không phải kết quả nhận diện giọng thật.</div>}
              <ul className="mt-2 text-mute">{result.lines.slice(0, 3).map((l, i) => <li key={i} className="truncate">{l.start.toFixed(2)}s · {l.text}</li>)}</ul></div>}
          </div>}
        </div>
        <div className="flex items-center gap-2 px-4 py-3 border-t border-line">
          {step > 0 && step < 3 && !busy && <button className="btn" onClick={() => setStep(step - 1)}>Quay lại</button>}
          <span className="flex-1" />
          {busy && <button className="btn" onClick={() => ctl.current?.abort()}>Hủy xử lý</button>}
          {step === 0 && <button className="btn pri" disabled={!canNext} onClick={() => setStep(1)}>Tiếp tục</button>}
          {step === 1 && <button className="btn pri" onClick={() => void run()}>Bắt đầu</button>}
          {step === 2 && err && <button className="btn pri" onClick={() => void run()}>Thử lại</button>}
          {step === 3 && <button className="btn pri" onClick={() => void open()}>Mở trong Karaoke Editor</button>}
        </div>
      </div>
    </div>
  );
}
