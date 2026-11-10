import { create } from 'zustand';
import * as K from './karaoke';
import { DEFAULT_STYLE, type KStyle } from './components/karaokeDraw';

export type Source = 'none' | 'file' | 'mock' | 'backend';
interface KS {
  lines: K.KLine[]; source: Source; sel?: string; selEdge?: number; offset: number; zoom: number; style: KStyle; dirty: boolean; auditionEnd?: number;
  projectId?: string; duration?: number; title?: string; past: K.KLine[][]; future: K.KLine[][];
  set: (p: Partial<KS>) => void; commit: () => void; undo: () => void; redo: () => void; load: (lines: K.KLine[], source: Source, meta?: { projectId?: string; duration?: number; title?: string }) => void;
  moveEdge: (id: string, idx: number, v: number) => void; shiftLine: (id: string, dt: number) => void; editText: (id: string, text: string) => void; distribute: (id: string) => void;
  remove: (id: string) => void; insert: (afterId: string | undefined, text: string) => void; bakeOffset: () => void; clear: () => void; markSaved: () => void;
}
export const useKaraoke = create<KS>((set, get) => {
  const edit = (f: (l: K.KLine[]) => K.KLine[]) => { get().commit(); set((s) => ({ lines: f(s.lines), dirty: true })); };
  return {
    lines: [], source: 'none', offset: 0, zoom: 120, style: DEFAULT_STYLE, dirty: false, past: [], future: [],
    set: (p) => set(p),
    commit: () => set((s) => ({ past: [...s.past.slice(-199), s.lines], future: [] })),
    undo: () => set((s) => (s.past.length ? { lines: s.past.at(-1)!, past: s.past.slice(0, -1), future: [s.lines, ...s.future], dirty: true } : s)),
    redo: () => set((s) => (s.future.length ? { lines: s.future[0], future: s.future.slice(1), past: [...s.past, s.lines], dirty: true } : s)),
    load: (lines, source, meta = {}) => { get().commit(); set({ lines, source, sel: undefined, selEdge: undefined, offset: 0, dirty: false, projectId: meta.projectId, duration: meta.duration, title: meta.title }); },
    // moveEdge được gọi liên tục khi kéo chuột: người gọi phải commit() một lần lúc bắt đầu kéo.
    moveEdge: (id, idx, v) => set((s) => ({ lines: K.moveEdge(s.lines, id, idx, v), dirty: true })),
    shiftLine: (id, dt) => edit((l) => K.shiftLine(l, id, dt)), editText: (id, text) => set((s) => ({ lines: K.editText(s.lines, id, text), dirty: true })),
    distribute: (id) => edit((l) => K.distribute(l, id)), remove: (id) => { edit((l) => K.removeLine(l, id)); set((s) => (s.sel === id ? { sel: undefined, selEdge: undefined } : s)); },
    insert: (afterId, text) => { get().commit(); const r = K.insertAfter(get().lines, afterId, text); if (r.id) set({ lines: r.lines, sel: r.id, dirty: true }); },
    bakeOffset: () => { if (!get().offset) return; edit((l) => K.shiftAll(l, get().offset)); set({ offset: 0 }); },
    clear: () => { get().commit(); set({ lines: [], source: 'none', sel: undefined, selEdge: undefined, dirty: false, projectId: undefined }); },
    markSaved: () => set({ dirty: false }),
  };
});
