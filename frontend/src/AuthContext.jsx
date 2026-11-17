import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from './services/api'

const AuthContext = createContext(null)
export function AuthProvider({ children }) {
  const [account, setAccount] = useState(null)
  const [loading, setLoading] = useState(true)
  const [authError, setAuthError] = useState('')
  const refresh = useCallback(async () => {
    try {
      const response = await authApi.me()
      setAccount(response.data.account)
      setAuthError('')
      return response.data.account
    } catch (error) {
      if (error.status === 401) {
        setAccount(null)
        setAuthError('')
      } else {
        setAuthError(error.message || 'Unable to restore your session.')
      }
      return null
    } finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const expire = () => { setAccount(null); setAuthError('') }
    window.addEventListener('fittrack:unauthorized', expire)
    return () => window.removeEventListener('fittrack:unauthorized', expire)
  }, [])
  const authenticate = data => setAccount(data.account)
  const signOut = async () => { try { await authApi.logout() } finally { setAccount(null) } }
  const value = { account, setAccount, loading, authError, refresh, authenticate, signOut }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
export function useAuth() { return useContext(AuthContext) }
