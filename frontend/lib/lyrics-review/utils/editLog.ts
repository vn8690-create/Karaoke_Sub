import type {
  EditLog,
  EditLogEntry,
  EditOperationType,
  EditFeedback,
  EditFeedbackReason,
} from '../types'

let counter = 0

function generateId(): string {
  counter += 1
  return `${Date.now().toString(36)}-${counter.toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

export function createEditLog(jobId: string, audioHash: string): EditLog {
  return {
    session_id: generateId(),
    job_id: jobId,
    audio_hash: audioHash,
    started_at: new Date().toISOString(),
    entries: [],
  }
}

export function addEditEntry(
  log: EditLog,
  operation: EditOperationType,
  opts: {
    segment_id?: string | null
    segment_index?: number | null
    word_ids_before?: string[]
    word_ids_after?: string[]
    text_before?: string
    text_after?: string
    details?: Record<string, unknown>
  }
): EditLogEntry {
  const entry: EditLogEntry = {
    id: generateId(),
    timestamp: new Date().toISOString(),
    operation,
    segment_id: opts.segment_id ?? null,
    segment_index: opts.segment_index ?? null,
    word_ids_before: opts.word_ids_before ?? [],
    word_ids_after: opts.word_ids_after ?? [],
    text_before: opts.text_before ?? '',
    text_after: opts.text_after ?? '',
    details: opts.details,
    feedback: null,
  }
  log.entries.push(entry)
  return entry
}

export function attachFeedback(
  log: EditLog,
  entryId: string,
  reason: EditFeedbackReason
): void {
  const entry = log.entries.find((e) => e.id === entryId)
  if (entry) {
    entry.feedback = {
      reason,
      timestamp: new Date().toISOString(),
    } satisfies EditFeedback
  }
}
