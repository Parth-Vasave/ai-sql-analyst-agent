import { useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'

function storedPreference(): ThemePreference {
  try {
    const value = localStorage.getItem('theme')
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

function systemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Light, dark, or follow the OS; remembered per browser only. */
export function useTheme(): { preference: ThemePreference; setPreference: (preference: ThemePreference) => void } {
  const [preference, setPreference] = useState<ThemePreference>(storedPreference)

  useEffect(() => {
    const apply = () => {
      document.documentElement.dataset.theme = preference === 'system' ? systemTheme() : preference
    }
    apply()
    try {
      if (preference === 'system') localStorage.removeItem('theme')
      else localStorage.setItem('theme', preference)
    } catch {
      // private browsing or blocked storage: the choice still applies for this load
    }
    if (preference !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [preference])

  return { preference, setPreference }
}
