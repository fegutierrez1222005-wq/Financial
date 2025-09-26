export type Outreach = {
  id: number
  to_email: string
  subject: string
  body: string
  status: string
  created_at: string
  updated_at: string
}

export type OutreachCreate = {
  to_email: string
  subject: string
  body: string
}


