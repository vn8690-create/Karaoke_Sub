// Local Studio backend client. Dev requests use Vite /api proxy; production is same-origin /api.
import { fromSegments, toSegments, type KLine, type Segment } from './karaoke';
export interface BackendProject { id: string; title?: string; status: string; progress?: number; message?: string; error?: string | null; duration: number; segments?: Segment[]; files: Record<string, string> }
export class BackendError extends Error { constructor(public status: number, message: string) { super(message); this.name = 'BackendError'; } }
export type Language = 'vi' | 'en' | 'ja' | 'auto';
export interface AlignOptions { text?: string; language: Language; model?: 'tiny' | 'base' | 'small' | 'medium' | 'large-v3'; device?: 'auto' | 'cuda' | 'cpu'; separate?: boolean }
export interface RenderOptions {
  audio_mode: 'original' | 'instrumental' | 'silent';
  resolution: '720p' | '1080p';
  font_size?: number;
  font_family?: 'Arial' | 'Tahoma' | 'Segoe UI' | 'Times New Roman';
  text_color?: string; highlight_color?: string; position?: 'bottom' | 'center' | 'top'; margin_percent?: number;
}
export type SubtitleOptions = Omit<RenderOptions, 'audio_mode'>;

export class BackendClient {
  constructor(private base = '', private f: typeof fetch = (...a) => fetch(...a)) {}
  private async response<T>(method: string, path: string, body?: BodyInit, json = false, signal?: AbortSignal): Promise<T> {
    let r: Response;
    try { r = await this.f(this.base + path, { method, headers: json ? { 'Content-Type': 'application/json' } : undefined, body, signal }); }
    catch { if (signal?.aborted) throw new DOMException('Đã hủy', 'AbortError'); throw new BackendError(0, 'Không kết nối được backend local_studio. Hãy chạy windows\start.bat rồi thử lại.'); }
    if (!r.ok) {
      let msg = r.statusText || 'Backend báo lỗi';
      try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* keep HTTP status */ }
      throw new BackendError(r.status, msg);
    }
    return r.json() as Promise<T>;
  }
  private req<T>(method: string, path: string, body?: unknown, signal?: AbortSignal) {
    return this.response<T>(method, path, body === undefined ? undefined : JSON.stringify(body), body !== undefined, signal);
  }
  health = () => this.req<Record<string, unknown>>('GET', '/api/health');
  projects = () => this.req<BackendProject[]>('GET', '/api/projects');
  project = (id: string) => this.req<BackendProject>('GET', '/api/projects/' + encodeURIComponent(id));

  createProject(source: File, title?: string, signal?: AbortSignal): Promise<BackendProject> {
    if (!source || !source.size) return Promise.reject(new Error('Hãy chọn file nhạc không rỗng.'));
    const data = new FormData();
    data.append('source', source, source.name);
    data.append('title', title?.trim() || source.name.replace(/\.[^.]+$/, ''));
    return this.response<BackendProject>('POST', '/api/projects', data, false, signal);
  }

  saveLyrics = (id: string, lines: KLine[], offset = 0) => this.req<BackendProject>('PUT', '/api/projects/' + encodeURIComponent(id) + '/lyrics', { segments: toSegments(lines, offset) });
  shift = (id: string, offsetSeconds: number) => this.req<BackendProject>('POST', '/api/projects/' + encodeURIComponent(id) + '/timing', { offset_seconds: offsetSeconds });
  align = (id: string, o: AlignOptions & { text: string }) => this.req<BackendProject>('POST', '/api/projects/' + encodeURIComponent(id) + '/align', { model: 'small', device: 'auto', separate: true, ...o });
  transcribe = (id: string, o: AlignOptions) => this.req<BackendProject>('POST', '/api/projects/' + encodeURIComponent(id) + '/transcribe', { model: 'small', device: 'auto', separate: true, ...o });
  subtitles = (id: string, o: SubtitleOptions) => this.req<BackendProject>('POST', '/api/projects/' + encodeURIComponent(id) + '/subtitles', o);
  render = (id: string, o: RenderOptions) => this.req<BackendProject>('POST', '/api/projects/' + encodeURIComponent(id) + '/render', o);
  cancelRender = (id: string) => this.req<{ status: string; message: string }>('POST', '/api/projects/' + encodeURIComponent(id) + '/render/cancel');
  quality = (id: string) => this.req<{ ok: boolean; issues: { code: string; message: string }[] }>('GET', '/api/projects/' + encodeURIComponent(id) + '/quality');
  fileUrl = (id: string, name: string) => this.base + '/api/projects/' + encodeURIComponent(id) + '/files/' + encodeURIComponent(name);
  backupUrl = (id: string) => this.base + '/api/projects/' + encodeURIComponent(id) + '/backup';

  /** Poll until ready/error/cancelled. Abort only stops polling, not the backend AI job. */
  async wait(id: string, onTick: (p: BackendProject) => void, signal?: AbortSignal, every = 1000): Promise<BackendProject> {
    for (;;) {
      if (signal?.aborted) throw new DOMException('Đã hủy', 'AbortError');
      const p = await this.req<BackendProject>('GET', '/api/projects/' + encodeURIComponent(id), undefined, signal);
      onTick(p);
      if (p.status === 'error') throw new BackendError(500, p.error || p.message || 'Backend báo lỗi.');
      if (p.status === 'cancelled') throw new DOMException('Backend đã hủy', 'AbortError');
      if (p.status === 'ready') return p;
      await new Promise<void>((resolve, reject) => {
        if (signal?.aborted) { reject(new DOMException('Đã hủy', 'AbortError')); return; }
        const finish = () => { signal?.removeEventListener('abort', abort); resolve(); };
        const timer = setTimeout(finish, every);
        const abort = () => { clearTimeout(timer); signal?.removeEventListener('abort', abort); reject(new DOMException('Đã hủy', 'AbortError')); };
        signal?.addEventListener('abort', abort, { once: true });
      });
    }
  }
  linesOf = (p: BackendProject) => fromSegments(p.segments ?? []);
}
