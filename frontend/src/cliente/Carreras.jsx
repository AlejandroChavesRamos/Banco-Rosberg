// Pagina "Trabaja con nosotros" (publica, no pide iniciar sesion).
// Banco Rosberg es un proyecto academico: aqui no se prometen vacantes reales
// ni se muestran cifras inventadas. Las cifras son datos reales del proyecto.
import IntroLogo from '../componentes/IntroLogo'
import Aparecer from '../componentes/Aparecer'
import { Logo, Volver } from '../componentes/ui'
import foto1 from '../imagenes/carreras-1.jpg'
import foto2 from '../imagenes/carreras-2.jpg'
import foto3 from '../imagenes/carreras-3.jpg'
import foto4 from '../imagenes/carreras-4.jpg'
import foto5 from '../imagenes/carreras-5.jpg'
import { BarraPublica } from './MarcoPublico'
import { FormularioCorreo } from './SeccionesInicio'

const CIFRAS = [
  ['2', 'bases de datos trabajando juntas: MySQL y Neo4j'],
  ['9', 'reglas antifraude que revisan cada operación'],
  ['4', 'roles: cliente, cajero, analista y administrador'],
]

const FOTOS = [
  [foto2, 'Tres personas riendo frente a un computador portátil'],
  [foto3, 'Estudiantes trabajando juntos en una biblioteca'],
  [foto4, 'Dos personas revisando algo en un portátil'],
  [foto5, 'Equipo reunido alrededor de un portátil'],
]

const botonOro = 'boton-vivo inline-block rounded-full bg-oro px-7 py-3.5 text-base font-semibold text-marca-900 hover:bg-oro-claro'

export default function Carreras() {
  return (
    <div className="min-h-screen bg-white">
      <IntroLogo />
      <BarraPublica />

      <main>
        {/* Portada */}
        <section className="bg-marca-700 text-white">
          <div className="mx-auto max-w-6xl px-6 pb-24 pt-16 md:pt-20">
            <Volver a="/app/login" claro className="mb-8">Volver al inicio</Volver>
            <p className="font-semibold">Carreras</p>
            <h1 className="mt-10 font-titulo text-6xl font-bold tracking-tight md:text-7xl">Trabaja en Rosberg</h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/85">
              Se trata de aprender construyendo: levantar, pieza por pieza, un banco simulado que detecta el fraude
              como lo haría uno de verdad. Porque aquí, un proyecto de clase se toma en serio.
            </p>
            <a href="#unete" className={`${botonOro} mt-9`}>Únete a nuestro equipo</a>
          </div>
        </section>

        {/* Haz que lo extraordinario suceda */}
        <section className="mx-auto max-w-6xl px-6 py-24">
          <div className="grid items-center gap-14 lg:grid-cols-2">
            <Aparecer>
              <h2 className="font-titulo text-5xl font-bold leading-[1.05] tracking-tight text-marca-700 md:text-6xl">
                Haz que lo extraordinario suceda
              </h2>
              <p className="mt-6 max-w-md text-lg leading-relaxed text-marca-600">
                Se trata de cuidar cada detalle: que ningún saldo se descuadre, que cada movimiento quede en la
                auditoría y que una operación sospechosa no pase de largo. Así se construye un banco en el que se
                puede confiar, aunque sea de práctica.
              </p>
            </Aparecer>
            <Aparecer retraso={150}>
              <img src={foto1} alt="Grupo de estudiantes colaborando alrededor de un computador"
                   className="aspect-[4/3] w-full rounded-[2rem] object-cover" />
            </Aparecer>
          </div>

          <ul className="mt-20 grid gap-10 border-t border-marca-100 pt-12 sm:grid-cols-3">
            {CIFRAS.map(([numero, texto], i) => (
              <li key={texto}>
                <Aparecer retraso={i * 120}>
                  <div className="cifras font-titulo text-7xl font-bold leading-none text-marca-500">{numero}</div>
                  <p className="mt-3 max-w-[15rem] text-marca-700">{texto}</p>
                </Aparecer>
              </li>
            ))}
          </ul>

          <Aparecer className="mt-24 text-center">
            <p className="font-titulo text-6xl font-bold tracking-tight text-marca-700 md:text-8xl">El futuro es verde</p>
            <a href="#unete" className={`${botonOro} mt-10`}>Únete a nuestro equipo</a>
          </Aparecer>
        </section>

        {/* Letras e imagenes que cruzan la pantalla */}
        <section className="space-y-6 overflow-hidden bg-marca-50 py-16" aria-label="La vida en Rosberg">
          <Cinta texto="El futuro es verde" clase="text-marca-700" />
          <CintaFotos />
          <Cinta texto="La vida en Rosberg" clase="text-marca-500" alReves />
          <Cinta texto="Únete a nosotros" clase="text-oro-oscuro" />
        </section>

        {/* Cierre con el formulario */}
        <section id="unete" className="bg-marca-700 text-white">
          <div className="mx-auto grid max-w-6xl gap-12 px-6 py-24 lg:grid-cols-[1fr_26rem]">
            <Aparecer>
              <h2 className="font-titulo text-4xl font-bold leading-tight tracking-tight md:text-5xl">
                Haz que lo extraordinario suceda. Únete a nuestro equipo.
              </h2>
              <p className="mt-6 max-w-md text-white/80">
                Banco Rosberg es un proyecto académico y no tiene vacantes reales. Si dejas tu correo, queda
                guardado como una solicitud de demostración.
              </p>
            </Aparecer>
            <Aparecer retraso={150} className="rounded-3xl bg-white/10 p-7">
              <FormularioCorreo
                tipo="empleo"
                textoBoton="Quiero unirme"
                conMensaje
                etiquetaMensaje="Cuéntanos qué te gustaría hacer"
                oscuro
                confirmacion={(c) => <>Recibimos tu solicitud. Si hay novedades, te escribiremos a <strong>{c}</strong>.</>}
              />
            </Aparecer>
          </div>
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-4 border-t border-white/15 px-6 py-8">
            <Logo claro />
            <p className="text-xs text-white/60">
              © 2026 Banco Rosberg. Proyecto académico: no es una entidad financiera real ni maneja dinero real.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}

// Una fila de texto que se desliza sin fin. El contenido va dos veces seguidas:
// cuando la primera copia sale de la pantalla, la segunda ocupa su lugar.
function Cinta({ texto, clase, alReves = false }) {
  const copia = (oculta) => (
    <div className="flex shrink-0 items-center" aria-hidden={oculta}>
      {Array.from({ length: 6 }, (_, i) => (
        <span key={i} className="flex items-center whitespace-nowrap px-8 font-titulo text-6xl font-bold tracking-tight md:text-7xl">
          {texto}
          <span className="ml-16 inline-block h-4 w-4 rounded-full bg-oro" />
        </span>
      ))}
    </div>
  )
  return (
    <div className={`cinta flex w-max ${alReves ? 'cinta-reves' : ''} ${clase}`}>
      {copia(false)}
      {copia(true)}
    </div>
  )
}

function CintaFotos() {
  const copia = (oculta) => (
    <div className="flex shrink-0 gap-6 pr-6" aria-hidden={oculta}>
      {[...FOTOS, ...FOTOS].map(([src, alt], i) => (
        <img key={i} src={src} alt={oculta ? '' : alt} loading="lazy"
             className="h-56 w-80 shrink-0 rounded-3xl object-cover md:h-64 md:w-96" />
      ))}
    </div>
  )
  return (
    <div className="cinta cinta-reves cinta-lenta flex w-max">
      {copia(false)}
      {copia(true)}
    </div>
  )
}
