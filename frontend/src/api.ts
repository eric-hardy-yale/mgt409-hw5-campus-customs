// Talks to the FastAPI backend at http://localhost:8000 (override with VITE_API_BASE).
import type {
  Approval, ApproveResult, Cash, EventsResponse, Health, RunInfo, Ticket, TicketSummary,
} from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const msg = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : res.statusText
    throw new ApiError(res.status, msg)
  }
  return body as T
}

const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  health: () => req<Health>('/api/health'),
  tickets: () => req<Ticket[]>('/api/tickets'),
  cash: () => req<Cash>('/api/cash'),
  events: (since: number, limit = 1000) => req<EventsResponse>(`/api/events?since=${since}&limit=${limit}`),
  approvals: () => req<Approval[]>('/api/approvals'),
  approve: (approvalId: string, approvedBy: string) =>
    req<ApproveResult>(`/api/approvals/${encodeURIComponent(approvalId)}/approve`, post({ approved_by: approvedBy })),
  run: (ticketId: number) => req<RunInfo>(`/api/tickets/${ticketId}/run`, post()),
  runInfo: (runId: string) => req<RunInfo>(`/api/runs/${runId}`),
  summary: (ticketId: number) => req<TicketSummary>(`/api/tickets/${ticketId}/summary`),
  reset: () => req<{ status: string; tickets: Ticket[]; cash: Cash }>('/api/reset', post()),
}
