import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './api/api' // installs the shared 401 -> Login handler for every request
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
