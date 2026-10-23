import type { CognitoUser } from 'amazon-cognito-identity-js'
import { ScanSearch } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { completeNewPassword, currentEmail, signIn } from '../auth'
import { Button, Card } from '../components/ui'

export function LoginPage({ onSignedIn }: { onSignedIn: (email: string) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pendingUser, setPendingUser] = useState<CognitoUser | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function finish() {
    onSignedIn((await currentEmail()) ?? email)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (pendingUser) {
        await completeNewPassword(pendingUser, newPassword)
        await finish()
      } else {
        const result = await signIn(email.trim(), password)
        if ('newPasswordRequired' in result) setPendingUser(result.user)
        else await finish()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  const input =
    'mt-1 block w-full rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600 outline-none'

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-slate-50 px-4">
      <Card className="w-full max-w-sm p-8">
        <div className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <ScanSearch className="h-4 w-4" />
          </span>
          TenderLens
        </div>
        <p className="mt-2 text-sm text-slate-500">RFP response and compliance agents. Sign in with the account you were given.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          {pendingUser ? (
            <label className="block text-sm font-medium text-slate-700">
              Choose a new password
              <input type="password" required minLength={8} value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)} className={input} autoFocus />
            </label>
          ) : (
            <>
              <label className="block text-sm font-medium text-slate-700">
                Email
                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} autoFocus />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Password
                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
              </label>
            </>
          )}
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <Button type="submit" loading={busy} className="w-full">
            {pendingUser ? 'Set password and sign in' : 'Sign in'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
