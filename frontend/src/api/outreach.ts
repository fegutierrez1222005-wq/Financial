import { api } from './client'
import type { Outreach, OutreachCreate } from '../types/outreach'

export async function listOutreach() {
  const { data } = await api.get<Outreach[]>('/outreach')
  return data
}

export async function sendOutreach(payload: OutreachCreate) {
  const { data } = await api.post<Outreach>('/outreach', {
    to: payload.to_email,
    subject: payload.subject,
    body: payload.body
  })
  return data
}


