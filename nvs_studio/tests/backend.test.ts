import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { BackendClient, BackendError } from '../src/backend';
import { BackendAIAdapter } from '../src/adapters/backend';
import { makeLine, toSegments } from '../src/karaoke';
import type { JobProgress } from '../src/contracts';

// Máy chủ giả mô phỏng đúng hình dạng API local_studio (xem local_studio/app.py): không phải backend thật.
let srv: http.Server, base = '', polls = 0, mode: 'ok' | 'fail' = 'ok';
const proj = { id: 'p1', title: 'Bài thử', status: 'ready', progress: 100, message: '', error: null as string | null, duration: 20, files: { audio: 'audio.mp3' }, segments: [] as unknown[] };
const body = (req: http.IncomingMessage) => new Promise<string>((res) => { let d = ''; req.on('data', (c) => (d += c)); req.on('end', () => res(d)); });
beforeAll(async () => {
  srv = http.createServer(async (req, res) => {
    const send = (code: number, o: unknown) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    const url = req.url ?? '';
    if (url === '/api/health') return send(200, { ok: true });
    if (url === '/api/projects') return send(200, [proj]);
    if (req.method === 'GET' && url === '/api/projects/p1') {
      if (proj.status === 'processing' && ++polls >= 2) { if (mode === 'fail') { proj.status = 'error'; proj.error = 'Không tìm được mốc thời gian cho lời chuẩn.'; } else { proj.status = 'ready'; proj.progress = 100; } }
      return send(200, proj);
    }
    if (req.method === 'PUT' && url === '/api/projects/p1/lyrics') {
      const b = JSON.parse(await body(req)); for (const s of b.segments) for (const w of s.words) if (w.end <= w.start) return send(400, { detail: 'Từ phải có nội dung và thời gian kết thúc lớn hơn bắt đầu.' });
      proj.segments = b.segments; return send(200, proj);
    }
    if (req.method === 'POST' && (url === '/api/projects/p1/align' || url === '/api/projects/p1/transcribe')) {
      const b = JSON.parse((await body(req)) || '{}'); polls = 0; proj.status = 'processing'; proj.progress = 40; proj.message = 'Đang căn…';
      proj.segments = toSegments([makeLine(b.text ?? 'Lời nhận diện thử', 1, 6)!]); return send(202, proj);
    }
    send(404, { detail: 'Không tìm thấy' });
  });
  await new Promise<void>((r) => srv.listen(0, '127.0.0.1', r)); base = `http://127.0.0.1:${(srv.address() as AddressInfo).port}`;
});
afterAll(() => srv.close());

describe('BackendClient + BackendAIAdapter (máy chủ giả)', () => {
  it('liệt kê dự án, lưu lời hợp lệ, hiện lỗi tiếng Việt khi backend từ chối', async () => {
    const c = new BackendClient(base); expect((await c.projects())[0].id).toBe('p1');
    const ok = makeLine('Xin chào bạn', 1, 4)!; await expect(c.saveLyrics('p1', [ok])).resolves.toMatchObject({ id: 'p1' });
    const bad = makeLine('Xin chào bạn', 1, 4)!; bad.words[0].end = bad.words[0].start;
    await expect(c.saveLyrics('p1', [bad])).rejects.toMatchObject({ status: 400, message: expect.stringContaining('kết thúc lớn hơn') });
  });
  it('căn lời thật: gửi align, đọc tiến độ rồi trả lời đã giữ nguyên chữ', async () => {
    const ev: JobProgress[] = []; const r = await new BackendAIAdapter(new BackendClient(base), 1).align({ audioPath: '', language: 'vi', engine: 'backend', projectId: 'p1', lyrics: 'Một hai ba' }, (p) => ev.push(p));
    expect(r.mock).toBe(false); expect(r.lines[0].text).toBe('Một hai ba'); expect(ev[0].state).toBe('analyzing'); expect(ev.at(-1)!.state).toBe('done'); expect(ev.some((e) => e.state === 'aligning')).toBe(true);
  });
  it('không lời → dùng transcribe', async () => {
    const ev: JobProgress[] = []; await new BackendAIAdapter(new BackendClient(base), 1).align({ audioPath: '', language: 'auto', engine: 'backend', projectId: 'p1' }, (p) => ev.push(p)); expect(ev.some((e) => e.state === 'recognizing')).toBe(true);
  });
  it('backend báo lỗi → hiện đúng thông điệp; tiếng Nhật và thiếu dự án bị từ chối trước khi gọi', async () => {
    mode = 'fail'; const ad = new BackendAIAdapter(new BackendClient(base), 1);
    await expect(ad.align({ audioPath: '', language: 'vi', engine: 'backend', projectId: 'p1', lyrics: 'x y' }, () => undefined)).rejects.toThrow(/mốc thời gian/); mode = 'ok';
    await expect(ad.align({ audioPath: '', language: 'ja', engine: 'backend', projectId: 'p1' }, () => undefined)).rejects.toThrow(/tiếng Nhật/);
    await expect(ad.align({ audioPath: '', language: 'vi', engine: 'backend' }, () => undefined)).rejects.toThrow(/dự án backend/);
  });
  it('hủy trong lúc chờ → AbortError; backend tắt → thông báo kết nối rõ ràng', async () => {
    const ctl = new AbortController(); proj.status = 'processing'; polls = -1000; ctl.abort();
    await expect(new BackendClient(base).wait('p1', () => undefined, ctl.signal, 1)).rejects.toMatchObject({ name: 'AbortError' }); proj.status = 'ready';
    const err = await new BackendClient('http://127.0.0.1:1').health().catch((e) => e); expect(err).toBeInstanceOf(BackendError); expect(err.message).toMatch(/start\.bat/);
  });
});
