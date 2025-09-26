export type DataSource = {
  id: number
  name: string
  base_url?: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export type DataSourceCreate = {
  name: string
  base_url?: string
}


