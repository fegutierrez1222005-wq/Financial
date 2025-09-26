import { createSlice, createAsyncThunk, PayloadAction, ActionReducerMapBuilder } from '@reduxjs/toolkit'
import { api, setAuthToken } from '../api/client'

type AuthState = {
  token: string | null
  loading: boolean
  error: string | null
}

const initialState: AuthState = {
  token: null,
  loading: false,
  error: null
}

export const login = createAsyncThunk<string, { email: string; password: string }>('auth/login', async (payload) => {
  const { data } = await api.post('/auth/login', payload)
  return data.access_token as string
})

const slice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout(state: AuthState) {
      state.token = null
      setAuthToken(null)
      try {
        localStorage.removeItem('auth_token')
      } catch {}
    },
    setToken(state: AuthState, action: PayloadAction<string | null>) {
      state.token = action.payload
      setAuthToken(action.payload)
      try {
        if (action.payload) {
          localStorage.setItem('auth_token', action.payload)
        } else {
          localStorage.removeItem('auth_token')
        }
      } catch {}
    }
  },
  extraReducers: (builder: ActionReducerMapBuilder<AuthState>) => {
    builder
      .addCase(login.pending, (state: AuthState) => {
        state.loading = true
        state.error = null
      })
      .addCase(login.fulfilled, (state: AuthState, action: PayloadAction<string>) => {
        state.loading = false
        state.token = action.payload
        setAuthToken(action.payload)
        try {
          localStorage.setItem('auth_token', action.payload)
        } catch {}
      })
      .addCase(login.rejected, (state: AuthState) => {
        state.loading = false
        state.error = 'Login failed'
      })
  }
})

export const { logout, setToken } = slice.actions
export default slice.reducer

