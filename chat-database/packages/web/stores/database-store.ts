import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface ExternalDatabase {
  id: string
  name: string
  dbType?: string
  host: string
  port: number
  database: string
  sslEnabled: boolean
  filePath?: string | null
  createdAt?: string | null
}

interface DatabaseStore {
  selectedDatabaseId: string | null
  databases: ExternalDatabase[]
  isLoading: boolean
  error: string | null
  setSelectedDatabase: (id: string | null) => void
  setDatabases: (databases: ExternalDatabase[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useDatabaseStore = create<DatabaseStore>()(
  persist(
    (set) => ({
      selectedDatabaseId: null,
      databases: [],
      isLoading: false,
      error: null,

      setSelectedDatabase: (id) => set({ selectedDatabaseId: id }),
      setDatabases: (databases) => set({ databases }),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
      reset: () =>
        set({
          selectedDatabaseId: null,
          databases: [],
          isLoading: false,
          error: null,
        }),
    }),
    {
      name: "database-store",
      partialize: (state) => ({
        selectedDatabaseId: state.selectedDatabaseId,
      }),
    }
  )
)
