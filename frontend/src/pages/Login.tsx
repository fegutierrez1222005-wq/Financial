import { FormEvent, useState } from 'react'
import { useAppDispatch, useAppSelector } from '../store'
import { login } from '../store/authSlice'
import { Navigate } from 'react-router-dom'

export default function Login() {
  const dispatch = useAppDispatch()
  const { token, loading, error } = useAppSelector(s => s.auth)
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('Nitrozox')

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    await dispatch(login({ email, password }))
  }

  if (token) return <Navigate to="/" />

  return (
    <div style={{ maxWidth: 360, margin: '10vh auto', padding: 24, border: '1px solid #ddd' }}>
      <h2>Login</h2>
      <form onSubmit={onSubmit}>
        <div>
          <label>Email</label>
          <input value={email} onChange={e => setEmail(e.target.value)} style={{ width: '100%' }} />
        </div>
        <div style={{ marginTop: 12 }}>
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ width: '100%' }} />
        </div>
        <button type="submit" disabled={loading} style={{ marginTop: 16 }}>Sign in</button>
        {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
      </form>
    </div>
  )
}

