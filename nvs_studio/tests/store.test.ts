import { beforeEach, describe, expect, it } from 'vitest';
import { snapTime, useStudio } from '../src/store';

const base = { track: 'A1', start: 2, dur: 10, off: 1, label: 'a', kind: 'audio' as const, x: .5, y: .5, scale: 1, opacity: 1 };
beforeEach(() => useStudio.getState().reset());
describe('timeline store', () => {
  it('snap chọn mốc gần nhất trong ngưỡng, ngoài ngưỡng giữ nguyên', () => {
    expect(snapTime(5.05, [0, 5, 9], .1)).toBe(5); expect(snapTime(6, [0, 5, 9], .1)).toBe(6);
  });
  it('cắt clip thành hai đoạn liền nhau và giữ offset âm thanh', () => {
    const id = useStudio.getState().addClip(base); useStudio.getState().split(id, 6);
    const cs = useStudio.getState().clips.filter((c) => c.track === 'A1');
    expect(cs).toHaveLength(2); expect(cs[0].dur).toBeCloseTo(4); expect(cs[1].start).toBe(6); expect(cs[1].dur).toBeCloseTo(6); expect(cs[1].off).toBeCloseTo(5);
  });
  it('không cắt sát mép clip', () => {
    const id = useStudio.getState().addClip(base); useStudio.getState().split(id, 2.01);
    expect(useStudio.getState().clips.filter((c) => c.track === 'A1')).toHaveLength(1);
  });
  it('undo và redo khôi phục đúng', () => {
    const n = useStudio.getState().clips.length; const id = useStudio.getState().addClip(base);
    useStudio.getState().remove(id); expect(useStudio.getState().clips).toHaveLength(n);
    useStudio.getState().undo(); expect(useStudio.getState().clips).toHaveLength(n + 1);
    useStudio.getState().redo(); expect(useStudio.getState().clips).toHaveLength(n);
  });
  it('khoá, ẩn, tắt tiếng track', () => {
    useStudio.getState().toggle('A1', 'mute'); expect(useStudio.getState().tracks.find((t) => t.id === 'A1')?.mute).toBe(true);
  });
});
