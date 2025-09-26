export type Company = {
  id: number
  name: string
  website?: string | null
  industry?: string | null
  country?: string | null
  last_updated_at?: string | null
  created_at: string
  updated_at: string
}

export type CompanyCreate = {
  name: string
  website?: string
  industry?: string
  country?: string
}
