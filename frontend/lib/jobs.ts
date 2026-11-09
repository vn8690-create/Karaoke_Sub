import { create } from "zustand"
import type { Job, JobStatus } from "./types"

interface JobsStore {
  jobs: Job[]
  addJob: (job: Omit<Job, "id" | "createdAt" | "updatedAt" | "progress" | "stages">) => void
  updateJobStatus: (id: string, status: JobStatus) => void
  getJobById: (id: string) => Job | undefined
  getUserJobs: (userId: string) => Job[]
}

// Mock initial jobs for demo
const mockJobs: Job[] = [
  {
    id: "1",
    userId: "demo",
    artist: "Journey",
    title: "Don't Stop Believin'",
    status: "completed",
    sourceType: "youtube",
    sourceUrl: "https://youtube.com/watch?v=example",
    progress: 100,
    createdAt: new Date(Date.now() - 86400000 * 2).toISOString(),
    updatedAt: new Date(Date.now() - 86400000).toISOString(),
    stages: [
      { name: "Audio Extraction", status: "completed", progress: 100 },
      { name: "Vocal Separation", status: "completed", progress: 100 },
      { name: "Lyrics Sync", status: "completed", progress: 100 },
      { name: "Video Generation", status: "completed", progress: 100 },
    ],
    resultUrl: "/downloads/journey-dont-stop-believin.mp4",
  },
  {
    id: "2",
    userId: "demo",
    artist: "Queen",
    title: "Bohemian Rhapsody",
    status: "processing",
    sourceType: "upload",
    fileName: "bohemian-rhapsody.mp3",
    progress: 65,
    createdAt: new Date(Date.now() - 3600000).toISOString(),
    updatedAt: new Date(Date.now() - 600000).toISOString(),
    stages: [
      { name: "Audio Extraction", status: "completed", progress: 100 },
      { name: "Vocal Separation", status: "completed", progress: 100 },
      { name: "Lyrics Sync", status: "in_progress", progress: 60 },
      { name: "Video Generation", status: "pending", progress: 0 },
    ],
  },
]

export const useJobs = create<JobsStore>((set, get) => ({
  jobs: mockJobs,
  addJob: (jobData) => {
    const newJob: Job = {
      ...jobData,
      id: Math.random().toString(36).substr(2, 9),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      progress: 0,
      stages: [
        { name: "Audio Extraction", status: "pending", progress: 0 },
        { name: "Vocal Separation", status: "pending", progress: 0 },
        { name: "Lyrics Sync", status: "pending", progress: 0 },
        { name: "Video Generation", status: "pending", progress: 0 },
      ],
    }
    set((state) => ({ jobs: [newJob, ...state.jobs] }))
  },
  updateJobStatus: (id, status) =>
    set((state) => ({
      jobs: state.jobs.map((job) => (job.id === id ? { ...job, status, updatedAt: new Date().toISOString() } : job)),
    })),
  getJobById: (id) => get().jobs.find((job) => job.id === id),
  getUserJobs: (userId) => get().jobs.filter((job) => job.userId === userId),
}))
