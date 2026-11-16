// Seguridad de la cuenta del cliente: verificacion en dos pasos y contrasena
import { Link } from 'react-router-dom'
import { ConfigurarDosPasos } from '../componentes/DosPasos'
import { Tarjeta } from '../componentes/ui'

export default function Seguridad() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Seguridad</h1>
        <p className="text-sm text-slate-500">Protege tu cuenta con una capa extra.</p>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
        <ConfigurarDosPasos />
        <Tarjeta className="space-y-3 text-sm">
          <h2 className="font-semibold">Consejos</h2>
          <p className="text-slate-500">Banco Rosberg nunca te pedirá tu contraseña ni tus códigos por teléfono, correo o chat.</p>
          <p className="text-slate-500">Si ves un aviso de inicio de sesión que no reconoces, pulsa “No fui yo”: cerramos todas las sesiones al instante.</p>
          <Link to="/app/cambiar-clave" className="inline-block font-semibold text-marca-600">Cambiar mi contraseña →</Link>
        </Tarjeta>
      </div>
    </div>
  )
}
