import { api } from './client'

export async function loginApi(payload: { email: string; password: string }) {
  const { data } = await api.post('/auth/login', payload)
  return data as { access_token: string; token_type: string }
}

