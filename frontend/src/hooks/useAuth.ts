import { useCallback } from 'react'
import { useAppDispatch, useAppSelector } from '../store'
import { login, logout } from '../store/authSlice'

export function useAuth() {
  const dispatch = useAppDispatch()
  const token = useAppSelector(s => s.auth.token)
  const loading = useAppSelector(s => s.auth.loading)
  const error = useAppSelector(s => s.auth.error)

  const signIn = useCallback(async (email: string, password: string) => {
    await dispatch(login({ email, password }))
  }, [dispatch])

  const signOut = useCallback(() => {
    dispatch(logout())
  }, [dispatch])

  return { token, loading, error, signIn, signOut }
}


