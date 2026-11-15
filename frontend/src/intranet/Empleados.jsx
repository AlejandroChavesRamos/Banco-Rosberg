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
      <h1 className="text-2xl font-bold tracking-tight">Empleados</h1>
      <Aviso>{error}</Aviso>

      <Tarjeta className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-100 text-left text-xs text-slate-500 dark:border-slate-800">
            <tr><th className="px-5 py-3">Nombre</th><th>Correo</th><th>Rol</th><th>Desde</th><th>Estado</th><th></th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {lista.map((e) => (
              <tr key={e.id}>
                <td className="px-5 py-3 font-medium">{e.nombre}</td>
                <td className="text-slate-500">{e.email}</td>
                <td>{ROLES.find((r) => r.valor === e.rol)?.texto}</td>
                <td className="text-slate-500">{fechaHora(e.creado_en)}</td>
                <td>
                  <Insignia color={e.activo ? 'bg-marca-50 text-marca-700 dark:bg-marca-950 dark:text-marca-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-800'}>
                    {e.activo ? 'Activo' : 'Inactivo'}
                  </Insignia>
                </td>
                <td className="pr-5 text-right">
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
        <h2 className="mb-4 font-semibold">Nuevo empleado</h2>
        {creado && (
          <div className="mb-4 rounded-xl bg-slate-50 p-4 text-center dark:bg-slate-800">
            <div className="text-xs text-slate-500">Contraseña temporal de {creado.email}</div>
            <div className="cifras mt-1 text-2xl font-bold tracking-wider">{creado.password_temporal}</div>
            <div className="mt-1 text-xs text-slate-500">No se volverá a mostrar. Deberá cambiarla al entrar.</div>
          </div>
        )}
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
