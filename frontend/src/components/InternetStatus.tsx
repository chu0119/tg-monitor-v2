import { useEffect, useRef } from 'react'

export default function InternetStatus() {
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true

    const check = async () => {
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 8000)
        const res = await fetch('/api/v1/diagnostics/internet-status', { signal: controller.signal })
        clearTimeout(timer)
        const data = await res.json()
        if (!mounted.current) return
        const online = data.online === true
        updateUI(online)
      } catch {
        if (!mounted.current) return
        updateUI(false)
      }
    }

    const updateUI = (online: boolean) => {
      const dotColor = online ? 'bg-green-500' : 'bg-red-500'
      const textColor = online ? 'text-green-400' : 'text-red-400'
      const text = online ? 'TG 在线' : 'TG 离线'

      const dot = document.getElementById('internet-dot')
      const dotMobile = document.getElementById('internet-dot-mobile')
      const textEl = document.getElementById('internet-text')

      ;[dot, dotMobile].forEach(el => {
        if (el) el.className = `w-2 h-2 rounded-full ${dotColor}`
      })
      if (textEl) {
        textEl.className = `text-sm ${textColor}`
        textEl.textContent = text
      }
    }

    check()
    const interval = setInterval(check, 30000)
    return () => { mounted.current = false; clearInterval(interval) }
  }, [])

  return null
}
