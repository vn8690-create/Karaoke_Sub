// Máy khách cho API local_studio hiện có (FastAPI, mặc định 127.0.0.1:8776). Không sửa backend: chỉ gọi các endpoint đã có.
import { fromSegments, toSegments, type KLine, type Segment } from './karaoke';
export interface BackendProject { id: string; title?: string; status: string; progress?: number; message?: string; error?: string | null; duration: number; segments?: Segment[]; files: Record<string, string> }
export class BackendError extends Error { constructor(public status: number, message: string) { super(message); } }
export interface AlignOptions { text?: string; language: 'vi' | 'en' | 'auto'; model?: 'tiny' | 'base' | 'small' | 'medium' | 'large-v3'; device?: 'auto' | 'cuda' | 'cpu'; separate?: boolean }

export class BackendClient {
  constructor(private base = '', private f: typeof fetch = (...a) => fetch(...a)) {}
  private async req<T>(method: string, path: string, body?: unknown): Promise<T> {
    let r: Response;
    try { r = await this.f(this.base + path, { method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined }); }
    catch { throw new BackendError(0, 'Không kết nối được backend local_studio. Hãy chạy windows\\start.bat rồi thử lại.'); }
    if (!r.ok) { let msg = r.statusText; try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* giữ statusText */ } throw new BackendError(r.status, msg); }
    return r.json() as Promise<T>;
  }
  health = () => this.req<Record<string, unknown>>('GET', '/api/health');
  projects = () => this.req<BackendProject[]>('GET', '/api/projects');
  project = (id: string) => this.req<BackendProject>('GET', `/api/projects/${id}`);
  saveLyrics = (id: string, lines: KLine[], offset = 0) => this.req<BackendProject>('PUT', `/api/projects/${id}/lyrics`, { segments: toSegments(lines, offset) });
  shift = (id: string, offsetSeconds: number) => this.req<BackendProject>('POST', `/api/projects/${id}/timing`, { offset_seconds: offsetSeconds });
  align = (id: string, o: AlignOptions & { text: string }) => this.req<BackendProject>('POST', `/api/projects/${id}/align`, { model: 'small', device: 'auto', separate: true, ...o });
  transcribe = (id: string, o: AlignOptions) => this.req<BackendProject>('POST', `/api/projects/${id}/transcribe`, { model: 'small', device: 'auto', separate: true, ...o });
  fileUrl = (id: string, name: string) => `${this.base}/api/projects/${id}/files/${encodeURIComponent(name)}`;
  /** Hỏi trạng thái cho tới khi xong (ready), lỗi hoặc bị hủy. */
  async wait(id: string, onTick: (p: BackendProject) => void, signal?: AbortSignal, every = 1000): Promise<BackendProject> {
    for (;;) {
      if (signal?.aborted) throw new DOMException('Đã hủy', 'AbortError');
      const p = await this.project(id); onTick(p);
      if (p.status === 'error') throw new BackendError(500, p.error || p.message || 'Backend báo lỗi.');
      if (p.status === 'cancelled') throw new DOMException('Backend đã hủy', 'AbortError');
      if (p.status === 'ready') return p;
      await new Promise((res) => setTimeout(res, every));
    }
  }
  linesOf = (p: BackendProject) => fromSegments(p.segments ?? []);
}
