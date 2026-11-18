"""Conocimiento inicial del Asistente Rosberg.

El backend lo carga en MySQL al arrancar (asistente.sembrar_conocimiento):
  - Solo agrega las respuestas que falten (por su "clave").
  - En las que ya existen, solo completa lo que este vacio (pregunta, accion,
    temas relacionados): nunca pisa lo que el admin haya editado.
  - Se ejecuta una vez por VERSION (configuracion CONOCIMIENTO_VERSION): si el
    admin borra un sinonimo, no vuelve a aparecer en el siguiente arranque.

En "respuesta" se pueden usar claves de la tabla configuracion entre llaves:
{RETIRO_MAXIMO} se reemplaza por el valor actual ("$2.000.000"). Asi, si el
admin cambia un limite, el asistente lo dice bien sin editar el texto.

"accion" (opcional) hace que, ademas del texto, el asistente consulte los
DATOS del cliente (solo lectura): sus envios, cuentas, saldo, codigos de
retiro, llaves o estado de seguridad.

Prioridad: si coinciden varias respuestas, gana la mayor. Las de cortesia
(saludo, gracias, despedida) tienen 1 o 2: solo ganan si no hay nada mas.
"""

VERSION = 3

RESPUESTAS = [
    # ------------------------------------------------------------ envios
    {
        "clave": "envio_revision", "titulo": "Transferencia en revisión", "prioridad": 7, "accion": "envios",
        "pregunta": "¿Por qué mi envío está en revisión?",
        "respuesta": "Si un envío dice \"En revisión\", nuestro sistema de seguridad lo está verificando. "
                     "El dinero NO sale de tu cuenta hasta que un analista lo apruebe; normalmente toma menos de un día. "
                     "No necesitas hacer nada.",
        "palabras": ["en revision", "retenida", "retenido", "revisando", "verificando", "pendiente"],
        "relacionadas": ["envio_bloqueado", "no_llego", "tiempo_envio"],
    },
    {
        "clave": "envio_bloqueado", "titulo": "Transferencia bloqueada", "prioridad": 8, "accion": "envios",
        "pregunta": "¿Por qué bloquearon mi transferencia?",
        "respuesta": "Una transferencia queda \"Bloqueada\" cuando nuestro sistema antifraude detecta un riesgo alto "
                     "(por ejemplo, un monto muy distinto a lo habitual, un dispositivo nuevo o una cuenta destino sospechosa). "
                     "El dinero no sale de tu cuenta. Si fuiste tú, un asesor puede revisarlo contigo.",
        "palabras": ["bloquearon la transferencia", "transferencia bloqueada", "envio bloqueado", "bloquearon el envio",
                     "rechazada", "no me deja transferir", "no puedo transferir"],
        "relacionadas": ["envio_revision", "transferir"],
    },
    {
        "clave": "no_llego", "titulo": "No me llegó el dinero", "prioridad": 7, "accion": "envios",
        "pregunta": "No me llegó una transferencia",
        "respuesta": "Las transferencias entre cuentas Rosberg llegan al instante cuando quedan \"Exitosas\". "
                     "Si la persona que te envió ve su envío \"En revisión\", llegará cuando se apruebe. "
                     "Revisé tus movimientos:",
        "palabras": ["no me llego", "no ha llegado", "no me ha llegado", "no aparece", "no me consignaron",
                     "no me han consignado", "no recibi", "no veo el dinero", "donde esta mi dinero"],
        "relacionadas": ["envio_revision", "movimientos"],
    },
    {
        "clave": "transferir", "titulo": "Cómo transferir", "prioridad": 5,
        "pregunta": "¿Cómo envío dinero?",
        "respuesta": "En \"Enviar dinero\" escribe la llave del destinatario (su celular o correo) o su número de cuenta "
                     "de 12 dígitos, el monto y, si quieres, un mensaje. Antes de confirmar te mostramos parte del nombre "
                     "del titular: verifícalo. Si el envío es de {MONTO_2FA} o más, el banco puede pedirte el código "
                     "de tu app autenticadora.",
        "palabras": ["como transfiero", "como envio", "enviar dinero", "hacer una transferencia", "mandar dinero",
                     "transferir", "transferencia"],
        "relacionadas": ["llaves", "mensaje_envio", "comprobante"],
    },
    {
        "clave": "tiempo_envio", "titulo": "Cuánto tarda un envío", "prioridad": 6,
        "pregunta": "¿Cuánto tarda una transferencia?",
        "respuesta": "Si el envío queda \"Exitoso\", el dinero llega de inmediato a la otra cuenta Rosberg. "
                     "Si queda \"En revisión\", llega cuando un analista lo apruebe (normalmente menos de un día).",
        "palabras": ["cuanto tarda", "cuanto demora", "cuando llega", "demora", "se demora", "inmediata"],
        "relacionadas": ["envio_revision", "no_llego"],
    },
    {
        "clave": "mensaje_envio", "titulo": "Mensaje en un envío", "prioridad": 6,
        "pregunta": "¿Puedo dejar un mensaje al enviar dinero?",
        "respuesta": "Sí. En \"Enviar dinero\" hay un campo \"Mensaje (opcional)\" de hasta 140 caracteres, "
                     "como \"Para el almuerzo\". Lo ven tú y quien recibe en sus movimientos y en el comprobante. "
                     "Una vez enviado no se puede cambiar.",
        "palabras": ["mensaje", "nota", "dejar un mensaje", "descripcion del envio", "concepto"],
        "relacionadas": ["transferir"],
    },
    {
        "clave": "comprobante", "titulo": "Comprobante", "prioridad": 5,
        "pregunta": "¿Cómo descargo el comprobante?",
        "respuesta": "Al terminar un envío aparece el comprobante con el botón \"Imprimir o guardar PDF\". "
                     "Para varios movimientos, usa \"Descargar extracto\" en el Inicio.",
        "palabras": ["comprobante", "recibo", "soporte", "constancia", "pdf"],
        "relacionadas": ["extracto", "transferir"],
    },
    # ------------------------------------------------------------ llaves
    {
        "clave": "llaves", "titulo": "Registrar una llave", "prioridad": 6, "accion": "llaves",
        "pregunta": "¿Cómo registro una llave?",
        "respuesta": "Para registrar una llave entra a \"Mis llaves\" y elige tu celular o tu correo. Solo puedes usar "
                     "los mismos que diste al abrir tu cuenta: si cambiaste de número, actualízalo en una oficina.",
        "palabras": ["llave", "llaves", "registrar mi celular", "registrar mi correo", "mis llaves"],
        "relacionadas": ["transferir"],
    },
    # ----------------------------------------------------------- retiros
    {
        "clave": "retiro", "titulo": "Retiro sin tarjeta", "prioridad": 6, "accion": "codigos_retiro",
        "pregunta": "¿Cómo retiro sin tarjeta?",
        "respuesta": "En \"Retirar sin tarjeta\" genera un código de 6 dígitos (máximo {RETIRO_MAXIMO} por retiro). "
                     "Llévalo a la ventanilla con tu cédula física: el código vence en {VIGENCIA_CODIGO_RETIRO} minutos "
                     "y solo sirve una vez.",
        "palabras": ["retiro", "retirar", "sin tarjeta", "efectivo", "codigo de retiro", "sacar plata", "sacar dinero"],
        "relacionadas": ["codigo_vencido", "deposito"],
    },
    {
        "clave": "codigo_vencido", "titulo": "Código de retiro vencido o bloqueado", "prioridad": 7,
        "accion": "codigos_retiro",
        "pregunta": "Mi código de retiro no funciona",
        "respuesta": "Un código de retiro vence a los {VIGENCIA_CODIGO_RETIRO} minutos y se bloquea si se escribe mal "
                     "{INTENTOS_CODIGO_RETIRO} veces. En ambos casos el dinero sigue en tu cuenta: genera uno nuevo en "
                     "\"Retirar sin tarjeta\".",
        "palabras": ["codigo vencido", "codigo bloqueado", "no funciona el codigo", "codigo no sirve",
                     "se vencio", "vencio", "codigo invalido"],
        "relacionadas": ["retiro"],
    },
    {
        "clave": "deposito", "titulo": "Depositar dinero", "prioridad": 6,
        "pregunta": "¿Cómo deposito dinero?",
        "respuesta": "Los depósitos en efectivo se hacen en la ventanilla de una oficina: el cajero los abona a tu cuenta "
                     "al instante. También puedes recibir transferencias de otras cuentas Rosberg.",
        "palabras": ["depositar", "deposito", "consignar", "consignacion", "meter plata", "abonar", "cargar dinero"],
        "relacionadas": ["retiro", "saldo"],
    },
    # ------------------------------------------------------------ cuentas
    {
        "clave": "saldo", "titulo": "Saldo", "prioridad": 5, "accion": "saldo",
        "pregunta": "¿Cuánto dinero tengo?",
        "respuesta": "Tu saldo siempre aparece en el Inicio de la app. Te lo muestro aquí también:",
        "palabras": ["saldo", "cuanto tengo", "cuanta plata tengo", "cuanto dinero tengo", "disponible"],
        "relacionadas": ["movimientos", "extracto"],
    },
    {
        "clave": "movimientos", "titulo": "Movimientos", "prioridad": 5,
        "pregunta": "¿Dónde veo mis movimientos?",
        "respuesta": "En el Inicio, elige la cuenta y verás la tabla de movimientos. Con \"Desde\" y \"Hasta\" puedes "
                     "filtrar por fechas.",
        "palabras": ["movimientos", "historial", "transacciones", "ver mis movimientos", "ultimos movimientos"],
        "relacionadas": ["extracto", "saldo"],
    },
    {
        "clave": "extracto", "titulo": "Extracto", "prioridad": 5,
        "pregunta": "¿Cómo descargo un extracto?",
        "respuesta": "En el Inicio elige la cuenta, escoge las fechas con \"Desde\" y \"Hasta\" y pulsa "
                     "\"Descargar extracto\". Se descarga un archivo que abre en Excel.",
        "palabras": ["extracto", "excel", "descargar movimientos", "estado de cuenta", "reporte"],
        "relacionadas": ["movimientos", "comprobante"],
    },
    {
        "clave": "abrir_cuenta", "titulo": "Abrir otra cuenta", "prioridad": 5,
        "pregunta": "¿Cómo abro otra cuenta?",
        "respuesta": "Desde el Inicio, con el botón \"Abrir otra cuenta\", puedes abrir una de ahorros o corriente. "
                     "Es gratis, queda lista de inmediato y puedes tener hasta {MAX_CUENTAS_CLIENTE} cuentas.",
        "palabras": ["abrir cuenta", "otra cuenta", "nueva cuenta", "cuenta corriente", "segunda cuenta"],
        "relacionadas": ["tipos_cuenta"],
    },
    {
        "clave": "tipos_cuenta", "titulo": "Tipos de cuenta", "prioridad": 4,
        "pregunta": "¿Qué tipos de cuenta hay?",
        "respuesta": "Hay cuentas de ahorros y corrientes. Las dos sirven para enviar, recibir y retirar dinero. "
                     "Al registrarte en línea te abrimos una de ahorros.",
        "palabras": ["tipos de cuenta", "ahorros", "corriente", "diferencia entre cuentas"],
        "relacionadas": ["abrir_cuenta"],
    },
    {
        "clave": "cuenta_congelada", "titulo": "Cuenta congelada", "prioridad": 8, "accion": "cuentas",
        "pregunta": "Mi cuenta está congelada",
        "respuesta": "Si tu cuenta aparece congelada, el equipo de seguridad detectó algo inusual y la protegió. "
                     "Un asesor revisará tu caso: escribe \"asesor\" para que te atienda una persona.",
        "palabras": ["congelada", "congelaron", "congelado", "cuenta bloqueada", "no puedo usar mi cuenta"],
        "relacionadas": ["robo"],
    },
    {
        "clave": "cerrar_cuenta", "titulo": "Cerrar una cuenta", "prioridad": 5, "accion": "cuentas",
        "pregunta": "Quiero cerrar mi cuenta",
        "respuesta": "Para cerrar una cuenta, primero deja el saldo en cero (transfiérelo o retíralo). "
                     "El cierre lo hace un asesor: escribe \"asesor\" y te ayudamos.",
        "palabras": ["cerrar cuenta", "cancelar cuenta", "cerrar mi cuenta", "dar de baja", "eliminar cuenta"],
        "relacionadas": ["retiro"],
    },
    {
        "clave": "costos", "titulo": "Costos", "prioridad": 6,
        "pregunta": "¿Cuánto cuesta usar la cuenta?",
        "respuesta": "Abrir una cuenta en Banco Rosberg es gratis y las transferencias entre cuentas Rosberg no tienen "
                     "costo.",
        "palabras": ["costo", "cuanto cuesta", "cobran", "cuanto cobran", "comision", "cuota de manejo", "gratis", "tarifa"],
        "relacionadas": ["abrir_cuenta"],
    },
    {
        "clave": "tarjeta", "titulo": "Tarjeta física", "prioridad": 5,
        "pregunta": "¿Cómo pido la tarjeta física?",
        "respuesta": "En la página de ingreso del banco, sin iniciar sesión, está la opción \"Pedir tarjeta física\": "
                     "deja tu correo y un empleado te escribirá con los pasos de la entrega.",
        "palabras": ["tarjeta", "tarjeta fisica", "tarjeta debito", "plastico"],
        "relacionadas": ["retiro"],
    },
    # --------------------------------------------------------- seguridad
    {
        "clave": "usuario_bloqueado", "titulo": "Usuario bloqueado", "prioridad": 7,
        "pregunta": "Mi usuario está bloqueado",
        "respuesta": "Por seguridad, después de {MAX_INTENTOS_LOGIN} intentos fallidos tu usuario se bloquea por "
                     "{MINUTOS_BLOQUEO_LOGIN} minutos. Espera ese tiempo e intenta de nuevo. Si no recuerdas tu contraseña, "
                     "usa \"¿Olvidaste tu contraseña?\" en la pantalla de ingreso.",
        "palabras": ["bloqueado", "bloqueo", "no puedo entrar", "intentos", "me bloqueo", "usuario bloqueado"],
        "relacionadas": ["contrasena"],
    },
    {
        "clave": "contrasena", "titulo": "Olvidé mi contraseña", "prioridad": 6,
        "pregunta": "Olvidé mi contraseña",
        "respuesta": "Puedes cambiarla en la pantalla de ingreso con \"¿Olvidaste tu contraseña?\": te pediremos tu "
                     "correo, tu cédula y tu celular. Si estás dentro de la app, ve a Seguridad > Cambiar mi contraseña. "
                     "Nunca le des tu contraseña a nadie, ni siquiera al banco.",
        "palabras": ["contrasena", "olvide", "recuperar", "restablecer"],
        "relacionadas": ["cambiar_contrasena", "usuario_bloqueado"],
    },
    {
        "clave": "cambiar_contrasena", "titulo": "Cambiar la contraseña", "prioridad": 6,
        "pregunta": "¿Cómo cambio mi contraseña?",
        "respuesta": "En Seguridad > \"Cambiar mi contraseña\". Debe tener al menos 10 caracteres, con letras y números. "
                     "Al cambiarla cerramos tus demás sesiones abiertas, por seguridad.",
        "palabras": ["cambiar contrasena", "cambiar mi contrasena", "nueva contrasena", "actualizar contrasena"],
        "relacionadas": ["contrasena", "dos_pasos"],
    },
    {
        "clave": "dos_pasos", "titulo": "Verificación en dos pasos", "prioridad": 6, "accion": "seguridad",
        "pregunta": "¿Qué es la verificación en dos pasos?",
        "respuesta": "La verificación en dos pasos agrega un código de 6 dígitos que genera tu celular con Google "
                     "Authenticator, además de tu contraseña. Actívala en Seguridad. Si cambiaste de celular y no tienes "
                     "el código, un asesor te ayudará a recuperarla.",
        "palabras": ["dos pasos", "2fa", "autenticador", "authenticator", "codigo de 6", "doble factor"],
        "relacionadas": ["cambiar_contrasena", "no_fui_yo"],
    },
    {
        "clave": "no_fui_yo", "titulo": "Aviso de inicio de sesión", "prioridad": 8, "accion": "seguridad",
        "pregunta": "Me llegó un aviso de inicio de sesión",
        "respuesta": "Cuando alguien entra a tu cuenta desde un dispositivo o lugar nuevo, te mostramos un aviso "
                     "\"¿Fuiste tú?\". Si no fuiste tú, pulsa \"No fui yo\": cerramos todas las sesiones al instante. "
                     "Después cambia tu contraseña y activa la verificación en dos pasos.",
        "palabras": ["fuiste tu", "no fui yo", "aviso", "inicio de sesion", "alguien entro", "otro dispositivo"],
        "relacionadas": ["robo", "cambiar_contrasena", "dos_pasos"],
    },
    {
        "clave": "robo", "titulo": "Robo o fraude", "prioridad": 10, "accion": "seguridad",
        "pregunta": "Creo que me robaron",
        "respuesta": "Lamento lo que pasó. Haz esto ya: 1) cambia tu contraseña en Seguridad, 2) si ves un aviso "
                     "\"¿Fuiste tú?\", pulsa \"No fui yo\" para cerrar todas las sesiones, y 3) escribe \"asesor\": "
                     "una persona del equipo de fraude revisará tu cuenta.",
        "palabras": ["robo", "robaron", "me robaron", "fraude", "estafa", "estafaron", "hackearon", "hackeo",
                     "sin mi permiso", "no reconozco", "suplantacion"],
        "relacionadas": ["no_fui_yo", "cuenta_congelada"],
    },
    {
        "clave": "phishing", "titulo": "Mensajes falsos", "prioridad": 8,
        "pregunta": "Me pidieron mi contraseña por teléfono",
        "respuesta": "Banco Rosberg NUNCA te pedirá tu contraseña, tus códigos de verificación ni tus códigos de "
                     "retiro por teléfono, correo, WhatsApp o chat. Si alguien lo hizo, no se los des. Si ya los "
                     "diste, cambia tu contraseña ya y escribe \"asesor\".",
        "palabras": ["me llamaron", "me escribieron", "me pidieron", "whatsapp", "llamada", "correo falso",
                     "mensaje sospechoso", "link"],
        "relacionadas": ["robo", "cambiar_contrasena"],
    },
    {
        "clave": "datos_personales", "titulo": "Cambiar datos personales", "prioridad": 5,
        "pregunta": "¿Cómo cambio mi celular o mi correo?",
        "respuesta": "En \"Perfil\" ves tus datos (por seguridad, la cédula y el celular aparecen ocultos). "
                     "Para cambiar tu celular o tu correo, acércate a una oficina con tu cédula.",
        "palabras": ["cambiar celular", "cambiar correo", "cambiar mi numero", "actualizar datos", "perfil",
                     "mis datos", "datos personales"],
        "relacionadas": ["llaves"],
    },
    # -------------------------------------------------------------- otros
    {
        "clave": "empleo", "titulo": "Trabajar en el banco", "prioridad": 4,
        "pregunta": "¿Cómo trabajo en Banco Rosberg?",
        "respuesta": "En la página de ingreso del banco está \"Trabaja con nosotros\": deja tu correo y el equipo te "
                     "escribirá.",
        "palabras": ["trabajo", "empleo", "trabajar", "vacante", "hoja de vida"],
        "relacionadas": [],
    },
    {
        "clave": "saludo", "titulo": "Saludo", "prioridad": 1,
        "respuesta": "¡Hola! Soy el Asistente Rosberg. Cuéntame tu duda en pocas palabras o elige un tema.",
        "palabras": ["hola", "buenos dias", "buenas tardes", "buenas noches", "buenas", "saludos"],
        "relacionadas": [],
    },
    {
        "clave": "gracias", "titulo": "Agradecimiento", "prioridad": 2,
        "respuesta": "¡Con gusto! Si ya resolviste tu duda puedes pulsar \"Finalizar\" para cerrar la conversación y "
                     "calificarnos.",
        "palabras": ["gracias", "muchas gracias", "te agradezco", "listo", "perfecto"],
        "relacionadas": [],
    },
    {
        "clave": "despedida", "titulo": "Despedida", "prioridad": 2,
        "respuesta": "¡Que estés muy bien! Pulsa \"Finalizar\" arriba para cerrar la conversación. Si necesitas algo "
                     "más, abre una nueva cuando quieras.",
        "palabras": ["chao", "adios", "hasta luego", "nos vemos", "eso es todo", "nada mas"],
        "relacionadas": [],
    },
]

# Palabra -> lo que significa. Se aplica al texto del cliente Y a las palabras
# clave antes de comparar, asi "me robaron la clave" = "me robaron la contrasena".
SINONIMOS = {
    "clave": "contrasena", "password": "contrasena", "pass": "contrasena",
    "plata": "dinero", "platica": "dinero", "lucas": "dinero", "pesos": "dinero",
    "envio": "transferencia", "envie": "transferencia", "giro": "transferencia",
    "transferi": "transferencia", "mande": "transferencia",
    "celu": "celular", "cel": "celular", "telefono": "celular", "movil": "celular",
    "mail": "correo", "email": "correo", "gmail": "correo", "hotmail": "correo",
    "consigne": "consignar", "consignaron": "consignar",
    "hackers": "hackearon", "jaquearon": "hackearon",
    "app": "aplicacion",
}

# Ajustes a respuestas que ya podian existir en una base, por version.
# Se aplican una sola vez, al pasar a esa version.
AJUSTES = [
    # (version, clave, columna, valor)
    (2, "costos", "prioridad", 6),
    (2, "deposito", "prioridad", 6),
    (2, "mensaje_envio", "prioridad", 6),
]
QUITAR_PALABRAS = [
    # (version, clave, palabra): palabras demasiado generales que hacian ganar
    # a una respuesta en mensajes que no eran de su tema
    (2, "envio_revision", "transferencia"),
    (2, "costos", "cuesta"),
    # Venian de la primera version; ahora son de "No me llego el dinero"
    (3, "envio_revision", "no me llego"),
    (3, "envio_revision", "no ha llegado"),
    (3, "envio_revision", "no aparece"),
]
