import type { AIAdapter, AlignRequest, AlignResult, JobProgress } from '../contracts';
import { BackendClient } from '../backend';
import { toTimings } from './mock';

/** Căn lời / nhận diện thật qua API local_studio (Whisper + stable-ts), gồm cả tiếng Nhật. */
export class BackendAIAdapter implements AIAdapter {
  constructor(private client: BackendClient, private pollMs = 1000) {}
  async align(req: AlignRequest, onProgress: (p: JobProgress) => void, signal?: AbortSignal): Promise<AlignResult> {
    if (!req.projectId) throw new Error('Cần chọn một dự án backend (đã tải nhạc lên local_studio).');
    const language = req.language, text = req.lyrics?.trim();
    onProgress({ jobId: req.projectId, state: 'analyzing', percent: 1, message: 'Gửi yêu cầu tới backend…' });
    if (text) await this.client.align(req.projectId, { text, language }); else await this.client.transcribe(req.projectId, { language });
    const done = await this.client.wait(req.projectId, (p) => onProgress({ jobId: req.projectId!, state: text ? 'aligning' : 'recognizing', percent: Math.max(1, Math.min(99, p.progress ?? 0)), message: p.message }), signal, this.pollMs);
    onProgress({ jobId: req.projectId, state: 'done', percent: 100 });
    return { lines: toTimings(this.client.linesOf(done)), engine: 'local_studio', mock: false };
  }
}
