import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAppDispatch } from '../../store'
import { logout } from '../../store/authSlice'

export default function Layout() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  function onLogout() {
    dispatch(logout())
    navigate('/login')
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', minHeight: '100vh' }}>
      <aside style={{ borderRight: '1px solid #eee', padding: 16 }}>
        <h3>FDMS</h3>
        <nav style={{ display: 'grid', gap: 8 }}>
          <Link to="/">Dashboard</Link>
          <Link to="/companies">Companies</Link>
          <Link to="/data-sources">Data Sources</Link>
          <Link to="/outreach">Outreach</Link>
          <Link to="/reports">Reports</Link>
          <Link to="/settings">Settings</Link>
          <button onClick={onLogout} style={{ marginTop: 12 }}>Logout</button>
        </nav>
      </aside>
      <main style={{ padding: 24 }}>
        <Outlet />
      </main>
    </div>
  )
}

