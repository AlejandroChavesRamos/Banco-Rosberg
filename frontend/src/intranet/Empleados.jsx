// Administracion de empleados: listar, crear y activar/desactivar
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Aviso, Boton, Campo, Insignia, Selector, Tarjeta } from '../componentes/ui'
import { fechaHora } from '../formato'

const ROLES = [
  { valor: 'cajero', texto: 'Cajero' },
  { valor: 'analista', texto: 'Analista de fraude' },
  { valor: 'admin', texto: 'Administrador' },
]

export default function Empleados() {
  const [lista, setLista] = useState([])
  const [datos, setDatos] = useState({ nombre: '', email: '', rol: 'cajero' })
  const [creado, setCreado] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    cargar()
  }, [])

  function cargar() {
    api.get('/admin/empleados').then(setLista).catch((e) => setError(e.message))
  }

  async function crear(evento) {
    evento.preventDefault()
    setError('')
    setCargando(true)
    try {
      setCreado(await api.post('/admin/empleados', datos))
      setDatos({ nombre: '', email: '', rol: 'cajero' })
      cargar()
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  // Para el empleado que olvido su contrasena: se le da una temporal nueva
  async function restablecer(empleado) {
    if (!confirm(`¿Dar una contraseña temporal nueva a ${empleado.nombre}? Se cerrarán sus sesiones.`)) return
    setError('')
    try {
      setCreado(await api.post(`/admin/empleados/${empleado.id}/restablecer`))
    } catch (e) {
      setError(e.message)
    }
  }

  async function cambiarActivo(empleado) {
    const accion = empleado.activo ? 'desactivar' : 'activar'
    if (!confirm(`¿Seguro que quieres ${accion} a ${empleado.nombre}?`)) return
    try {
      await api.patch(`/admin/empleados/${empleado.id}`, { activo: !empleado.activo })
      cargar()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-marca-700">Empleados</h1>
      <Aviso>{error}</Aviso>

      {creado && (
        <div className="confirmado max-w-xl rounded-3xl bg-marca-700 p-6 text-center text-white" role="status">
          <div className="text-sm text-white/80">Contraseña temporal de {creado.email}</div>
          <div className="cifras mt-2 select-all font-titulo text-3xl font-bold tracking-wider text-oro">{creado.password_temporal}</div>
          <div className="mt-2 text-xs text-white/70">No se volverá a mostrar. Entrégasela al empleado: deberá cambiarla al entrar.</div>
        </div>
      )}

      <Tarjeta className="sin-barras overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-100 text-left text-xs text-slate-500">
            <tr><th className="px-5 py-3">Nombre</th><th>Correo</th><th>Rol</th><th>Desde</th><th>Estado</th><th></th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {lista.map((e) => (
              <tr key={e.id}>
                <td className="px-5 py-3 font-medium">{e.nombre}</td>
                <td className="text-slate-500">{e.email}</td>
                <td>{ROLES.find((r) => r.valor === e.rol)?.texto}</td>
                <td className="text-slate-500">{fechaHora(e.creado_en)}</td>
                <td>
                  <Insignia color={e.activo ? 'bg-marca-50 text-marca-700' : 'bg-slate-100 text-slate-500'}>
                    {e.activo ? 'Activo' : 'Inactivo'}
                  </Insignia>
                </td>
                <td className="whitespace-nowrap pr-5 text-right">
                  <button onClick={() => restablecer(e)} className="mr-4 text-xs font-medium text-marca-700 hover:underline">
                    Restablecer contraseña
                  </button>
                  <button onClick={() => cambiarActivo(e)} className="text-xs font-medium text-slate-500 hover:text-red-600">
                    {e.activo ? 'Desactivar' : 'Activar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Tarjeta>

      <Tarjeta className="max-w-xl">
        <h2 className="mb-4 text-lg font-semibold text-marca-700">Nuevo empleado</h2>
        <form onSubmit={crear} className="space-y-4">
          <Campo etiqueta="Nombre completo" required value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} />
          <Campo etiqueta="Correo corporativo" type="email" required value={datos.email} onChange={(e) => setDatos({ ...datos, email: e.target.value })} />
          <Selector etiqueta="Rol" value={datos.rol} onChange={(e) => setDatos({ ...datos, rol: e.target.value })} opciones={ROLES} />
          <Boton type="submit" cargando={cargando}>Crear empleado</Boton>
        </form>
      </Tarjeta>
    </div>
  )
}
