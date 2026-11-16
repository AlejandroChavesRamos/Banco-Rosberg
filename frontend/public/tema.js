// Aplica el tema guardado ANTES de dibujar la pagina, para que no "parpadee".
// Esta en un archivo aparte (y no dentro de index.html) porque la politica de
// seguridad de contenido (CSP) de produccion prohibe scripts escritos en linea.
try {
  var tema = localStorage.getItem('rosberg-tema')
  var oscuro = tema ? tema === 'oscuro' : window.matchMedia('(prefers-color-scheme: dark)').matches
  if (oscuro) document.documentElement.classList.add('dark')
} catch (e) {}
