import { api } from './client'
import type { DataSource, DataSourceCreate } from '../types'

export async function listDataSources() {
  const { data } = await api.get<DataSource[]>('/data-sources')
  return data
}

export async function createDataSource(payload: DataSourceCreate) {
  const { data } = await api.post<DataSource>('/data-sources', payload)
  return data
}


