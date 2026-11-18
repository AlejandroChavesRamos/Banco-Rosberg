# Banco Rosberg

Banco simulado con **detector de fraude**. Proyecto final de Bases de Datos.

- **MySQL 8.4**: la fuente de verdad (cuentas, saldos, transacciones, auditoría).
- **Neo4j 5.26**: el grafo de relaciones para detectar fraude (ciclos de dinero, dispositivos compartidos, cuentas mula).
- **Backend** en Python (FastAPI) y **frontend** en React.
- **Mailpit**: un buzón de correo de prueba para los correos que envía el banco.
- **Todo corre en contenedores Docker**: no hay que instalar MySQL, Neo4j, Python ni Node.

> El modelo de datos, el diccionario de datos y las decisiones de diseño están en [docs/BASE_DE_DATOS.md](docs/BASE_DE_DATOS.md).

---

## Contenido

1. [Requisitos](#1-requisitos)
2. [Descargar el proyecto](#2-descargar-el-proyecto)
3. [Crear el archivo `.env`](#3-crear-el-archivo-env)
4. [Levantar los contenedores](#4-levantar-los-contenedores)
5. [Crear el administrador](#5-crear-el-administrador)
6. [Cargar datos de prueba (opcional)](#6-cargar-datos-de-prueba-opcional)
7. [Usar el banco](#7-usar-el-banco)
8. [Conectarse a las bases de datos](#8-conectarse-a-las-bases-de-datos)
9. [El simulador](#9-el-simulador)
10. [Modo producción (HTTPS)](#10-modo-producción-https)
11. [Comandos del día a día](#11-comandos-del-día-a-día)
12. [Actualizar el proyecto sin perder los datos](#12-actualizar-el-proyecto-sin-perder-los-datos)
13. [Estructura del proyecto](#13-estructura-del-proyecto)
14. [Problemas comunes](#14-problemas-comunes)

---

## 1. Requisitos

| Necesitas | Para qué | Dónde |
|---|---|---|
| **Windows 10/11** con virtualización activada | Docker en Windows usa WSL 2 | Administrador de tareas → Rendimiento → CPU → *Virtualización: Habilitado* |
| **WSL 2** | El Linux liviano sobre el que corre Docker | PowerShell como administrador: `wsl --install` y reiniciar |
| **Docker Desktop** | Ejecutar los contenedores | https://www.docker.com/products/docker-desktop/ |
| *(Opcional)* MySQL Workbench, Neo4j Desktop | Ver los datos con interfaz gráfica | — |

**No necesitas instalar** MySQL, Neo4j, Python ni Node: vienen dentro de los contenedores.

Estos puertos de tu PC deben estar libres: **3307, 7475, 7688, 8000, 5173 y 8025** (y **80 y 443** solo para el modo producción). Usamos 3307 y no 3306 para no chocar con un MySQL instalado en el PC.

Comprueba que Docker funciona (Docker Desktop debe estar **abierto**, con *Engine running* en verde):

```powershell
docker --version
docker compose version
```

---

## 2. Descargar el proyecto

```powershell
git clone <url-del-repositorio> ProyectoFinalBase
cd ProyectoFinalBase
```

**Todos los comandos de esta guía se ejecutan dentro de esa carpeta.**

---

## 3. Crear el archivo `.env`

El `.env` guarda las contraseñas y claves. **Nunca se sube a Git** (está en `.gitignore`), por eso cada persona crea el suyo a partir de la plantilla.

### 3.1 Copiar la plantilla

```powershell
Copy-Item .env.example .env
notepad .env
```

### 3.2 Cambiar las contraseñas

Cambia **todos** los valores que empiezan por `CambiaEsta...`. Reglas:

- Sin comillas y sin el carácter `'`.
- `NEO4J_PASSWORD`: mínimo 8 caracteres.
- `SIM_PASSWORD_CLIENTES`: mínimo 10 caracteres, con letras y números (es la contraseña de todos los clientes simulados).
- `TZ`: tu zona horaria (por ejemplo `America/Bogota`).

### 3.3 Generar las 3 claves criptográficas

`JWT_SECRETO`, `CLAVE_CIFRADO` y `CLAVE_INDICES` deben ser **32 bytes aleatorios en base64**. Ejecuta este comando **tres veces** y pega cada resultado en una de las tres variables:

```powershell
$b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b)
```

Debe quedar algo así (con tus propios valores):

```env
JWT_SECRETO=q3V9yYk0bS1...=
CLAVE_CIFRADO=Zf8xP2mWn7...=
CLAVE_INDICES=Hc4tR6uLs0...=
```

> **No pierdas `CLAVE_CIFRADO`.** Con ella se cifran las cédulas y los celulares; sin ella esos datos no se pueden recuperar. Si dejas el texto `GENERA_UNA_CLAVE`, el backend no arranca.

---

## 4. Levantar los contenedores

```powershell
docker compose up -d --build
```

La **primera vez** tarda varios minutos: descarga las imágenes de MySQL y Neo4j y construye las del backend y el frontend. Las siguientes veces basta con `docker compose up -d`.

Comprueba que los **5 contenedores** estén sanos:

```powershell
docker compose ps
```

```
NAME             STATUS
banco_backend    Up (healthy)
banco_frontend   Up (healthy)
banco_mailpit    Up (healthy)
banco_mysql      Up (healthy)
banco_neo4j      Up (healthy)
```

Si alguno dice `health: starting`, espera unos segundos y repite. Abre también **http://localhost:8000/salud**; debe responder:

```json
{"api":"ok","mysql":"ok","neo4j":"ok","estado":"ok"}
```

Al crearse por primera vez, MySQL ejecuta solo los scripts de `db/mysql/init/` (tablas, procedimientos, usuarios con privilegios mínimos y datos base) y el backend crea las restricciones del grafo en Neo4j.

---

## 5. Crear el administrador

El primer administrador se crea por consola (así ninguna contraseña queda guardada en el repositorio):

```powershell
docker compose exec backend python -m app.cli crear-admin --email admin@rosberg.co --nombre "Tu Nombre"
```

Te pedirá la contraseña dos veces (mínimo 10 caracteres, con letras y números). Mientras escribes no se ve nada: es normal.

Los demás empleados (cajeros, analistas) se crean desde la Intranet: **Empleados → Nuevo empleado**. Cada uno recibe una contraseña temporal que debe cambiar al entrar. Si un empleado olvida su contraseña, el administrador le da una temporal nueva desde **Empleados → Restablecer contraseña**.

---

## 6. Cargar datos de prueba (opcional)

El simulador llena el banco con **500 clientes, 90 días de movimientos y 8 casos de fraude escondidos**:

```powershell
docker compose run --rm simulador cargar
```

Tarda unos 4 minutos y solo se puede ejecutar una vez. Al terminar muestra la lista de fraudes plantados. Todos los clientes simulados usan la contraseña `SIM_PASSWORD_CLIENTES` de tu `.env`.

---

## 7. Usar el banco

| Portal | Dirección | Quién entra |
|---|---|---|
| **App Rosberg** | http://localhost:5173/app | Clientes. Cualquiera puede registrarse desde la pantalla de inicio. La página de inicio también tiene *Pedir tarjeta*, *Contáctanos* y *Trabaja con nosotros* (`/app/carreras`). |
| **Intranet Rosberg** | http://localhost:5173/intranet | Empleados: cajero, analista de fraude y administrador. |
| **API (documentación interactiva)** | http://localhost:8000/docs | Para probar la API directamente. El login exige `"portal": "app"` o `"portal": "intranet"`. |
| **Estado del sistema** | http://localhost:8000/salud | Estado de la API y de cada base. |
| **Buzón de correos (Mailpit)** | http://localhost:8025 | Los correos que envía el banco. No salen a internet: llegan aquí. |

Recorrido sugerido:

1. **Intranet** (admin): crea un cajero y un analista.
2. **App**: registra un cliente; abre otro en ventanilla como cajero.
3. **Intranet** (cajero → Ventanilla): deposita dinero al cliente.
4. **App**: registra una llave (celular o correo) y transfiere a otro cliente.
5. **App** → Retirar sin tarjeta: genera un código; canjéalo como cajero.
6. **Intranet** (analista → Alertas): revisa alertas, abre el grafo de una cuenta, lanza el barrido del historial.
7. **App** (sin iniciar sesión): deja tu correo en *Contáctanos*. En la **Intranet → Solicitudes** ábrela y respóndela: la respuesta llega por correo a **http://localhost:8025**.
8. **App** → *¿Olvidaste tu contraseña?*: el cliente la cambia demostrando su cédula y su celular (el banco no envía correos). En **Perfil** ve sus datos enmascarados.
9. **App → Ayuda**: abre una conversación con un asesor. En la **Intranet → Atención al cliente** un empleado pulsa *Atender* y le responde; el chat se actualiza solo en las dos pantallas. Al finalizar, el cliente califica la atención (el promedio aparece en el Tablero).
11. **Intranet** (admin) → **Asistente**: el contestador automático (sin IA externa, todo local).
    - Entiende errores de escritura (“trasferencia”), sinónimos (“clave” = contraseña) y variantes (“retiré”, “retirar”).
    - Responde con **los datos reales del cliente** cuando sirve: sus envíos, saldo, cuentas, códigos de retiro, llaves o seguridad (solo lectura, enmascarados).
    - Muestra **botones** de respuesta rápida (“Sí, me sirvió”, temas relacionados) y recuerda de qué se venía hablando.
    - En **Lo que no entendió**, el admin le enseña con un clic. También ve qué respuestas le sirven a los clientes, prueba textos y edita respuestas y sinónimos.
    - Se activa a mano (Atención al cliente → *Activar asistente*) o solo, si nadie atiende un tiquete en X minutos. Se apaga cuando un empleado toma el caso, si no entiende dos veces o si el cliente escribe “asesor”.
10. **App → Enviar dinero**: escribe un mensaje opcional (“Para el almuerzo”). Quien recibe lo ve en sus movimientos.

---

## 8. Conectarse a las bases de datos

### MySQL Workbench

| Campo | Valor |
|---|---|
| Hostname | `127.0.0.1` |
| Port | `3307` |
| Username | `root` (o `banco_reportes`, de solo lectura) |
| Password | la de tu `.env` |
| Base de datos | `banco` (y `banco_sim`, la del simulador) |

Workbench mostrará una advertencia de versión (MySQL 8.4): elige **Continue Anyway**.

### Neo4j

Abre **http://localhost:7475** y conéctate con:

- URL: `bolt://127.0.0.1:7688` (usa `127.0.0.1`, no `localhost`)
- Usuario: `neo4j` · Contraseña: la de tu `.env`

Para ver una parte del grafo: `MATCH (n) RETURN n LIMIT 100;`

---

## 9. El simulador

```powershell
docker compose run --rm simulador en-vivo                 # tráfico normal continuo (Ctrl + C para detener)
docker compose run --rm simulador lanzar robo             # lanzar un fraude: robo | ciclo | mula | dispositivo
docker compose run --rm simulador reporte                 # hoja de respuestas: qué cuentas son fraude
docker compose run --rm simulador evaluar                 # qué tan bien detecta el motor (precisión y cobertura)
```

Para una demo: deja `en-vivo` corriendo en una terminal, abre **Intranet → Alertas** y, en otra terminal, ejecuta `lanzar robo`. La alerta aparece sola en unos segundos.

> Si el administrador enciende "2FA obligatoria para empleados", el cajero del simulador no podrá entrar (no tiene app autenticadora). Apágalo antes de usar `lanzar mula`.

---

## 10. Modo producción (HTTPS)

Mismo banco y mismos datos, pero con una sola puerta de entrada: **nginx con HTTPS**. Las bases quedan sin puertos hacia afuera, `/docs` se oculta y se activan el límite de intentos y las cabeceras de seguridad.

```powershell
docker compose down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Abre **https://localhost/app** y **https://localhost/intranet**. La primera vez el navegador dirá *"La conexión no es privada"* (el certificado es autofirmado): **Avanzado → Continuar a localhost**.

En este modo **Workbench no puede conectarse**. Para volver a desarrollo:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose up -d
```

---

## 11. Comandos del día a día

| Quiero… | Comando |
|---|---|
| Encender todo | `docker compose up -d` |
| Ver el estado | `docker compose ps` (con `-a` muestra también los apagados) |
| Ver los registros de un servicio | `docker compose logs -f backend` |
| Apagar / encender un servicio | `docker compose stop mysql` · `docker compose start mysql` |
| Reiniciar un servicio | `docker compose restart backend` |
| Reconstruir tras cambiar librerías o un Dockerfile | `docker compose up -d --build backend` |
| Apagar todo (los datos se conservan) | `docker compose down` |
| **Borrar todo, incluidos los datos** | `docker compose down -v` ⚠️ sin vuelta atrás |

Los datos viven en **volúmenes** (`mysql_data`, `neo4j_data`, `mailpit_data`), no en los contenedores: `down` borra los contenedores pero no los datos. Solo `down -v` los elimina.

---

## 12. Actualizar el proyecto sin perder los datos

Los scripts de `db/mysql/init/` **solo corren cuando la base está vacía**. Si ya tenías el proyecto corriendo y haces `git pull`, las tablas o permisos nuevos no aparecen solos: hay que aplicarlos a mano (o borrar todo con `docker compose down -v`, perdiendo los datos).

```powershell
git pull
docker compose up -d --build
```

Luego aplica lo que tu base no tenga todavía:

| Cambio | Si te falta… | Comando |
|---|---|---|
| Seguridad (2FA, avisos de inicio de sesión) | Error `Unknown column 'totp_ultimo_paso'` o falta la tabla `avisos_login` | Ver abajo ① |
| Solicitudes públicas (tarjeta, contacto, empleo) | Error `Table 'banco.solicitudes_publicas' doesn't exist` | Ver abajo ② |
| Mensajería (chat de ayuda, respuestas por correo, mensaje en transferencias) | Error `Table 'banco.tiquetes' doesn't exist` o `Incorrect number of arguments for PROCEDURE banco.sp_transferir` | Ver abajo ③ |
| Asistente automático | Error `Unknown column 't.asistente_activo'` | Ver abajo ④ |
| Metas de ahorro | Error `Table 'banco.metas_ahorro' doesn't exist` | Ver abajo ⑤ |

① Seguridad (en PowerShell):

```powershell
Get-Content db/mysql/migraciones/2026-11-15_fase6_seguridad.sql | docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" banco'
docker compose exec mysql bash /docker-entrypoint-initdb.d/03_usuarios.sh
```

② Solicitudes:

```powershell
docker compose exec mysql bash /docker-entrypoint-initdb.d/07_solicitudes.sh
```

③ Mensajería (después de ②; el orden importa porque una tabla nueva apunta a `solicitudes_publicas`):

```powershell
Get-Content db/mysql/migraciones/2026-11-17_mensaje_transferencias.sql | docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" banco'
docker compose exec mysql bash /docker-entrypoint-initdb.d/03_usuarios.sh
docker compose exec mysql bash /docker-entrypoint-initdb.d/08_mensajeria.sh
```

④ Asistente automático (después de ③):

```powershell
docker compose exec mysql bash /docker-entrypoint-initdb.d/09_asistente.sh
```

⑤ Metas de ahorro:

```powershell
docker compose exec mysql bash /docker-entrypoint-initdb.d/10_metas.sh
```

Después reinicia el backend: `docker compose restart backend`.

---

## 13. Estructura del proyecto

```
ProyectoFinalBase/
├── docker-compose.yml          ← servicios en modo desarrollo
├── docker-compose.prod.yml     ← cambios para producción (nginx + HTTPS)
├── .env.example                ← plantilla de contraseñas (el .env real no se sube)
├── backend/                    ← API en Python (FastAPI) + simulador
│   ├── Dockerfile
│   └── app/
│       ├── main.py             ← arranque de la API
│       ├── rutas/              ← endpoints: auth, cliente, cajero, analista, admin, tablero, seguridad, publico, ayuda
│       ├── seguridad/          ← Argon2, JWT, cifrado AES-GCM, 2FA, roles
│       ├── servicios/          ← lógica del banco, auditoría, sincronización con Neo4j, envío de correos
│       ├── antifraude/         ← motor en tiempo real y barrido del historial
│       └── simulador/          ← generador de datos y fraudes de prueba
├── frontend/                   ← pantallas en React (App + Intranet)
│   ├── Dockerfile
│   └── src/
│       ├── cliente/            ← pantallas de la App Rosberg
│       ├── intranet/           ← pantallas de la Intranet
│       ├── componentes/        ← piezas comunes (botones, íconos, 2FA, logo animado, chat)
│       └── imagenes/           ← fotos de las pantallas (créditos en CREDITOS.md)
├── nginx/                      ← configuración de producción (HTTPS, límites, cabeceras)
├── db/
│   ├── mysql/init/             ← scripts que MySQL ejecuta la primera vez
│   ├── mysql/migraciones/      ← cambios aplicados a una base ya existente
│   └── neo4j/                  ← restricciones e índices del grafo
└── docs/
    └── BASE_DE_DATOS.md        ← modelo de datos y decisiones de diseño
```

---

## 14. Problemas comunes

| Síntoma | Solución |
|---|---|
| `failed to connect to the docker API` | Docker Desktop está cerrado. Ábrelo y espera *Engine running*. |
| `no configuration file provided` | No estás en la carpeta del proyecto: `cd ProyectoFinalBase`. |
| `port is already allocated` | Otro programa usa ese puerto. Ciérralo o cambia `MYSQL_PORT` en `.env`. |
| El backend se reinicia una y otra vez | Revisa `docker compose logs backend`. Casi siempre es una clave del `.env` sin generar (`GENERA_UNA_CLAVE`). |
| Workbench: *Access denied* | Usa el puerto 3307. Si cambiaste el `.env` después del primer arranque, las contraseñas viejas siguen en el volumen. |
| Neo4j: *Connection to instance failed* | Usa `bolt://127.0.0.1:7688` (no `localhost`, no `neo4j+s://`). |
| `/bin/bash^M: bad interpreter` | Un `.sh` quedó con saltos de línea de Windows. En VS Code cambia `CRLF` → `LF`. El `.gitattributes` del proyecto lo evita al clonar. |
| Una respuesta a una solicitud dice *No se pudo enviar el correo* | Mailpit está apagado: `docker compose up -d mailpit` y pulsa **Reintentar** en la conversación. La respuesta no se pierde. |
| `https://localhost` no carga | Estás en modo desarrollo: usa `http://localhost:5173/app` o sigue la sección 10. |
| El usuario quedó bloqueado | 5 intentos fallidos (contraseña, código 2FA o recuperación) bloquean el usuario 15 minutos; el mensaje dice cuántos minutos faltan. Un empleado puede pedirle al admin una contraseña temporal. |
| `Table ... doesn't exist` o `Unknown column` tras un `git pull` | Tu base es anterior al cambio: sigue la sección 12. |

---

*Banco Rosberg es un banco simulado con fines académicos.*
