import type { AppProps } from 'next/app'
import { ThemeProvider } from '@/providers/theme'
import ErrorBoundary from '@/components/ErrorBoundary'
import '@/styles/globals.css'

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="file-manager-theme">
      <ErrorBoundary>
        <Component {...pageProps} />
      </ErrorBoundary>
    </ThemeProvider>
  )
}