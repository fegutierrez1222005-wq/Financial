import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAppSelector } from '../store'

export default function Companies() {
  const [rows, setRows] = useState<any[]>([])
  const [name, setName] = useState('')

  const token = useAppSelector(s => s.auth.token)

  function load() {
    if (!token) return
    api.get('/companies').then(r => setRows(r.data)).catch(() => {})
  }

  useEffect(() => { load() }, [])

  async function add() {
    if (!name) return
    await api.post('/companies', { name }).catch(() => {})
    setName('')
    load()
  }

  return (
    <div>
      <h2>Companies</h2>
      <div>
        <input placeholder="Company name" value={name} onChange={e => setName(e.target.value)} />
        <button onClick={add}>Add</button>
      </div>
      <ul>
        {rows.map(r => (
          <li key={r.id}>{r.name}</li>
        ))}
      </ul>
    </div>
  )
}

