// MOCK: dữ liệu và tiến trình GIẢ LẬP để thử giao diện. Không nhận diện giọng thật.
import type { AIAdapter, AlignRequest, AlignResult, JobProgress, JobState, LineTiming } from '../contracts';
import { plainToLines, type KLine } from '../karaoke';

const sleep = (ms: number, signal?: AbortSignal) => new Promise<void>((res, rej) => {
  if (signal?.aborted) return rej(new DOMException('Đã hủy', 'AbortError'));
  const id = setTimeout(res, ms); signal?.addEventListener('abort', () => { clearTimeout(id); rej(new DOMException('Đã hủy', 'AbortError')); }, { once: true });
});
export const toTimings = (lines: KLine[]): LineTiming[] => lines.map((l) => ({ text: l.words.map((w) => w.text).join(l.sep), start: l.words[0].start, end: l.words.at(-1)!.end, words: l.words.map((w) => ({ ...w })) }));
export const MOCK_TEXT: Record<string, string> = { vi: 'Đây là dòng lời mẫu một\nĐây là dòng lời mẫu hai\nĐây là dòng lời mẫu ba\nĐây là dòng lời mẫu bốn', ja: 'これはサンプルの歌詞です\nもう一行のサンプルです', en: 'This is the first sample line\nThis is the second sample line' };

export class MockAIAdapter implements AIAdapter {
  constructor(private tickMs = 250, private ticks = 12) {}
  async align(req: AlignRequest, onProgress: (p: JobProgress) => void, signal?: AbortSignal): Promise<AlignResult> {
    const state = (pc: number): JobState => (pc < 30 ? 'analyzing' : pc < 60 ? 'recognizing' : 'aligning');
    try {
      for (let i = 0; i <= this.ticks; i++) { const pc = Math.round((i / this.ticks) * 95); onProgress({ jobId: 'mock', state: state(pc), percent: pc, message: 'MOCK: tiến trình giả lập' }); await sleep(this.tickMs, signal); }
    } catch (e) { onProgress({ jobId: 'mock', state: 'cancelled', percent: 0 }); throw e; }
    const text = req.lyrics?.trim() || MOCK_TEXT[req.language] || MOCK_TEXT.vi;
    const lines = plainToLines(text, req.durationSec ?? 60, req.language === 'ja' ? 'ja' : undefined);
    onProgress({ jobId: 'mock', state: 'done', percent: 100 });
    return { lines: toTimings(lines), engine: 'mock', mock: true };
  }
}
