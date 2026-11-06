// How each agent looks on the desk: color, icon, short role, and seat on the floor.
import type { AgentKey } from './types'

export interface AgentLook {
  key: AgentKey
  name: string
  role: string
  color: string
  soft: string
  glow: string // lighter shade for the dark panels
  // seat on the floor, in a 1000 x 480 coordinate space
  x: number
  y: number
}

export const AGENT_ORDER: AgentKey[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const AGENTS: Record<AgentKey, AgentLook> = {
  boss: { key: 'boss', glow: '#8fb4e8', name: 'Boss', role: 'Reads the ticket, routes it, makes the call', color: '#14365f', soft: '#e3eaf4', x: 500, y: 58 },
  inventory: { key: 'inventory', glow: '#5fc7b5', name: 'Inventory', role: 'Shelf counts, shortfalls, restock vendors', color: '#1f7a6d', soft: '#e0f1ed', x: 125, y: 228 },
  accounting: { key: 'accounting', glow: '#e0b252', name: 'Accounting', role: 'Cash, invoices, margins, approvals', color: '#a87914', soft: '#f6ecd6', x: 375, y: 278 },
  facilities: { key: 'facilities', glow: '#ef8a6c', name: 'Facilities', role: 'Lease, rent, the shop space', color: '#b4553a', soft: '#f6e3dc', x: 625, y: 278 },
  customer_service: { key: 'customer_service', glow: '#c79ddb', name: 'Customer Service', role: 'Drafts replies (never sends)', color: '#7a4b8c', soft: '#efe5f3', x: 875, y: 228 },
}

export const HUMAN_COLOR = '#2f7a46'

export function agentColor(key: string): string {
  return key in AGENTS ? AGENTS[key as AgentKey].color : HUMAN_COLOR
}

export function AgentIcon({ agent, size = 22 }: { agent: AgentKey | 'human'; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (agent) {
    case 'boss':
      return <svg {...common}><path d="M3 18h18" /><path d="M4 18 3 8l5 4 4-7 4 7 5-4-1 10" /></svg>
    case 'inventory':
      return <svg {...common}><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z" /><path d="M3 7.5 12 12l9-4.5" /><path d="M12 12v9" /></svg>
    case 'accounting':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M15 9.4c-.5-.9-1.6-1.4-3-1.4-1.7 0-3 .8-3 2s1.3 1.6 3 1.9 3 .9 3 2.1-1.3 2-3 2c-1.4 0-2.5-.5-3-1.4" /><path d="M12 6v2M12 16v2" /></svg>
    case 'facilities':
      return <svg {...common}><path d="M4 21V9l8-5 8 5v12" /><path d="M3 21h18" /><path d="M9.5 21v-6h5v6" /><path d="M9 11h.01M15 11h.01" /></svg>
    case 'customer_service':
      return <svg {...common}><path d="M4 5h16v11H10l-5 4v-4H4z" /><path d="M8 9.5h8M8 12.5h5" /></svg>
    default:
      return <svg {...common}><path d="M4 20l4-1 11-11-3-3L5 16z" /><path d="M14 6l3 3" /></svg>
  }
}
