import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './styles.css'
import App from './App'
import MethodologyPage from './pages/MethodologyPage'

const isMethodology = window.location.pathname === '/methodology'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isMethodology ? <MethodologyPage /> : <App />}
  </StrictMode>,
)
