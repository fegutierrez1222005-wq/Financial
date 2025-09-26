import { configureStore } from '@reduxjs/toolkit'
import authReducer from './authSlice'
import companyReducer from './companySlice'
import notificationReducer from './notificationSlice'
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    company: companyReducer,
    notification: notificationReducer
  }
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
export const useAppDispatch: () => AppDispatch = useDispatch
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector

