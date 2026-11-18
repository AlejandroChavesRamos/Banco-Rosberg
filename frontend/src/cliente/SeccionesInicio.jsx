// Secciones que aparecen al bajar en la pantalla de login:
// beneficios, tarjeta debito, preguntas frecuentes y contacto.
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api'
import Aparecer from '../componentes/Aparecer'
import { Aviso, Boton, Logo, Simbolo } from '../componentes/ui'
import fotoAyuda from '../imagenes/ayuda.jpg'

const CORREO_AYUDA = 'bancorosberg@gmail.com'

export default function SeccionesInicio() {
  // Si se llega con /app/login#tarjeta (por ejemplo desde otra pagina), baja hasta esa seccion
  const ubicacion = useLocation()
  useEffect(() => {
    if (ubicacion.hash) document.getElementById(ubicacion.hash.slice(1))?.scrollIntoView()
  }, [ubicacion])

  return (
    <>
      <Beneficios />
      <SeccionTarjeta />
      <SeccionPreguntas />
      <SeccionContacto />
    </>
  )
}

// ---------------------------------------------------------------------
// Beneficios
// ---------------------------------------------------------------------
const BENEFICIOS = [
  ['llave', 'Envía con llaves', 'Transfiere a un celular o a un correo, sin pedir números de cuenta.'],
  ['codigo', 'Retira con un código', 'Genera un código en la app y retira tu dinero en la oficina.'],
  ['escudo', 'Protección antifraude', 'Revisamos cada operación en tiempo real para cuidar tu dinero.'],
]

function Beneficios() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-16 pt-4">
      <ul className="grid gap-8 border-t border-marca-100 pt-10 md:grid-cols-3">
        {BENEFICIOS.map(([icono, titulo, texto], i) => (
          <li key={titulo}>
            <Aparecer retraso={i * 120} className="flex gap-4">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-marca-100 text-marca-700">
                <Icono nombre={icono} />
              </span>
              <div>
                <h3 className="font-titulo text-lg font-semibold text-marca-700">{titulo}</h3>
                <p className="mt-1 text-sm leading-relaxed text-marca-600">{texto}</p>
              </div>
            </Aparecer>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Icono({ nombre }) {
  const trazos = {
    llave: <><circle cx="8" cy="15" r="4" /><path d="M11 12l8-8M16 7l3 3M14 9l2 2" /></>,
    codigo: <><rect x="4" y="5" width="16" height="14" rx="3" /><path d="M8 10v4M12 10v4M16 10v4" /></>,
    escudo: <><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" /><path d="M9 12l2.2 2.2L15.5 10" /></>,
  }
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {trazos[nombre]}
    </svg>
  )
}

// ---------------------------------------------------------------------
// Formulario de un solo correo (lo usan "pedir tarjeta", "contacto" y "trabaja con nosotros").
// La solicitud queda guardada en la base de datos del banco.
// ---------------------------------------------------------------------
export function FormularioCorreo({ tipo, textoBoton, conMensaje = false, etiquetaMensaje = '¿En qué te ayudamos?', oscuro = false, confirmacion }) {
  const [email, setEmail] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [enviadoA, setEnviadoA] = useState('')

  async function enviar(evento) {
    evento.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await api.post('/publico/solicitudes', { email, tipo, mensaje: mensaje.trim() || null }, { sinRenovar: true })
      setEnviadoA(email)
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  if (enviadoA) {
    return (
      <div className={`confirmado flex items-start gap-3 rounded-2xl p-4 ${oscuro ? 'bg-white/10 text-white' : 'bg-marca-100 text-marca-800'}`} role="status">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-oro font-bold text-marca-900">✓</span>
        <p className="text-sm leading-relaxed">{confirmacion(enviadoA)}</p>
      </div>
    )
  }

  const campo = `w-full rounded-xl border-0 px-4 py-3 text-sm text-marca-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${
    oscuro ? 'bg-white focus:ring-oro' : 'bg-white ring-1 ring-marca-200 focus:ring-marca-500'
  }`
  return (
    <form onSubmit={enviar} className="space-y-3">
      <label className="block">
        <span className={`mb-1 block text-sm font-medium ${oscuro ? 'text-white' : 'text-marca-800'}`}>Tu correo</span>
        <input type="email" required maxLength={254} autoComplete="email" placeholder="nombre@correo.com"
               className={campo} value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      {conMensaje && (
        <label className="block">
          <span className={`mb-1 block text-sm font-medium ${oscuro ? 'text-white' : 'text-marca-800'}`}>
            {etiquetaMensaje} <span className="font-normal opacity-70">(opcional)</span>
          </span>
          <textarea rows={3} maxLength={500} className={`${campo} resize-none`}
                    value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
        </label>
      )}
      <Aviso>{error}</Aviso>
      <Boton type="submit" variante={oscuro ? 'acento' : 'principal'} cargando={enviando} className="w-full py-3">
        {textoBoton}
      </Boton>
    </form>
  )
}

// ---------------------------------------------------------------------
// Tarjeta debito
// ---------------------------------------------------------------------
function SeccionTarjeta() {
  const [abierto, setAbierto] = useState(false)
  return (
    <section id="tarjeta" className="bg-marca-100">
      <div className="mx-auto grid max-w-6xl items-start gap-12 px-6 py-20 lg:grid-cols-[1fr_26rem]">
        <Aparecer className="lg:pt-24">
          <h2 className="font-titulo text-4xl font-bold leading-tight tracking-tight text-marca-700 md:text-5xl">
            Conoce la Tarjeta Débito Rosberg
          </h2>
          <p className="mt-5 max-w-md text-lg text-marca-600">
            Una sola tarjeta, conectada a tu cuenta de ahorros y sin cuota de manejo.
          </p>
        </Aparecer>

        <Aparecer retraso={150} className="overflow-hidden rounded-3xl bg-white shadow-xl shadow-marca-700/10">
          <div className="escena-tarjeta grid place-items-center bg-marca-50 py-12">
            <TarjetaDebito />
          </div>
          <div className="p-7">
            <h3 className="font-titulo text-2xl font-semibold text-marca-700">Tarjeta Débito Rosberg</h3>
            <p className="mt-2 text-sm leading-relaxed text-marca-600">
              Paga con el saldo de tu cuenta. Cada compra pasa por la misma revisión antifraude que tus transferencias.
            </p>
            <Boton variante="acento" className="mt-6 rounded-full px-6 py-3" aria-expanded={abierto} onClick={() => setAbierto(!abierto)}>
              Pedir tarjeta física
            </Boton>

            {/* Se despliega con una transicion de altura (grid 0fr -> 1fr) */}
            <div className={`grid transition-[grid-template-rows] duration-500 ease-out ${abierto ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
              <div className="overflow-hidden">
                <div className="px-0.5 pb-1 pt-6">
                  <p className="mb-4 text-sm text-marca-600">
                    Escribe tu correo. Por ese correo seguiremos contigo el proceso de entrega de la tarjeta.
                  </p>
                  {abierto && (
                    <FormularioCorreo
                      tipo="tarjeta"
                      textoBoton="Pedir mi tarjeta"
                      confirmacion={(c) => <>Recibimos tu solicitud. El proceso de entrega sigue en <strong>{c}</strong>.</>}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </Aparecer>
      </div>
    </section>
  )
}

function TarjetaDebito() {
  return (
    <div className="tarjeta-3d relative h-72 w-48" aria-label="Tarjeta Débito Rosberg girando" role="img">
      {/* Frente */}
      <div className="tarjeta-cara absolute inset-0 overflow-hidden rounded-[1.4rem] bg-gradient-to-br from-marca-600 to-marca-800 p-5 text-white shadow-2xl shadow-marca-900/40">
        <div className="tarjeta-brillo absolute inset-0" />
        <div className="relative flex h-full flex-col">
          <div className="flex items-start justify-between">
            <Simbolo claro className="h-8 w-auto" />
            <svg viewBox="0 0 28 36" className="h-11 w-9 text-marca-300" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <rect x="1" y="1" width="26" height="34" rx="6" />
              <path d="M1 12h8v12H1M27 12h-8v12h8M9 18h10M14 1v11M14 24v11" />
            </svg>
          </div>
          <div className="mt-auto">
            <div className="text-sm font-medium text-oro">débito</div>
            <div className="font-titulo text-3xl font-bold leading-none tracking-tight">Rosberg</div>
          </div>
        </div>
      </div>
      {/* Reverso */}
      <div className="tarjeta-cara tarjeta-reverso absolute inset-0 overflow-hidden rounded-[1.4rem] bg-marca-900 text-white shadow-2xl shadow-marca-900/40">
        <div className="mt-8 h-10 bg-marca-950" />
        <div className="mx-5 mt-5 h-8 rounded bg-white/90" />
        <p className="absolute inset-x-5 bottom-6 text-[11px] leading-snug text-white/60">
          Banco Rosberg. Tarjeta de demostración de un proyecto académico, sin valor comercial.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------
// Preguntas frecuentes
// ---------------------------------------------------------------------
const PREGUNTAS = [
  [
    '¿Cuál es el propósito de Banco Rosberg?',
    <>
      Banco Rosberg es un proyecto académico de la materia Bases de Datos. Simula el funcionamiento de un banco
      (cuentas, transferencias, retiros) y un detector de fraude que combina una base de datos relacional con una de
      grafos. No es una entidad financiera real y no capta ni mueve dinero de verdad.
    </>,
  ],
  [
    '¿Si necesito ayuda, qué hago?',
    <>
      Escribe a nuestra línea de atención, <a href={`mailto:${CORREO_AYUDA}`} className="font-semibold underline">{CORREO_AYUDA}</a>,
      o déjanos tu correo en la sección de contacto al final de esta página y te escribimos nosotros.
    </>,
  ],
  [
    '¿El dinero que veo en mi cuenta es real?',
    <>
      No. Todos los saldos y movimientos son simulados y solo existen dentro de este proyecto. No se pueden retirar,
      cobrar ni convertir en dinero real.
    </>,
  ],
  [
    '¿Qué puedo hacer en la banca en línea?',
    <>
      Consultar tu saldo y tus movimientos, transferir a otras cuentas, registrar llaves (tu celular o tu correo) para
      recibir dinero sin compartir el número de cuenta, y generar códigos para retirar en la oficina.
    </>,
  ],
  [
    '¿Cómo cuida el banco mis operaciones?',
    <>
      Un motor antifraude revisa cada operación en el momento en que se hace. Si algo se sale de lo normal, la
      operación queda retenida hasta que un analista del banco la revisa.
    </>,
  ],
]

function SeccionPreguntas() {
  const [abierta, setAbierta] = useState(0)
  return (
    <section id="preguntas" className="bg-marca-50">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-[1fr_1.25fr]">
        <Aparecer>
          <h2 className="font-titulo text-4xl font-bold tracking-tight text-marca-700 md:text-5xl">¿Tienes más preguntas?</h2>
          <img src={fotoAyuda} alt="Clienta revisando su celular en una sala"
               className="mt-10 hidden aspect-[4/5] w-72 rounded-[2rem] object-cover lg:block" loading="lazy" />
        </Aparecer>

        <ul className="space-y-3">
          {PREGUNTAS.map(([pregunta, respuesta], i) => {
            const activa = abierta === i
            return (
              <li key={pregunta}>
                <Aparecer retraso={i * 80} className="rounded-3xl bg-white">
                  <h3>
                    <button
                      className="no-crecer flex w-full items-center justify-between gap-6 rounded-3xl px-7 py-6 text-left text-lg font-medium text-marca-800 transition-colors hover:text-marca-500"
                      aria-expanded={activa}
                      onClick={() => setAbierta(activa ? -1 : i)}
                    >
                      {pregunta}
                      <span className={`shrink-0 text-2xl font-light leading-none transition-transform duration-300 ${activa ? 'rotate-45 text-oro-oscuro' : ''}`} aria-hidden="true">+</span>
                    </button>
                  </h3>
                  <div className={`grid transition-[grid-template-rows] duration-300 ease-out ${activa ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
                    <div className="overflow-hidden">
                      <p className="px-7 pb-6 leading-relaxed text-marca-600">{respuesta}</p>
                    </div>
                  </div>
                </Aparecer>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------
// Contacto y pie de pagina
// ---------------------------------------------------------------------
function SeccionContacto() {
  const enlace = 'enlace-vivo font-medium text-white'
  return (
    <footer id="contacto" className="bg-marca-700 text-white">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-[1fr_26rem]">
          <Aparecer>
            <h2 className="font-titulo text-4xl font-bold tracking-tight md:text-5xl">Contáctanos</h2>
            <p className="mt-5 max-w-md text-lg text-white/80">
              Déjanos tu correo y una persona del equipo te escribe para resolver tus dudas.
            </p>
            <p className="mt-8 text-sm text-marca-300">Dudas o preguntas</p>
            <a href={`mailto:${CORREO_AYUDA}`} className={`${enlace} text-lg`}>{CORREO_AYUDA}</a>
          </Aparecer>

          <Aparecer retraso={150} className="rounded-3xl bg-white/10 p-7">
            <FormularioCorreo
              tipo="contacto"
              textoBoton="Enviar"
              conMensaje
              oscuro
              confirmacion={(c) => <>Enviado. Te escribiremos a <strong>{c}</strong> para ayudarte con tus dudas.</>}
            />
          </Aparecer>
        </div>

        <div className="mt-16 grid gap-10 border-t border-white/15 pt-10 sm:grid-cols-3">
          <div>
            <h3 className="text-sm text-marca-300">Productos</h3>
            <ul className="mt-4 space-y-3">
              <li><Link to="/app/registro" className={enlace}>Cuenta de ahorros</Link></li>
              <li><a href="#tarjeta" className={enlace}>Tarjeta Débito Rosberg</a></li>
            </ul>
          </div>
          <div>
            <h3 className="text-sm text-marca-300">Ayuda</h3>
            <ul className="mt-4 space-y-3">
              <li><a href="#preguntas" className={enlace}>Preguntas frecuentes</a></li>
              <li><a href={`mailto:${CORREO_AYUDA}`} className={enlace}>{CORREO_AYUDA}</a></li>
            </ul>
          </div>
          <div>
            <h3 className="text-sm text-marca-300">Portales</h3>
            <ul className="mt-4 space-y-3">
              <li><a href="#top" className={enlace} onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>Banca en línea</a></li>
              <li><Link to="/intranet" className={enlace}>Intranet para empleados</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-14 flex flex-wrap items-center gap-x-8 gap-y-4 border-t border-white/15 pt-8">
          <a href="/app/login" aria-label="Banco Rosberg, inicio"
             onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>
            <Logo claro />
          </a>
          <p className="text-xs text-white/60">
            © 2026 Banco Rosberg. Proyecto académico: no es una entidad financiera real ni maneja dinero real.
          </p>
        </div>
      </div>
    </footer>
  )
}
