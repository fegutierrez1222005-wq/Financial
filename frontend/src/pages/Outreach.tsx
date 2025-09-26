import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAppSelector } from '../store'

export default function Outreach() {
  const [rows, setRows] = useState<any[]>([])
  const [to, setTo] = useState('banker@example.com')
  const [subject, setSubject] = useState('Request for updated financials')
  const [body, setBody] = useState('Hello, could you share updated financials?')

  const token = useAppSelector(s => s.auth.token)

  function load() {
    if (!token) return
    api.get('/outreach').then(r => setRows(r.data)).catch(() => {})
  }

  useEffect(() => { load() }, [])

  async function send() {
    await api.post('/outreach', { to, subject, body }).catch(() => {})
    load()
  }

  return (
    <div>
      <h2>Outreach</h2>
      <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
        <input placeholder="to" value={to} onChange={e => setTo(e.target.value)} />
        <input placeholder="subject" value={subject} onChange={e => setSubject(e.target.value)} />
        <textarea placeholder="body" value={body} onChange={e => setBody(e.target.value)} />
        <button onClick={send}>Send</button>
      </div>
      <h3>History</h3>
      <ul>
        {rows.map(r => (
          <li key={r.id}>{r.to_email} - {r.status}</li>
        ))}
      </ul>
    </div>
  )
}

