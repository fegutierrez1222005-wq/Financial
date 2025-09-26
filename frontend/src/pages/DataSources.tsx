import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAppSelector } from '../store'

export default function DataSources() {
  const [rows, setRows] = useState<any[]>([])
  const [name, setName] = useState('pitchbook')

  const token = useAppSelector(s => s.auth.token)

  function load() {
    if (!token) return
    api.get('/data-sources').then(r => setRows(r.data)).catch(() => {})
  }

  useEffect(() => { load() }, [])

  async function add() {
    if (!name) return
    await api.post('/data-sources', { name }).catch(() => {})
    setName('')
    load()
  }

  return (
    <div>
      <h2>Data Sources</h2>
      <div>
        <input placeholder="Source name" value={name} onChange={e => setName(e.target.value)} />
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

