// Bandeja de solicitudes: los correos que dejan los visitantes en la pagina
// publica (pedir tarjeta, contacto, trabaja con nosotros). El empleado las
// revisa, responde por correo y las marca como atendidas.
import { useEffect, useState } from 'react'
import { api } from '../api'
import Icono from '../componentes/Icono'
import { Aviso, Boton, Cargando, Encabezado, EstadoVacio, Insignia, Tarjeta } from '../componentes/ui'
import { fechaHora } from '../formato'

const TIPOS = {
  tarjeta: { texto: 'Tarjeta física', icono: 'ventanilla', color: 'bg-oro-claro/60 text-marca-900' },
  contacto: { texto: 'Contacto', icono: 'arroba', color: 'bg-marca-100 text-marca-700' },
  empleo: { texto: 'Trabaja con nosotros', icono: 'empleados', color: 'bg-slate-100 text-slate-700' },
}

export default function Solicitudes() {
  const [verAtendidas, setVerAtendidas] = useState(false)
  const [lista, setLista] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    cargar()
  }, [verAtendidas])

  function cargar() {
    setLista(null)
    api.get(`/publico/solicitudes?atendidas=${verAtendidas}`).then(setLista).catch((e) => setError(e.message))
  }

  async function marcar(solicitud, atendida) {
    setError('')
    try {
      await api.patch(`/publico/solicitudes/${solicitud.id}`, { atendida })
      // Sale de la lista actual sin volver a pedir todo
      setLista((actual) => actual.filter((s) => s.id !== solicitud.id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <Encabezado
        titulo="Solicitudes"
        acciones={
          <div className="flex rounded-full bg-white p-1 ring-1 ring-marca-200" role="tablist">
            {[[false, 'Pendientes'], [true, 'Atendidas']].map(([valor, texto]) => (
              <button
                key={texto}
                role="tab"
                aria-selected={verAtendidas === valor}
                onClick={() => setVerAtendidas(valor)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  verAtendidas === valor ? 'bg-marca-700 text-white' : 'text-marca-700 hover:bg-marca-50'
                }`}
              >
                {texto}
              </button>
            ))}
          </div>
        }
      >
        Correos que dejaron los visitantes en la página del banco. Respóndeles y márcalas como atendidas.
      </Encabezado>
      <Aviso>{error}</Aviso>

      <Tarjeta className="p-0">
        {!lista ? (
          !error && <Cargando texto="Cargando solicitudes" />
        ) : lista.length === 0 ? (
          <EstadoVacio icono="buzon" titulo={verAtendidas ? 'Aún no hay solicitudes atendidas' : 'No hay solicitudes pendientes'}>
            {verAtendidas
              ? 'Las que marques como atendidas quedarán guardadas aquí.'
              : 'Cuando alguien pida la tarjeta, escriba por contacto o quiera unirse al equipo, aparecerá aquí.'}
          </EstadoVacio>
        ) : (
          <ul className="divide-y divide-marca-100">
            {lista.map((s) => {
              const tipo = TIPOS[s.tipo]
              return (
                <li key={s.id} className="flex flex-wrap items-start gap-4 px-6 py-5">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-marca-50 text-marca-600">
                    <Icono nombre={tipo.icono} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <a href={`mailto:${s.email}`} className="enlace-vivo font-semibold text-marca-800">{s.email}</a>
                      <Insignia color={tipo.color}>{tipo.texto}</Insignia>
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">{fechaHora(s.creada_en)}</div>
                    {s.mensaje && <p className="mt-2 max-w-2xl whitespace-pre-line text-sm text-marca-900">{s.mensaje}</p>}
                  </div>
                  {verAtendidas ? (
                    <Boton variante="secundario" onClick={() => marcar(s, false)}>Volver a pendientes</Boton>
                  ) : (
                    <Boton onClick={() => marcar(s, true)}>
                      <Icono nombre="check" className="h-4 w-4" />
                      Marcar atendida
                    </Boton>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Tarjeta>
    </div>
  )
}
