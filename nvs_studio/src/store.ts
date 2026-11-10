import { create } from 'zustand';
export type Kind = 'video' | 'audio' | 'vocal' | 'lyrics' | 'fx';
export interface Clip { id: string; track: string; start: number; dur: number; off: number; label: string; kind: Kind; src?: string; text?: string; peaks?: number[]; x: number; y: number; scale: number; opacity: number }
export interface Track { id: string; name: string; kind: Kind; mute: boolean; lock: boolean; hide: boolean }
export interface Media { id: string; name: string; kind: 'image' | 'audio' | 'video'; url: string; dur: number; peaks?: number[] }
export const uid = () => Math.random().toString(36).slice(2, 9);
export const snapTime = (t: number, targets: number[], th: number) => { let best = t, d = th; for (const x of targets) if (Math.abs(x - t) < d) { d = Math.abs(x - t); best = x; } return best; };
const TRACKS: Track[] = ([['V1', 'Video / Ảnh', 'video'], ['A1', 'Nhạc', 'audio'], ['VOC', 'Giọng hát', 'vocal'], ['LYR', 'Lời Karaoke', 'lyrics'], ['FX', 'Hiệu ứng', 'fx']] as [string, string, Kind][])
  .map(([id, name, kind]) => ({ id, name, kind, mute: false, lock: false, hide: false }));
const LINES = ['[MOCK] Dòng lời mẫu thứ nhất', '[MOCK] Dòng lời mẫu thứ hai', '[MOCK] Dòng lời mẫu thứ ba', '[MOCK] Dòng lời mẫu thứ tư'];
export const demoClips = (): Clip[] => LINES.map((text, i) => ({ id: uid(), track: 'LYR', start: i * 4, dur: 3.6, off: 0, label: text, kind: 'lyrics', text, x: .5, y: .82, scale: 1, opacity: 1 }));
export const defaultTrack = (k: Media['kind']) => (k === 'audio' ? 'A1' : 'V1');

interface S {
  tracks: Track[]; clips: Clip[]; media: Media[]; playhead: number; playing: boolean; zoom: number; sel?: string; aspect: string; grid: boolean; safe: boolean; snap: boolean;
  leftW: number; rightW: number; tlH: number; toast: string; past: Clip[][]; future: Clip[][];
  set: (p: Partial<S>) => void; commit: () => void; undo: () => void; redo: () => void; addMedia: (m: Media) => void; addClip: (c: Omit<Clip, 'id'>) => string;
  patch: (id: string, p: Partial<Clip>) => void; split: (id: string, t: number) => void; remove: (id: string) => void; toggle: (id: string, k: 'mute' | 'lock' | 'hide') => void; reset: () => void; notify: (m: string) => void;
}
let toastTimer: ReturnType<typeof setTimeout> | undefined;
export const useStudio = create<S>((set, get) => ({
  tracks: TRACKS, clips: demoClips(), media: [], playhead: 0, playing: false, zoom: 60, aspect: '16:9', grid: false, safe: false, snap: true,
  leftW: 260, rightW: 280, tlH: 250, toast: '', past: [], future: [],
  set: (p) => set(p),
  commit: () => set((s) => ({ past: [...s.past.slice(-99), s.clips], future: [] })),
  undo: () => set((s) => (s.past.length ? { clips: s.past.at(-1)!, past: s.past.slice(0, -1), future: [s.clips, ...s.future] } : s)),
  redo: () => set((s) => (s.future.length ? { clips: s.future[0], future: s.future.slice(1), past: [...s.past, s.clips] } : s)),
  addMedia: (m) => set((s) => ({ media: [...s.media, m] })),
  addClip: (c) => { const id = uid(); get().commit(); set((s) => ({ clips: [...s.clips, { ...c, id }], sel: id })); return id; },
  patch: (id, p) => set((s) => ({ clips: s.clips.map((c) => (c.id === id ? { ...c, ...p } : c)) })),
  split: (id, t) => { const c = get().clips.find((x) => x.id === id); if (!c || t <= c.start + .05 || t >= c.start + c.dur - .05) return;
    get().commit(); set((s) => ({ clips: s.clips.flatMap((x) => (x.id === id ? [{ ...x, dur: t - x.start }, { ...x, id: uid(), start: t, dur: x.start + x.dur - t, off: x.off + (t - x.start) }] : [x])) })); },
  remove: (id) => { get().commit(); set((s) => ({ clips: s.clips.filter((c) => c.id !== id), sel: s.sel === id ? undefined : s.sel })); },
  toggle: (id, k) => set((s) => ({ tracks: s.tracks.map((t) => (t.id === id ? { ...t, [k]: !t[k] } : t)) })),
  reset: () => set({ clips: demoClips(), past: [], future: [], playhead: 0, playing: false, sel: undefined }),
  notify: (m) => { set({ toast: m }); clearTimeout(toastTimer); toastTimer = setTimeout(() => set({ toast: '' }), 3500); },
}));
