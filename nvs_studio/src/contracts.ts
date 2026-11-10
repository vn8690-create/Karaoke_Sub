// API contract cho backend (Codex tích hợp). Frontend chỉ gọi các adapter này, không nhúng API key.
export type JobState = 'idle' | 'model-missing' | 'downloading-model' | 'analyzing' | 'recognizing' | 'aligning' | 'done' | 'error' | 'cancelled';
export interface WordTiming { text: string; start: number; end: number }
export interface LineTiming { text: string; start: number; end: number; words: WordTiming[] }
export interface AlignRequest { audioPath: string; language: 'vi' | 'ja' | 'en' | 'auto'; lyrics?: string; engine: 'whisper' | 'karaoke-gen' }
export interface AlignResult { lines: LineTiming[]; engine: string; mock: boolean }
export interface JobProgress { jobId: string; state: JobState; percent: number; message?: string }
export interface AIAdapter {
  align(req: AlignRequest, onProgress: (p: JobProgress) => void, signal?: AbortSignal): Promise<AlignResult>;
  separateVocals(audioPath: string, onProgress: (p: JobProgress) => void, signal?: AbortSignal): Promise<{ vocalPath: string; instrumentalPath: string }>;
}
export interface RenderSettings { codec: 'h264' | 'h265'; width: number; height: number; fps: 24 | 25 | 30 | 60; bitrateKbps: number; gpu: boolean; outputDir: string }
export interface RenderAdapter {
  enqueue(projectPath: string, settings: RenderSettings): Promise<{ jobId: string }>;
  progress(jobId: string): AsyncIterable<JobProgress>;
  cancel(jobId: string): Promise<void>;
}
export interface ProjectStorageAdapter { save(name: string, json: string): Promise<void>; load(name: string): Promise<string>; list(): Promise<string[]> }
export interface SystemInfo { gpu: string | null; vramTotalMB: number | null; vramFreeMB: number | null; ramTotalMB: number; ramFreeMB: number; cpuThreads: number }
