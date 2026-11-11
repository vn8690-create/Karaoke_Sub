import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { BackendClient, BackendError } from '../src/backend';
import { BackendAIAdapter } from '../src/adapters/backend';
import { makeLine, toSegments } from '../src/karaoke';
import type { JobProgress } from '../src/contracts';

// Máy chủ giả mô phỏng đúng hình dạng API local_studio (xem local_studio/app.py): không phải backend thật.
let srv: http.Server, base = '', polls = 0, mode: 'ok' | 'fail' = 'ok';
const proj = { id: 'p1', title: 'Bài thử', status: 'ready', progress: 100, message: '', error: null as string | null, duration: 20, files: { audio: 'audio.mp3' } as Record<string, string>, segments: [] as unknown[] };
const body = (req: http.IncomingMessage) => new Promise<string>((res) => { let d = ''; req.on('data', (c) => (d += c)); req.on('end', () => res(d)); });
beforeAll(async () => {
  srv = http.createServer(async (req, res) => {
    const send = (code: number, o: unknown) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    const url = req.url ?? '';
    if (url === '/api/health') return send(200, { ok: true });
    if (url === '/api/projects' && req.method === 'POST') {
      const form = await body(req);
      if (!req.headers['content-type']?.includes('multipart/form-data') || !form.includes('name="source"') || !form.includes('name="title"')) return send(400, { detail: 'Multipart upload required' });
      return send(201, proj);
    }
    if (url === '/api/projects') return send(200, [proj]);
    if (req.method === 'GET' && url === '/api/projects/p1') {
      if (proj.status === 'processing' && ++polls >= 2) { if (mode === 'fail') { proj.status = 'error'; proj.error = 'Không tìm được mốc thời gian cho lời chuẩn.'; } else { proj.status = 'ready'; proj.progress = 100; } }
      return send(200, proj);
    }
    if (req.method === 'POST' && url === '/api/projects/p1/render') {
      const opts = JSON.parse(await body(req));
      if (opts.audio_mode !== 'original') return send(400, { detail: 'Test requires original audio' });
      proj.files.video = 'karaoke.mp4'; proj.status = 'processing'; proj.progress = 15; polls = 0;
      return send(202, proj);
    }
    if (req.method === 'POST' && url === '/api/projects/p1/subtitles') {
      proj.files.srt = 'lyrics.srt'; proj.files.ass = 'lyrics.ass'; proj.files.lrc = 'lyrics.lrc'; return send(200, proj);
    }
    if (req.method === 'POST' && url === '/api/projects/p1/render/cancel') return send(200, { status: 'cancelling', message: 'OK' });
    if (req.method === 'GET' && url === '/api/projects/p1/quality') return send(200, { ok: true, issues: [] });
    if (req.method === 'PUT' && url === '/api/projects/p1/lyrics') {
      const b = JSON.parse(await body(req)); for (const s of b.segments) for (const w of s.words) if (w.end <= w.start) return send(400, { detail: 'Từ phải có nội dung và thời gian kết thúc lớn hơn bắt đầu.' });
      proj.segments = b.segments; return send(200, proj);
    }
    if (req.method === 'POST' && (url === '/api/projects/p1/align' || url === '/api/projects/p1/transcribe')) {
      const b = JSON.parse((await body(req)) || '{}'); polls = 0; proj.status = 'processing'; proj.progress = 40; proj.message = 'Đang căn…';
      proj.segments = toSegments([makeLine(b.text?.includes('Lời đúng trong TXT') ? 'Whisper trả lời sai' : (b.text ?? 'Lời nhận diện thử'), 1, 6)!]); return send(202, proj);
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
  it('TXT là lời chuẩn: backend trả khác dù timestamp hợp lệ thì không chấp nhận', async () => {
    const ad = new BackendAIAdapter(new BackendClient(base), 1);
    await expect(ad.align({
      audioPath: '', language: 'vi', engine: 'backend', projectId: 'p1',
      lyrics: '[Intro]\\nLời đúng trong TXT',
    }, () => undefined)).rejects.toThrow(/khác nội dung TXT chuẩn/);
  });
  it('không lời → dùng transcribe', async () => {
    const ev: JobProgress[] = []; await new BackendAIAdapter(new BackendClient(base), 1).align({ audioPath: '', language: 'auto', engine: 'backend', projectId: 'p1' }, (p) => ev.push(p)); expect(ev.some((e) => e.state === 'recognizing')).toBe(true);
  });
  it('backend báo lỗi, tiếng Nhật được chấp nhận, thiếu dự án bị từ chối', async () => {
    mode = 'fail'; const ad = new BackendAIAdapter(new BackendClient(base), 1);
    await expect(ad.align({ audioPath: '', language: 'vi', engine: 'backend', projectId: 'p1', lyrics: 'x y' }, () => undefined)).rejects.toThrow(/mốc thời gian/); mode = 'ok';
    const japanese = await ad.align({ audioPath: '', language: 'ja', engine: 'backend', projectId: 'p1', lyrics: 'お母さん は 怖い' }, () => undefined); expect(japanese.mock).toBe(false);
    await expect(ad.align({ audioPath: '', language: 'vi', engine: 'backend' }, () => undefined)).rejects.toThrow(/dự án backend/);
  });
  it('upload file thật bằng multipart, xuất phụ đề, MP4 và kiểm tra chất lượng', async () => {
    const c = new BackendClient(base);
    const f = new File([new Uint8Array([82, 73, 70, 70])], 'nhac.wav', { type: 'audio/wav' });
    await expect(c.createProject(f, 'Bài test')).resolves.toMatchObject({ id: 'p1' });
    await expect(c.subtitles('p1', { resolution: '720p', font_size: 54 })).resolves.toMatchObject({ files: { srt: 'lyrics.srt' } });
    await expect(c.render('p1', { audio_mode: 'original', resolution: '720p' })).resolves.toMatchObject({ status: 'processing' });
    const done = await c.wait('p1', () => undefined, undefined, 1);
    expect(done.files.video).toBe('karaoke.mp4');
    expect((await c.quality('p1')).ok).toBe(true);
    expect(c.fileUrl('p1', 'karaoke.mp4')).toContain('/api/projects/p1/files/karaoke.mp4');
    expect((await c.cancelRender('p1')).status).toBe('cancelling');
  });
  it('hủy trong lúc chờ → AbortError; backend tắt → thông báo kết nối rõ ràng', async () => {
    const ctl = new AbortController(); proj.status = 'processing'; polls = -1000; ctl.abort();
    await expect(new BackendClient(base).wait('p1', () => undefined, ctl.signal, 1)).rejects.toMatchObject({ name: 'AbortError' }); proj.status = 'ready';
    const err = await new BackendClient('http://127.0.0.1:1').health().catch((e) => e); expect(err).toBeInstanceOf(BackendError); expect(err.message).toMatch(/start\.bat/);
  });
});
