import { describe, expect, it } from 'vitest';
import { MockAIAdapter } from '../src/adapters/mock';
import type { JobProgress, JobState } from '../src/contracts';

describe('MockAIAdapter', () => {
  it('đi qua các trạng thái đúng thứ tự, phần trăm không giảm, kết quả đánh dấu mock', async () => {
    const ev: JobProgress[] = []; const r = await new MockAIAdapter(0, 12).align({ audioPath: 'a', language: 'vi', engine: 'mock', durationSec: 30, lyrics: 'Một hai ba\nBốn năm sáu' }, (p) => ev.push(p));
    const order = ev.map((e) => e.state).filter((s, i, a) => a.indexOf(s) === i); expect(order).toEqual<JobState[]>(['analyzing', 'recognizing', 'aligning', 'done']);
    expect(ev.map((e) => e.percent).every((p, i, a) => i === 0 || p >= a[i - 1])).toBe(true);
    expect(r.mock).toBe(true); expect(r.lines.map((l) => l.text)).toEqual(['Một hai ba', 'Bốn năm sáu']); expect(r.lines.at(-1)!.end).toBeLessThanOrEqual(30.01);
    for (const l of r.lines) expect(l.words.every((w) => w.end > w.start)).toBe(true);
  });
  it('hủy giữa chừng: báo cancelled và ném AbortError', async () => {
    const ctl = new AbortController(); const ev: JobProgress[] = [];
    const p = new MockAIAdapter(5, 50).align({ audioPath: 'a', language: 'vi', engine: 'mock' }, (e) => { ev.push(e); if (e.percent > 20) ctl.abort(); }, ctl.signal);
    await expect(p).rejects.toMatchObject({ name: 'AbortError' }); expect(ev.at(-1)!.state).toBe('cancelled');
  });
  it('lời tiếng Nhật được tách thành nhiều từ', async () => {
    const r = await new MockAIAdapter(0, 2).align({ audioPath: 'a', language: 'ja', engine: 'mock', durationSec: 10, lyrics: 'お母さんは怖いですね' }, () => undefined);
    expect(r.lines[0].words.length).toBeGreaterThan(2); expect(r.lines[0].words.map((w) => w.text).join('')).toBe('お母さんは怖いですね');
  });
});
