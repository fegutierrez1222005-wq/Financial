import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAppSelector } from '../store'

export default function Dashboard() {
  const [data, setData] = useState<any>(null)
  const token = useAppSelector(s => s.auth.token)
  useEffect(() => {
    if (!token) return
    api.get('/reports/summary').then(r => setData(r.data)).catch(() => {})
  }, [token])
  return (
    <div>
      <h2>Dashboard</h2>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}

