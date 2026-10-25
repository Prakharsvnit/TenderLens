import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { cx } from './ui'

type Kind = 'success' | 'error' | 'info'
interface Toast {
  id: number
  kind: Kind
  text: string
}

const ToastContext = createContext<(kind: Kind, text: string) => void>(() => undefined)

const ICON = {
  success: <CheckCircle2 className="h-4 w-4 text-emerald-600" />,
  error: <XCircle className="h-4 w-4 text-rose-600" />,
  info: <Info className="h-4 w-4 text-brand-600" />,
}

/** Short confirmations and errors in the corner, gone after a few seconds. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const dismiss = (id: number) => setToasts((all) => all.filter((t) => t.id !== id))
  const push = useCallback((kind: Kind, text: string) => {
    const id = Date.now() + Math.random()
    setToasts((all) => [...all.slice(-3), { id, kind, text }])
    setTimeout(() => dismiss(id), kind === 'error' ? 7000 : 4000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:left-auto">
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.kind === 'error' ? 'alert' : 'status'}
            className={cx(
              'pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-lg border bg-white p-3 text-sm shadow-lg',
              t.kind === 'error' ? 'border-rose-200' : 'border-slate-200',
            )}
          >
            <span className="mt-0.5">{ICON[t.kind]}</span>
            <span className="flex-1 text-slate-700">{t.text}</span>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-slate-400 hover:text-slate-700">
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
