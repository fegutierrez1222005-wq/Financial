import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { listCompanies, createCompany } from '../api/companies'
import type { Company, CompanyCreate } from '../types/company'

type CompanyState = {
  items: Company[]
  loading: boolean
  error: string | null
}

const initialState: CompanyState = {
  items: [],
  loading: false,
  error: null
}

export const fetchCompanies = createAsyncThunk('companies/fetch', async () => {
  return await listCompanies()
})

export const addCompany = createAsyncThunk('companies/add', async (payload: CompanyCreate) => {
  return await createCompany(payload)
})

const slice = createSlice({
  name: 'company',
  initialState,
  reducers: {},
  extraReducers: builder => {
    builder
      .addCase(fetchCompanies.pending, state => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchCompanies.fulfilled, (state, action: PayloadAction<Company[]>) => {
        state.loading = false
        state.items = action.payload
      })
      .addCase(fetchCompanies.rejected, state => {
        state.loading = false
        state.error = 'Failed to load companies'
      })
      .addCase(addCompany.fulfilled, (state, action: PayloadAction<Company>) => {
        state.items.unshift(action.payload)
      })
  }
})

export default slice.reducer

