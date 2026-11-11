/** Full real-backend smoke: requires NVS_REAL_BACKEND_URL and local FFmpeg/FastAPI.
 * Does not download AI models. Uses generated 2-second WAV with deterministic lyrics.
 */
import { describe, expect, it } from 'vitest';
import { BackendClient } from '../src/backend';
import { makeLine } from '../src/karaoke';

function makeWav(seconds = 2): File {
  const sampleRate = 44100, sampleCount = sampleRate * seconds;
  const bytes = new Uint8Array(44 + sampleCount * 2), view = new DataView(bytes.buffer);
  const tag = (at: number, name: string) => { for (let i = 0; i < name.length; i++) bytes[at + i] = name.charCodeAt(i); };
  tag(0, 'RIFF'); view.setUint32(4, 36 + sampleCount * 2, true); tag(8, 'WAVE');
  tag(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  tag(36, 'data'); view.setUint32(40, sampleCount * 2, true);
  for (let i = 0; i < sampleCount; i++) view.setInt16(44 + 2 * i, Math.round(12000 * Math.sin(i * 440 * Math.PI * 2 / sampleRate)), true);
  return new File([bytes], 'nhac-thu.wav', { type: 'audio/wav' });
}

describe('NVS client connected to actual FastAPI local_studio (no mock)', () => {
  it.skipIf(!process.env.NVS_REAL_BACKEND_URL)(
    'uploads a WAV, saves timed lyrics, exports subtitles, renders 720p MP4 and downloads it',
    async () => {
      const client = new BackendClient(process.env.NVS_REAL_BACKEND_URL);
      const health = await client.health();
      expect(health.ok).toBe(true);
      const page = await fetch(process.env.NVS_REAL_BACKEND_URL + '/nvs/');
      expect(page.ok).toBe(true);
      expect(await page.text()).toContain('/nvs/assets/');

      const created = await client.createProject(makeWav(), 'NVS Bridge Smoke Test');
      expect(created.id).toMatch(/^[a-f0-9]{32}$/);
      expect(created.duration).toBeGreaterThan(1.9);
      expect(created.files.audio).toBe('audio.wav');

      const line = makeLine('Xin chào Karaoke', 0.25, 1.75);
      expect(line).not.toBeNull();
      const saved = await client.saveLyrics(created.id, [line!]);
      expect(saved.segments?.[0]?.words.length).toBeGreaterThan(1);
      expect(client.linesOf(await client.project(created.id))[0].words.length).toBeGreaterThan(1);

      const subs = await client.subtitles(created.id, { resolution: '720p', font_size: 40 });
      expect(subs.files.ass).toBe('lyrics.ass');
      const srt = await fetch(client.fileUrl(created.id, subs.files.srt));
      expect(srt.ok).toBe(true);
      expect(await srt.text()).toContain('Xin');

      const queued = await client.render(created.id, { audio_mode: 'original', resolution: '720p', font_size: 40 });
      expect(['queued', 'rendering']).toContain(queued.status);
      const ready = await client.wait(created.id, () => undefined, undefined, 200);
      expect(ready.files.video).toBe('karaoke.mp4');
      const quality = await client.quality(created.id);
      expect(quality.ok).toBe(true);

      const video = await fetch(client.fileUrl(created.id, ready.files.video));
      expect(video.status).toBe(200);
      expect(video.headers.get('content-type')).toContain('video/mp4');
      expect((await video.arrayBuffer()).byteLength).toBeGreaterThan(1000);

      const backup = await fetch(client.backupUrl(created.id));
      expect(backup.ok).toBe(true);
      expect(backup.headers.get('content-type')).toContain('application/zip');
      expect((await backup.arrayBuffer()).byteLength).toBeGreaterThan(1000);
    }, 120_000,
  );
});
