// Punto de entrada: decide que portal mostrar segun la direccion (URL)
//   /app/...       -> App Rosberg (clientes)
//   /intranet/...  -> Intranet Rosberg (empleados)
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import { SesionProvider } from './sesion'
import AppCliente from './cliente/AppCliente'
import Intranet from './intranet/Intranet'

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Navigate to="/app" replace />} />
      <Route
        path="/app/*"
        element={
          <SesionProvider portal="app">
            <AppCliente />
          </SesionProvider>
        }
      />
      <Route
        path="/intranet/*"
        element={
          <SesionProvider portal="intranet">
            <Intranet />
          </SesionProvider>
        }
      />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  </BrowserRouter>,
)
