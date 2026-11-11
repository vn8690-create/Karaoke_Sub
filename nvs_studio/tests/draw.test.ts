import { describe, expect, it } from 'vitest';
import { drawKaraoke, DEFAULT_STYLE } from '../src/components/karaokeDraw';
import type { KLine } from '../src/karaoke';

// Canvas giả ghi lại lệnh vẽ: kiểm tra tô màu đúng theo mốc từng từ mà không cần trình duyệt.
function fakeCtx() {
  const calls: { fn: string; args: unknown[] }[] = []; const props: Record<string, unknown> = {};
  const ctx = new Proxy({}, { get: (_t, k: string) => (k === 'measureText' ? (t: string) => ({ width: t.length * 10 }) : k in props ? props[k] : (...a: unknown[]) => { calls.push({ fn: k, args: a }); }), set: (_t, k: string, v) => { props[k] = v; return true; } });
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}
const line: KLine = { id: 'a', sep: ' ', words: [{ text: 'abcd', start: 1, end: 2 }, { text: 'efgh', start: 2, end: 4 }] };
const fills = (calls: { fn: string; args: unknown[] }[]) => calls.filter((c) => c.fn === 'rect').map((c) => c.args as number[]);

describe('drawKaraoke', () => {
  it('chưa tới từ nào thì không tô màu', () => { const { ctx, calls } = fakeCtx(); drawKaraoke(ctx, [line], 0, 0.8, 800, 400, DEFAULT_STYLE); expect(fills(calls)).toHaveLength(0); });
  it('tô đúng tỉ lệ theo mốc: giữa từ thứ hai = 50% chiều rộng, từ thứ nhất đã đầy', () => {
    const { ctx, calls } = fakeCtx(); drawKaraoke(ctx, [line], 0, 3, 800, 400, DEFAULT_STYLE); const r = fills(calls);
    expect(r).toHaveLength(2); const [w1, w2] = [r[0][2], r[1][2]]; const pad = (400 * 0.07) * 0.2; // chiều rộng từ = 40 (4 ký tự × 10) + đệm 20% cỡ chữ
    expect(w1).toBeCloseTo(40 + pad, 0); expect(w2).toBeCloseTo((40 + pad) * 0.5, 0);
  });
  it('hiệu ứng gõ chữ ẩn từ chưa tới; câu rỗng/ chỉ số sai không lỗi', () => {
    const a = fakeCtx(); drawKaraoke(a.ctx, [line], 0, 1.5, 800, 400, { ...DEFAULT_STYLE, effect: 'type', next: false }); expect(a.calls.filter((c) => c.fn === 'fillText').map((c) => c.args[0])).toContain('abcd');
    expect(a.calls.filter((c) => c.fn === 'fillText').map((c) => c.args[0])).not.toContain('efgh');
    expect(() => drawKaraoke(fakeCtx().ctx, [line], -1, 0, 800, 400, DEFAULT_STYLE)).not.toThrow(); expect(() => drawKaraoke(fakeCtx().ctx, [], 0, 0, 800, 400, DEFAULT_STYLE)).not.toThrow();
  });
});
