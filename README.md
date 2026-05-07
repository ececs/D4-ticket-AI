# D4-Ticket AI

Aplicación full-stack de ticketing colaborativo desarrollada para la prueba técnica de Orbidi.
Repositorio creado específicamente para esta prueba.

## Demo en producción

**URL:** [https://frontend-eight-chi-54.vercel.app/board]

Hay dos formas de acceder:

- **Google OAuth** — disponible para cuentas personales Gmail y para cuentas del dominio `@orbidi.com`.
- **Modo demo** — acceso rápido para evaluación, facilitado directamente por email al equipo de ORBIDI.

> **Nota sobre acceso:** Orbidi solicitó que en entorno local cualquier cuenta Google pueda registrarse y acceder, y así funciona (configurando `ALLOWED_EMAILS=["*"]` para acceso abierto). En la demo desplegada en producción se restringió el acceso por seguridad para evitar registros no deseados en la instancia pública. El acceso demo se ha facilitado directamente por email al equipo de ORBIDI. Si fuese necesario volver a compartirlo, puedo proporcionarlo de nuevo sin problema.

Incluye:

- autenticación con Google OAuth 2.0
- vista lista y vista Kanban sobre el mismo conjunto de tickets
- comentarios, adjuntos y reasignación
- notificaciones en tiempo real
- asistente conversacional con IA para consultar y operar sobre tickets
- búsqueda híbrida (semántica + keyword) con `pgvector`

## Stack

| Capa          | Tecnología                                                    |
| :------------ | :------------------------------------------------------------ |
| Frontend      | Next.js 16, React 19, TypeScript, Tailwind CSS, Zustand       |
| Backend       | FastAPI, SQLAlchemy 2, Pydantic v2, Alembic                   |
| Base de datos | PostgreSQL 16 + `pgvector`                                    |
| Tiempo real   | WebSockets + Redis Pub/Sub con fallback a PostgreSQL NOTIFY   |
| Storage       | MinIO en local / Cloudflare R2 en producción                  |
| IA            | LangGraph, Gemini 2.5 Flash, OpenAI GPT-4o-mini como fallback |

## Decisiones técnicas

- **FastAPI + Next.js**: stack moderno, productivo y con un excelente equilibrio entre velocidad de desarrollo y mantenibilidad. FastAPI aporta tipado, validación y documentación automática; Next.js resuelve bien App Router, cliente/servidor y una UI reactiva.
- **Persistencia real desde el primer momento**: el proyecto no usa mocks ni almacenamiento efímero. Toda la lógica trabaja sobre PostgreSQL, lo que garantiza la integridad referencial, la consistencia de los datos y un control de versiones robusto del esquema mediante migraciones.
- **PostgreSQL + pgvector para búsqueda híbrida**: la búsqueda semántica por sí sola puede perder coincidencias literales útiles; la búsqueda keyword por sí sola pierde contexto. Por eso la búsqueda final combina ambas señales con Reciprocal Rank Fusion.
- **Redis + PG NOTIFY como fallback**: Redis se usa para Pub/Sub y sincronización en tiempo real. Cuando Redis no está disponible, la aplicación degrada a PostgreSQL NOTIFY para no romper el sistema.
- **MinIO en local / Cloudflare R2 en producción**: ambos exponen API S3-compatible, así que el mismo código de adjuntos sirve en desarrollo y despliegue real.
- **Asistente IA con tool calling**: el chat no toca la base de datos “por libre”; reutiliza servicios y endpoints del propio sistema. Esto reduce duplicación y ayuda a que UI e IA respeten las mismas reglas.
- **Permisos conservadores en acciones destructivas**: cualquier usuario autenticado puede colaborar, comentar o reasignar, pero el borrado queda restringido al autor del ticket. Si otro usuario lo intenta, puede solicitar el borrado al autor mediante notificación.
- **Historial de actividad persistente**: se guarda el cambio relevante del ticket (estado, prioridad, asignación, etc.) para poder explicar qué pasó y también para dar contexto al asistente.

## Arquitectura resumida

### Backend

- `FastAPI` organiza la API por routers (`tickets`, `comments`, `attachments`, `notifications`, `auth`, `ai`).
- `SQLAlchemy 2` modela entidades y relaciones.
- `Alembic` versiona cambios de esquema.
- La lógica de dominio se concentra en servicios (`ticket_service`, `notification_service`, `comment_service`, etc.) para mantener routers finos.

### Frontend

- `Next.js App Router` para estructura de aplicación.
- `Zustand` para estado compartido ligero:
  - usuario autenticado
  - notificaciones
  - selección de tickets
  - estado del chat IA
- Componentes separados por responsabilidad: tablero, detalle, notificaciones, chat, formularios.

### Tiempo real

- El backend emite eventos WebSocket para:
  - `ticket_created`
  - `ticket_updated`
  - `ticket_deleted`
  - `notification`
  - `notification_read`
  - `notifications_read_all`
- El frontend actualiza estado local o hace refetch parcial según el tipo de evento.

Los eventos emitidos son:

| Evento                   | Descripción                                   |
| :----------------------- | :-------------------------------------------- |
| `ticket_created`         | un ticket nuevo fue creado                    |
| `ticket_updated`         | un ticket fue modificado                      |
| `ticket_deleted`         | un ticket fue eliminado                       |
| `notification`           | notificación nueva para el usuario            |
| `notification_read`      | una notificación fue marcada como leída       |
| `notification_deleted`   | una notificación fue eliminada                |
| `notifications_read_all` | todas las notificaciones marcadas como leídas |
| `web_scrape_completed`   | el análisis de la URL del cliente finalizó    |

### IA

- El agente está construido con `LangGraph`.
- Las capacidades se exponen como tools:
  - consultar tickets
  - crear tickets
  - cambiar estado
  - añadir comentarios
  - reasignar
  - actualizar
  - consultar historial
  - buscar usuarios por nombre para reasignación asistida
  - borrar con confirmación humana
  - diagnóstico IA específico del ticket (análisis centrado en ese caso concreto)
- Para temas documentales o contexto cliente, el agente usa búsqueda sobre base de conocimiento.
- Además del chat general, el detalle del ticket incluye un **botón de diagnóstico IA** que genera un análisis específico para ese ticket usando su información estructurada y el contexto disponible.

## Qué está implementado

- login con Google
- modo demo para evaluadores
- CRUD de tickets
- filtros, ordenación y paginación
- vista Kanban con drag & drop
- comentarios
- adjuntos con límite de 10 MB
- reasignación
- notificaciones in-app con badge de no leídas
- sincronización multi-pestaña
- historial de actividad del ticket
- asistente IA con creación, consulta, cambio de estado, comentario, reasignación y borrado asistido
- diagnóstico IA específico desde el detalle del ticket
- enriquecimiento contextual mediante URL del cliente y resumen/manual notes del operador

## Comportamientos relevantes

### Reasignación

- La reasignación está disponible desde la UI y desde el asistente.
- Si el usuario pide reasignar por nombre, el asistente busca coincidencias:
  - si hay una sola coincidencia, confirma por nombre completo
  - si hay varias, pide aclaración
  - solo pide email cuando sigue habiendo ambigüedad o no encuentra a nadie

### Diagnóstico IA y contexto

- Cada ticket puede incluir una **URL del cliente** (`client_url`).
- El sistema puede analizar esa web en segundo plano y guardar contexto extraído para enriquecer el diagnóstico.
- El ticket también permite guardar un **resumen manual del cliente** o notas operativas (`client_summary`) para añadir contexto de negocio o técnico que no está en la web.
- Desde el detalle del ticket hay un **botón de diagnóstico IA** que genera un análisis específico del caso usando:
  - título y descripción
  - estado y prioridad
  - historial del ticket
  - contexto extraído de la web del cliente
  - contexto manual añadido por el operador

### RAG

- El proyecto usa un enfoque de **RAG aplicado al soporte**.
- La base de conocimiento puede combinar:
  - contenido extraído de la web del cliente
  - contexto estructurado del propio ticket
  - historial de cambios
- El objetivo no es solo responder preguntas generales, sino ayudar a que la IA diagnostique mejor cada incidencia con contexto real del cliente.

### Borrado de tickets

- Solo el autor puede borrar un ticket.
- Si otro usuario intenta borrarlo:
  - la UI lo impide
  - el asistente tampoco lo ejecuta
  - el sistema puede enviar una notificación al autor para pedirle que lo elimine

### Notificaciones

- Hay notificaciones por asignación, comentario, cambio relevante de ticket y solicitud de borrado.
- Se pueden marcar como leídas, marcar todas como leídas y borrar individualmente.
- La sincronización entre pestañas del mismo usuario está soportada.

## Levantamiento local

Hay dos formas de arrancar el proyecto:

1. **Docker Compose**: la más rápida y recomendable para validarlo desde cero.
2. **Manual**: útil si quieres depurar backend/frontend por separado.

### Opción A: Docker Compose

#### Requisitos

- Docker Desktop o Docker Engine + Compose
- una API key de Google AI Studio si se quiere usar el asistente completo

#### Qué levanta Docker Compose

- PostgreSQL 16 + `pgvector`
- Redis
- MinIO
- backend FastAPI
- frontend Next.js

#### Pasos

1. Crear el archivo de entorno raíz:

```bash
cp .env.example .env
```

2. Editar `.env` y completar como mínimo:

- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_API_KEY`

Opcionales pero recomendables:

- `OPENAI_API_KEY` para fallback del agente
- `DEMO_ACCESS_CODE` para acceso rápido del evaluador
- `ALLOWED_EMAILS` si se quiere restringir quién puede entrar

Si no quieres depender de Google OAuth durante la revisión, configura también:

- `DEMO_ACCESS_CODE`

Con eso, el evaluador puede entrar desde la pantalla de login usando el código demo sin necesidad de configurar Google OAuth en su entorno.

3. Levantar el stack (desde la raíz del proyecto):

```bash
docker-compose up --build
```

El backend aplica automáticamente las migraciones de base de datos (`alembic upgrade head`) al arrancar el contenedor, de modo que no es necesario ejecutarlas de manera manual en tu máquina local.

#### Servicios disponibles

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- MinIO Console: [http://localhost:9001](http://localhost:9001)
- PostgreSQL expuesto en host: `localhost:5433`

#### Notas

- En Docker local se usa **MinIO** como storage S3-compatible.
- El frontend usa `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- El contenedor backend ejecuta migraciones al arrancar, incluyendo las últimas del enum de notificaciones.
- Si cambias el esquema local, `docker-compose up` volverá a ejecutar `alembic upgrade head` de forma segura.

#### Validación rápida tras arrancar

1. Abrir [http://localhost:3000](http://localhost:3000)
2. Entrar por Google o modo demo
3. Crear un ticket
4. Verificar que aparece en lista y Kanban
5. Abrir [http://localhost:8000/docs](http://localhost:8000/docs) para comprobar que la API está operativa

#### Datos de prueba (opcional)

Para poblar la instancia con tickets realistas sin crearlos manualmente, hay un script en `docs_private/seed_data.py` que crea 12 tickets con distintos estados, prioridades y asignaciones. Está pensado para la demo en producción pero funciona igual en local apuntando a `http://localhost:8000/api/v1`. Requiere un token JWT válido (se obtiene de la cookie `access_token` tras iniciar sesión).

```bash
TOKEN=<tu_token> python3 docs_private/seed_data.py
```

### Opción B: Ejecución manual

#### Requisitos

- Python 3.12
- Node.js 22+
- npm
- PostgreSQL 16 con extensión `pgvector`
- Redis
- MinIO o cualquier storage S3-compatible para adjuntos

#### 1. Infraestructura local

Si quieres ejecutar solo backend y frontend fuera de Docker, puedes seguir usando Docker para la infraestructura:

```bash
docker-compose up -d db redis minio
```

#### 2. Configurar backend

Crear archivo de entorno del backend:

```bash
cp backend/.env.example backend/.env
```

Valores importantes para ejecución manual:

- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ticketai`
- `REDIS_URL=redis://localhost:6379`
- `STORAGE_ENDPOINT=http://localhost:9000`
- `FRONTEND_URL=http://localhost:3000`
- `BACKEND_URL=http://localhost:8000`
- `GOOGLE_API_KEY=...`
- `OPENAI_API_KEY=...` si quieres activar fallback del agente
- `DEMO_ACCESS_CODE=...` si quieres login demo

Instalar dependencias y lanzar:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip uv
uv pip install --python .venv/bin/python -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Notas:

- `alembic upgrade head` es obligatorio también en manual.
- Sí hay migraciones recientes en el proyecto, incluida una para el tipo de notificación `deletion_requested`.
- El backend lee `backend/.env` cuando se ejecuta desde la carpeta `backend`.

#### 3. Configurar frontend

Asegúrate de que `frontend/.env.local` contiene al menos:

```bash
cat > frontend/.env.local <<'EOF'
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_FRONTEND_URL=http://localhost:3000
EOF
```

Instalar y lanzar:

```bash
cd frontend
npm install
npm run dev
```

#### URLs

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)

## Variables de entorno más importantes

### Backend

| Variable               | Descripción                                                                         |
| :--------------------- | :---------------------------------------------------------------------------------- |
| `DATABASE_URL`         | conexión async a PostgreSQL                                                         |
| `REDIS_URL`            | conexión a Redis                                                                    |
| `SECRET_KEY`           | firma de JWT                                                                        |
| `GOOGLE_CLIENT_ID`     | OAuth Google                                                                        |
| `GOOGLE_CLIENT_SECRET` | OAuth Google                                                                        |
| `FRONTEND_URL`         | URL del frontend                                                                    |
| `BACKEND_URL`          | URL pública del backend                                                             |
| `GOOGLE_API_KEY`       | Gemini / embeddings                                                                 |
| `OPENAI_API_KEY`       | fallback del agente                                                                 |
| `STORAGE_ENDPOINT`     | MinIO o R2                                                                          |
| `STORAGE_ACCESS_KEY`   | credencial S3                                                                       |
| `STORAGE_SECRET_KEY`   | credencial S3                                                                       |
| `STORAGE_BUCKET`       | bucket de adjuntos                                                                  |
| `DEMO_ACCESS_CODE`     | acceso demo opcional                                                                |
| `ALLOWED_EMAILS`       | lista de emails o dominios autorizados para login (vacío = cualquier cuenta Google) |

### Frontend

| Variable                   | Descripción              |
| :------------------------- | :----------------------- |
| `NEXT_PUBLIC_API_URL`      | URL base del backend     |
| `NEXT_PUBLIC_FRONTEND_URL` | URL pública del frontend |

## Base de datos y migraciones

- El proyecto usa `Alembic` para versionar cambios de esquema.
- El backend ejecuta `alembic upgrade head` al arrancar en Docker.
- En ejecución manual hay que lanzarlo explícitamente antes de iniciar FastAPI.
- La base de datos incluye:
  - tablas de tickets, comentarios, adjuntos, usuarios y notificaciones
  - historial de actividad
  - soporte `pgvector`
  - ajustes para preservar histórico cuando un ticket se elimina

## Acceso para evaluación

Se puede entrar de dos formas:

- **Google OAuth** — cualquier cuenta Google en local (sin restricciones, tal como se solicitó); en producción el acceso está más restringido para proteger la instancia pública.
- **Modo demo** — sin necesidad de cuenta Google, usando el código `Orbidi@2026Xdesafio` en la pantalla de login. Este acceso se ha dejado de forma temporal para facilitar la evaluación.

Esto evita depender obligatoriamente de una cuenta Google durante la revisión.

## Qué probar rápidamente si se levanta desde cero

Si estás validando una instalación limpia, esta secuencia cubre lo importante:

1. login
2. crear ticket
3. moverlo en Kanban
4. editar prioridad o descripción
5. añadir comentario
6. subir adjunto
7. abrir notificaciones
8. usar el asistente para consultar o actualizar un ticket
9. abrir una segunda pestaña y comprobar sincronización en tiempo real

Antes de la entrega se realizó además una validación manual final de funcionalidad, responsividad, flujos del asistente, sincronización en tiempo real y casos límite relevantes del sistema.

## Checklist de validación recomendada

Además del arranque técnico, esta es la comprobación funcional que considero más útil antes de entregar o revisar:

### Backend y arranque

- ejecutar `alembic upgrade head`
- abrir Swagger en `/docs`
- ejecutar `uv run pytest tests -q`

### Frontend

- ejecutar `npm run lint`
- ejecutar `npm run type-check`
- ejecutar `npm run build`

### Flujo funcional mínimo

- login
- crear ticket
- comprobar que aparece en lista y Kanban
- reasignar ticket
- cambiar estado
- añadir comentario
- subir y eliminar adjunto
- abrir notificaciones y marcar como leídas
- abrir una segunda pestaña y verificar sincronización
- usar el asistente para consultar y modificar un ticket
- probar borrado con confirmación humana

### Casos importantes de UX

- estado vacío sin tickets
- estado vacío con filtros activos
- rollback visual ante error de borrado
- vista lista en horizontal con scroll
- board y chat en móvil
- toasts y panel IA sin solapamientos en móvil

## Comandos útiles

### Backend

```bash
uv run pytest tests -q
```

También útiles:

```bash
cd backend
alembic current
alembic history
```

### Frontend

```bash
npm run lint
npm run type-check
npm run build
```

Tests unitarios con Vitest (43 casos):

```bash
cd frontend
npx vitest run
```

La batería cubre cuatro módulos:

- **`ticketRealtime`** — lógica pura de inserción en tiempo real: filtros activos (status, priority, assignee_id), ordenación por campo y dirección, refetch cuando hay búsqueda o página > 1, truncado por tamaño de página con totalDelta correcto.
- **`notificationStore`** — store Zustand: deduplicación, addNotification, syncMarkOneRead/All (con y sin server count), syncRemoveNotification, triggerRefresh/Delete, markAsRead y markAllAsRead optimistas.
- **`useTickets`** — hook de datos: carga inicial, error state, update parcial por WS, fast-path de borrado, refetch por señal global, rollback optimista en status y delete, updateTicket.
- **`useWebSocket`** — ciclo de vida del socket: conexión con token, eventos ticket_created/updated/deleted (incluyendo alias y fallbacks), notification/read/deleted/read_all, web_scrape_completed, ping ignorado, reconexión tras cierre anormal, no reconexión en cierre limpio, onerror, limpieza en unmount.

## Estado actual del asistente IA

El asistente es una mejora funcional real del sistema, no solo una demo textual.

Actualmente puede:

- consultar tickets con filtros
- crear tickets
- cambiar estado
- añadir comentarios
- reasignar tickets
- actualizar campos
- revisar historial
- pedir borrado con confirmación humana
- apoyarse en contexto documental y del cliente para responder mejor

Además del chat, existe una acción específica de **Diagnóstico IA** en el detalle del ticket para obtener un análisis más centrado en ese caso concreto.

Además:

- usa contexto del ticket abierto o tickets seleccionados
- puede apoyarse en búsqueda documental
- respeta permisos del sistema

## Trade-offs aceptados

- La confirmación de acciones sensibles se resuelve en frontend, no con `interrupt/resume` persistente del grafo.
- El identificador visible del ticket es un fragmento de UUID, no un contador secuencial.
- **Zustand + React Hooks frente a React Query:** Se optó deliberadamente por un estado del cliente basado en Zustand y hooks personalizados en lugar de React Query. Dado que el sistema utiliza **sincronización en tiempo real vía WebSockets con actualizaciones optimistas**, un almacén de estado ligero como Zustand permite manipular quirúrgicamente el estado de la UI (inserciones, modificaciones y borrados reactivos) ante eventos entrantes del WebSocket, evitando los bucles de revalidación redundantes en segundo plano y el overhead de red propios de las políticas de caché por defecto de React Query.
- Algunas decisiones de UX y permisos son deliberadamente conservadoras para priorizar estabilidad y claridad en una prueba técnica de una semana.

## Uso de IA durante el desarrollo

Durante el desarrollo se utilizaron herramientas de IA generativa como apoyo puntual en tareas de productividad y revisión técnica. En concreto:

- **Scaffolding inicial** de algunas piezas del frontend y backend.
- **Generación y ampliación de tests** de regresión y validaciones.
- **Revisión de código** para detectar edge cases, incoherencias y mejoras de robustez.
- **Documentación** y refinado del README.

Todas las decisiones de arquitectura, integración, permisos, validaciones y comportamiento final fueron revisadas manualmente. Ningún fragmento se incorporó sin adaptación al contexto del proyecto y validación posterior mediante ejecución local y batería de tests.

## Limitaciones / mejoras futuras

- El asistente IA usa confirmaciones en frontend para acciones sensibles; no implementa un `interrupt/resume` persistente del grafo.
- El identificador visible del ticket sigue derivándose del UUID; una mejora natural sería añadir un `ticket_number` secuencial.
- La búsqueda híbrida funciona sobre tickets; una extensión futura sería indexar también documentación PDF del cliente.

## Licencia

Proyecto desarrollado como reto técnico para **Orbidi**.
