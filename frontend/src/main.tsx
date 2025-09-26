import React from 'react'
import ReactDOM from 'react-dom/client'
import { Provider } from 'react-redux'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { store } from './store'
import './index.css'
import { setToken } from './store/authSlice'
import { setAuthToken } from './api/client'

// Restore token from localStorage before rendering
try {
  const saved = localStorage.getItem('auth_token')
  if (saved) {
    store.dispatch(setToken(saved))
    setAuthToken(saved)
  }
} catch {}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  </React.StrictMode>
)

