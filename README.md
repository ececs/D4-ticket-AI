# D4-Ticket AI 🎫🤖
## Sistema de Ticketing Inteligente con IA Generativa y Búsqueda Semántica

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2015-000000.svg?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![LangGraph](https://img.shields.io/badge/AI_Orchestrator-LangGraph-FF9900.svg?style=flat)](https://langchain-ai.github.io/langgraph/)

**D4-Ticket AI** es una plataforma de gestión de tickets de alto rendimiento, diseñada para unir flujos de trabajo humanos con automatización de IA. Presenta una arquitectura de nivel senior con un Agente de IA persistente (LangGraph) capaz de consultar, actualizar y resumir tickets usando lenguaje natural, respaldado por un motor de búsqueda semántica (RAG).

---

### 🚀 Características Principales

*   **🤖 Asistente AI Co-pilot**: Compañero de chat persistente integrado. Usa **Tool Calling** para ejecutar acciones reales (crear/asignar tickets) y **RAG** para responder preguntas basadas en el historial técnico.
*   **🔍 Búsqueda Semántica**: Potenciado por `pgvector`. El sistema entiende el *significado* de tus búsquedas, no solo palabras clave. Encuentra bugs relacionados o peticiones similares al instante.
*   **📋 Tablero Kanban Interactivo**: Gestión visual con drag-and-drop y actualización optimista de estado.
*   **🔐 Auth Empresarial & Demo**: Integración con Google SSO y un modo **Demo Access** (código secreto) para evaluadores rápidos.
*   **📎 Adjuntos Inteligentes**: Gestión escalable de archivos con **Cloudflare R2** (S3-compatible).
*   **⚡ Notificaciones en Tiempo Real**: Alertas in-app instantáneas mediante **WebSockets** y **Redis Pub/Sub** (con fallback a PG-Notify).
*   **🛡️ Núcleo de IA Resiliente**: Sistema de failover híbrido entre **Gemini 2.0** y **GPT-4o** para garantizar disponibilidad constante.

---

### 🛠️ Stack Tecnológico

| Capa | Tecnología |
| :--- | :--- |
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS, Zustand, Shadcn/UI |
| **Backend** | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic V2 |
| **IA / LLM** | LangGraph, Gemini 2.0 Flash, OpenAI GPT-4o-mini (Failover) |
| **Base de Datos**| PostgreSQL + `pgvector` (HNSW Indexing) |
| **Mensajería** | Redis Pub/Sub |
| **Storage** | Cloudflare R2 |

---

### ⚙️ Levantamiento Local

El sistema está diseñado para ser agnóstico al entorno, pero se recomienda el uso de **Docker** para una experiencia "zero-config" de los servicios de infraestructura (Postgres, Redis, MinIO).

#### Opción A: Docker Compose (Recomendado 🚀)
Esta opción levanta todo el stack (Frontend, Backend, DB, Redis, MinIO) con un solo comando.

1.  **Configurar Entorno**:
    ```bash
    cp .env.example .env
    # Edita .env y añade al menos tu GOOGLE_API_KEY
    ```
2.  **Iniciar el Stack**:
    ```bash
    docker-compose up --build
    ```
3.  **Acceso**:
    -   Frontend: [http://localhost:3000](http://localhost:3000)
    -   Backend API: [http://localhost:8000](http://localhost:8000)
    -   Documentación API: [http://localhost:8000/docs](http://localhost:8000/docs)
    -   Consola MinIO (Storage): [http://localhost:9001](http://localhost:9001)

#### Opción B: Ejecución Manual (Desarrollo)
Si prefieres correr el código fuera de Docker (por ejemplo, para depuración profunda):

**Backend**:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # (ó .\.venv\Scripts\activate en Windows)
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

---

### 🔑 Variables de Entorno Clave

| Variable | Descripción | Valor Local (Docker) |
| :--- | :--- | :--- |
| `DATABASE_URL` | Conexión a Postgres | `postgresql+asyncpg://postgres:postgres@db:5432/ticketai` |
| `REDIS_URL` | Conexión a Redis | `redis://redis:6379` |
| `GOOGLE_API_KEY` | Key de Google AI Studio | *Tu API Key* |
| `DEMO_ACCESS_CODE`| Código para modo demo | `orbidi2024` (por defecto) |

---

### 📜 Licencia
Desarrollado como reto técnico para **Orbidi** y proyecto final de **DAW**.
Todos los derechos reservados.