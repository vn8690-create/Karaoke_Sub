import { uid, useStudio, type Media } from './store';
export async function importFile(f: File): Promise<Media> {
  const url = URL.createObjectURL(f), base = { id: uid(), name: f.name, url };
  if (f.type.startsWith('image')) return { ...base, kind: 'image', dur: 5 };
  if (f.type.startsWith('audio')) {
    const ctx = new AudioContext(); const buf = await ctx.decodeAudioData(await f.arrayBuffer()); await ctx.close();
    const d = buf.getChannelData(0), N = 400, step = Math.floor(d.length / N) || 1, peaks: number[] = [];
    for (let i = 0; i < N; i++) { let m = 0; for (let j = i * step; j < Math.min(d.length, (i + 1) * step); j += 16) m = Math.max(m, Math.abs(d[j])); peaks.push(m); }
    return { ...base, kind: 'audio', dur: buf.duration, peaks };
  }
  if (f.type.startsWith('video')) {
    const dur = await new Promise<number>((res, rej) => { const v = document.createElement('video'); v.onloadedmetadata = () => res(v.duration); v.onerror = () => rej(new Error('Không đọc được video')); v.src = url; });
    return { ...base, kind: 'video', dur };
  }
  throw new Error('Định dạng chưa hỗ trợ: ' + f.name);
}
export async function importFiles(files: File[]) {
  const s = useStudio.getState();
  for (const f of files) { try { s.addMedia(await importFile(f)); } catch (e) { s.notify((e as Error).message); } }
}
// Phát âm thanh đồng bộ với playhead (nhạc + giọng). Phần video chưa phát tiếng trong bản này.
const els = new Map<string, HTMLAudioElement>();
export function syncAudio(playing: boolean, t: number) {
  const s = useStudio.getState();
  for (const [id, a] of els) if (!s.clips.some((c) => c.id === id)) { a.pause(); els.delete(id); }
  for (const c of s.clips) {
    if ((c.kind !== 'audio' && c.kind !== 'vocal') || !c.src) continue;
    let a = els.get(c.id); if (!a) { a = new Audio(c.src); els.set(c.id, a); }
    a.muted = !!s.tracks.find((x) => x.id === c.track)?.mute;
    const at = c.off + t - c.start;
    if (playing && t >= c.start && t < c.start + c.dur) { if (a.paused) { a.currentTime = at; void a.play().catch(() => undefined); } else if (Math.abs(a.currentTime - at) > .35) a.currentTime = at; }
    else if (!a.paused) a.pause();
  }
}
