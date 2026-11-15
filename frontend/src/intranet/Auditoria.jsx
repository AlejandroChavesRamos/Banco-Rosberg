// Auditoria: ultimos registros y verificacion de la cadena de hashes
import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { Aviso, Boton, Tarjeta } from '../componentes/ui'
import { fechaHora } from '../formato'

export default function Auditoria() {
  const [registros, setRegistros] = useState([])
  const [verificacion, setVerificacion] = useState(null)
  const [verificando, setVerificando] = useState(false)
  const [abierto, setAbierto] = useState(null)

  useEffect(() => {
    api.get('/admin/auditoria?limite=150').then(setRegistros)
  }, [])

  async function verificar() {
    setVerificando(true)
    try {
      setVerificacion(await api.get('/admin/auditoria/verificar'))
    } finally {
      setVerificando(false)
    }
  }

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Auditoría</h1>
          <p className="text-sm text-slate-500">
            Cada registro guarda el hash del anterior: si alguien modifica uno, la cadena se rompe.
          </p>
        </div>
        <Boton onClick={verificar} cargando={verificando}>⛓ Verificar integridad</Boton>
      </div>

      {verificacion && (
        verificacion.integra ? (
          <Aviso tipo="exito">
            Cadena íntegra: se verificaron {verificacion.registros_verificados.toLocaleString('es-CO')} registros y ninguno fue alterado.
          </Aviso>
        ) : (
          <Aviso>⚠ {verificacion.mensaje}. Primer registro alterado: #{verificacion.primer_registro_alterado}</Aviso>
        )
      )}

      <Tarjeta className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-100 text-left text-xs text-slate-500 dark:border-slate-800">
            <tr><th className="px-5 py-3">#</th><th>Fecha</th><th>Acción</th><th>Entidad</th><th>Usuario</th><th>IP</th><th>Hash</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {registros.map((r) => (
              <Fragment key={r.id}>
                <tr onClick={() => setAbierto(abierto === r.id ? null : r.id)} className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="cifras px-5 py-2 text-slate-500">{r.id}</td>
                  <td className="whitespace-nowrap text-slate-500">{fechaHora(r.fecha)}</td>
                  <td className="font-mono text-xs font-semibold">{r.accion}</td>
                  <td className="text-slate-500">{r.entidad}{r.entidad_id ? ` #${r.entidad_id}` : ''}</td>
                  <td className="text-slate-500">{r.usuario_id ?? '—'}</td>
                  <td className="text-slate-500">{r.ip ?? '—'}</td>
                  <td className="font-mono text-xs text-slate-400">{r.hash.slice(0, 12)}…</td>
                </tr>
                {abierto === r.id && r.detalle && (
                  <tr>
                    <td colSpan={7} className="bg-slate-50 px-5 py-3 dark:bg-slate-800/50">
                      <pre className="whitespace-pre-wrap text-xs text-slate-600 dark:text-slate-300">{JSON.stringify(r.detalle, null, 2)}</pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </Tarjeta>
    </div>
  )
}
