import { api } from './client'
import type { Company, CompanyCreate } from '../types/company'

export async function listCompanies() {
  const { data } = await api.get<Company[]>('/companies')
  return data
}

export async function createCompany(payload: CompanyCreate) {
  const { data } = await api.post<Company>('/companies', payload)
  return data
}


