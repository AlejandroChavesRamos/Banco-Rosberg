// Aviso de inicio de sesion sospechoso: aparece arriba de cualquier pantalla
// de la App cuando alguien entro desde un dispositivo o IP nuevos.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Boton } from '../componentes/ui'
import { usePeriodico } from '../componentes/usePeriodico'
import { fechaHora } from '../formato'

export default function AvisosSeguridad() {
  const navegar = useNavigate()
  const [avisos, setAvisos] = useState([])
  const [ocupado, setOcupado] = useState(null)

  // Revisar cada 30 segundos
  usePeriodico(() => {
    api.get('/seguridad/avisos').then(setAvisos).catch(() => {})
  }, 30000)

  async function responder(aviso, fuiYo) {
    if (!fuiYo && !confirm('Cerraremos TODAS las sesiones de tu cuenta y deberás crear una contraseña nueva. ¿Continuar?')) return
    setOcupado(aviso.id)
    try {
      await api.post(`/seguridad/avisos/${aviso.id}/${fuiYo ? 'fui-yo' : 'no-fui-yo'}`)
      setAvisos((lista) => lista.filter((a) => a.id !== aviso.id))
      if (!fuiYo) navegar('/app/cambiar-clave')
    } catch (e) {
      alert(e.message)
    } finally {
      setOcupado(null)
    }
  }

  if (avisos.length === 0) return null
  return (
    <div className="mb-6 space-y-3">
      {avisos.map((a) => (
        <div key={a.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-amber-300 bg-amber-50 px-5 py-4">
          <span className="text-2xl">⚠</span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-amber-900">¿Fuiste tú? Nuevo inicio de sesión</div>
            <div className="text-sm text-amber-800">{a.motivo} · {fechaHora(a.creado_en)}</div>
          </div>
          <div className="flex gap-2">
            <Boton variante="secundario" cargando={ocupado === a.id} onClick={() => responder(a, true)}>Sí, fui yo</Boton>
            <Boton variante="peligro" cargando={ocupado === a.id} onClick={() => responder(a, false)}>No fui yo</Boton>
          </div>
        </div>
      ))}
    </div>
  )
}
