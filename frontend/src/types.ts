// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentKey = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Health {
  ok: boolean
  model: string
  portkey_key_set: boolean
  database: string
  run_in_progress: string | null
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  resolved: boolean
  state: 'open' | 'resolved'
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  today: string
}

export interface Usage {
  requests: number
  tool_calls: number
  input_tokens: number
  output_tokens: number
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown> | null
}

export interface ToolResult {
  tool: string | null
  result: unknown
}

export interface Delegation {
  to: AgentKey | null
  task: string | null
  status: string | null
  reason: string | null
  summary: string | null
}

export interface AgentEvent {
  seq: number
  ts: string
  run_id: string
  ticket_id: number | null
  agent: AgentKey | 'human'
  agent_name: string
  chain: string[]
  step: number | null
  event: string
  said: string | null
  tools: ToolCall[]
  tool_results: ToolResult[]
  output: Record<string, unknown> | null
  delegation: Delegation | null
  model: string | null
  usage: Usage | null
}

export interface EventsResponse {
  events: AgentEvent[]
  next_since: number
  run_in_progress: string | null
}

export interface Approval {
  approval_id: string
  run_id: string
  ticket_id: number
  proposed_at: string
  kind: 'payment' | 'purchase_order' | 'discount'
  summary: string
  amount: number | null
  ref: Record<string, unknown>
  reason: string
  status: 'pending' | 'approved'
  approved_by: string | null
  last_refusal?: string | null
}

export interface ApproveResult {
  status: string
  approval_id: string | null
  result: Record<string, unknown>
  cash?: { account: string; balance: number; as_of: string }[]
  cash_changed?: boolean
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'error'
  started_at: string
  finished_at: string | null
  error: string | null
}

export interface AgentSummary {
  agent: AgentKey
  name: string
  used: boolean
  asked_by: string[]
  tools: Record<string, number>
  delegated_to: { to: AgentKey; name: string; task: string }[]
  refused_delegations: number
  steps: number
  input_tokens: number
  output_tokens: number
  summary: string | null
  output: Record<string, unknown> | null
  error: string | null
}

export interface TicketSummary {
  ticket_id: number
  run_id: string | null
  started_at?: string
  status: 'not_run' | 'running' | 'done' | 'error' | 'stopped'
  usage?: Usage | null
  agents: AgentSummary[]
}
