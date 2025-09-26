import { createSlice, PayloadAction } from '@reduxjs/toolkit'

type Notification = { id: string; type: 'success' | 'error' | 'info'; message: string }

type NotificationState = {
  items: Notification[]
}

const initialState: NotificationState = {
  items: []
}

const slice = createSlice({
  name: 'notification',
  initialState,
  reducers: {
    push(state, action: PayloadAction<Notification>) {
      state.items.push(action.payload)
    },
    remove(state, action: PayloadAction<string>) {
      state.items = state.items.filter(n => n.id !== action.payload)
    },
    clear(state) {
      state.items = []
    }
  }
})

export const { push, remove, clear } = slice.actions
export default slice.reducer

