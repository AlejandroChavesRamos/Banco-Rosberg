// =====================================================================
// Metas de ahorro ("bolsillos"): el cliente aparta parte del saldo de una
// cuenta para algo con nombre (por ejemplo "Viaje") y ve cuanto le falta.
//
// El dinero NO sale de la cuenta: solo deja de estar disponible para enviar o
// retirar hasta que el cliente lo libere o elimine la meta.
// =====================================================================
import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAviso } from '../componentes/Avisos'
import Icono from '../componentes/Icono'
import { Dinero } from '../componentes/Saldo'
import { Aviso, Boton, Campo, Cargando, Dialogo, Encabezado, EstadoVacio, Selector, Tarjeta } from '../componentes/ui'
import { cop, enmascarar } from '../formato'

export default function Metas() {
  const avisar = useAviso()
  const [metas, setMetas] = useState(null)
  const [cuentas, setCuentas] = useState([])
  const [error, setError] = useState('')
  const [mover, setMover] = useState(null) // { meta, accion: 'apartar' | 'liberar' } abre el dialogo

  useEffect(() => {
    cargar()
  }, [])

  function cargar() {
    Promise.all([api.get('/metas'), api.get('/cuentas')])
      .then(([m, c]) => {
        setMetas(m)
        setCuentas(c.filter((x) => x.estado === 'activa'))
      })
      .catch((e) => setError(e.message))
  }

  async function eliminar(meta) {
    const texto = Number(meta.apartado) > 0
      ? `¿Eliminar la meta "${meta.nombre}"? Los ${cop(meta.apartado)} apartados vuelven a estar disponibles en tu cuenta.`
      : `¿Eliminar la meta "${meta.nombre}"?`
    if (!confirm(texto)) return
    try {
      await api.delete(`/metas/${meta.id}`)
      avisar(`Meta "${meta.nombre}" eliminada`)
      cargar()
    } catch (e) {
      setError(e.message)
    }
  }

  const totalApartado = (metas ?? []).reduce((s, m) => s + Number(m.apartado), 0)

  return (
    <div className="space-y-6">
      <Encabezado
        titulo="Metas de ahorro"
        acciones={
          metas?.length > 0 && (
            <div className="text-right">
              <div className="text-xs text-slate-500">Apartado en total</div>
              <div className="font-titulo text-2xl font-bold text-marca-800"><Dinero valor={totalApartado} /></div>
            </div>
          )
        }
      >
        Separa dinero para lo que quieres lograr. Sigue en tu cuenta, pero no se gasta por error.
      </Encabezado>
      <Aviso>{error}</Aviso>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
        <div>
          {!metas ? (
            <Tarjeta className="p-0"><Cargando texto="Cargando tus metas" filas={3} /></Tarjeta>
          ) : metas.length === 0 ? (
            <Tarjeta className="p-0">
              <EstadoVacio icono="meta" titulo="Aún no tienes metas">
                Crea tu primera meta con el formulario: dale un nombre, un valor y empieza a apartar.
              </EstadoVacio>
            </Tarjeta>
          ) : (
            <ul className="grid gap-5 md:grid-cols-2">
              {metas.map((m) => (
                <li key={m.id}>
                  <TarjetaMeta
                    meta={m}
                    onApartar={() => setMover({ meta: m, accion: 'apartar' })}
                    onLiberar={() => setMover({ meta: m, accion: 'liberar' })}
                    onEliminar={() => eliminar(m)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <NuevaMeta cuentas={cuentas} onCreada={(nombre) => { avisar(`Meta "${nombre}" creada`); cargar() }} />
      </div>

      {mover && (
        <DialogoMover
          {...mover}
          cuenta={cuentas.find((c) => c.numero === mover.meta.cuenta)}
          onCerrar={() => setMover(null)}
          onListo={(texto) => {
            setMover(null)
            avisar(texto)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function TarjetaMeta({ meta, onApartar, onLiberar, onEliminar }) {
  const apartado = Number(meta.apartado)
  const objetivo = Number(meta.objetivo)
  const avance = Math.min(100, (apartado / objetivo) * 100)
  const lograda = apartado >= objetivo
  return (
    <Tarjeta className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`grid h-11 w-11 place-items-center rounded-2xl ${lograda ? 'bg-oro text-marca-900' : 'bg-marca-100 text-marca-700'}`}>
            <Icono nombre={lograda ? 'check' : 'meta'} />
          </span>
          <div>
            <h3 className="font-titulo text-lg font-semibold text-marca-800">{meta.nombre}</h3>
            <p className="text-xs text-slate-500">De la cuenta {enmascarar(meta.cuenta)}</p>
          </div>
        </div>
        <button onClick={onEliminar} className="rounded-lg p-1.5 text-slate-400 hover:text-red-600" aria-label={`Eliminar la meta ${meta.nombre}`}>
          <Icono nombre="cerrar" className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-5 flex items-baseline justify-between gap-2">
        <span className="font-titulo text-2xl font-bold text-marca-800"><Dinero valor={apartado} /></span>
        <span className="text-sm text-slate-500">de <Dinero valor={objetivo} animado={false} /></span>
      </div>
      {/* Barra de progreso */}
      <div className="mt-2 h-3 overflow-hidden rounded-full bg-marca-100" role="progressbar" aria-valuenow={Math.round(avance)}
           aria-valuemin={0} aria-valuemax={100} aria-label={`Avance de ${meta.nombre}`}>
        <div className={`barra-llena h-full rounded-full ${lograda ? 'bg-oro' : 'bg-marca-500'}`} style={{ width: `${avance}%` }} />
      </div>
      <p className="mt-2 text-sm text-slate-500">
        {lograda ? '¡Lo lograste! Ya tienes todo lo que te propusiste.' : <>Vas en {Math.floor(avance)} %. Te faltan <Dinero valor={objetivo - apartado} animado={false} />.</>}
      </p>

      <div className="mt-auto flex gap-2 pt-5">
        <Boton className="flex-1" onClick={onApartar}>
          <Icono nombre="mas" className="h-4 w-4" />
          Apartar
        </Boton>
        <Boton variante="secundario" className="flex-1" onClick={onLiberar} disabled={apartado === 0}>Liberar</Boton>
      </div>
    </Tarjeta>
  )
}

function NuevaMeta({ cuentas, onCreada }) {
  const [datos, setDatos] = useState({ nombre: '', objetivo: '', cuenta: '' })
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const cuenta = datos.cuenta || cuentas[0]?.numero || ''

  async function crear(e) {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await api.post('/metas', { nombre: datos.nombre.trim(), objetivo: Number(datos.objetivo), cuenta })
      onCreada(datos.nombre.trim())
      setDatos({ nombre: '', objetivo: '', cuenta })
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Tarjeta>
      <h2 className="mb-4 text-lg font-semibold text-marca-700">Nueva meta</h2>
      <form onSubmit={crear} className="space-y-4">
        <Campo etiqueta="¿Para qué ahorras?" required minLength={2} maxLength={60} placeholder="Viaje, computador, emergencias…"
               value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} />
        <Campo etiqueta="¿Cuánto necesitas?" type="number" inputMode="numeric" min="1000" step="1" required placeholder="1000000"
               value={datos.objetivo} onChange={(e) => setDatos({ ...datos, objetivo: e.target.value })} />
        <Selector
          etiqueta="Cuenta de donde apartas"
          value={cuenta}
          onChange={(e) => setDatos({ ...datos, cuenta: e.target.value })}
          opciones={cuentas.map((c) => ({ valor: c.numero, texto: `Ahorros ${enmascarar(c.numero)}` }))}
        />
        <Aviso>{error}</Aviso>
        <Boton type="submit" cargando={enviando} disabled={!cuenta} className="w-full">Crear meta</Boton>
      </form>
    </Tarjeta>
  )
}

// Apartar dinero en la meta, o liberarlo de vuelta al disponible de la cuenta
function DialogoMover({ meta, accion, cuenta, onCerrar, onListo }) {
  const [monto, setMonto] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const apartar = accion === 'apartar'
  const disponible = cuenta ? Math.max(0, Number(cuenta.saldo) - Number(cuenta.apartado || 0)) : 0
  const tope = apartar ? disponible : Number(meta.apartado)

  async function enviar(e) {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await api.post(`/metas/${meta.id}/${accion}`, { monto: Number(monto) })
      onListo(apartar ? `Apartaste ${cop(monto)} en "${meta.nombre}"` : `Liberaste ${cop(monto)} de "${meta.nombre}"`)
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialogo titulo={apartar ? `Apartar en "${meta.nombre}"` : `Liberar de "${meta.nombre}"`} onCerrar={onCerrar}>
      <form onSubmit={enviar} className="space-y-4">
        <p className="text-sm text-slate-600">
          {apartar
            ? <>Tienes {cop(disponible)} disponibles en la cuenta {enmascarar(meta.cuenta)}.</>
            : <>Tienes {cop(meta.apartado)} apartados. Lo que liberes vuelve a estar disponible en tu cuenta.</>}
        </p>
        <Campo etiqueta="Monto" type="number" inputMode="numeric" min="1" max={tope || undefined} step="1" required autoFocus
               value={monto} onChange={(e) => setMonto(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          {[0.25, 0.5, 1].map((parte) => (
            <button type="button" key={parte} onClick={() => setMonto(String(Math.floor(tope * parte)))} disabled={!tope}
                    className="rounded-full px-3 py-1 text-xs font-medium text-marca-700 ring-1 ring-marca-200 hover:bg-marca-50 disabled:opacity-50">
              {parte === 1 ? 'Todo' : `${parte * 100} %`}
            </button>
          ))}
        </div>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-3 pt-1">
          <Boton type="button" variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={enviando}>{apartar ? 'Apartar' : 'Liberar'}</Boton>
        </div>
      </form>
    </Dialogo>
  )
}
