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

### ⚙️ Configuración Local

#### Requisitos Previos
*   Docker & Docker Compose
*   Python 3.12+ (si se corre manual)
*   Node.js 20+

#### Variables de Entorno (.env)
Crea un archivo `.env` en la raíz (o dentro de `/backend` y `/frontend`) con:

```env
# Backend
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/railway
SECRET_KEY=tu_secreto_super_seguro
GOOGLE_API_KEY=tu_key_de_google_ai_studio
OPENAI_API_KEY=tu_key_de_openai (opcional, para failover)
DEMO_ACCESS_CODE=orbidi2024  # Código para el login de evaluador

# Storage (Cloudflare R2)
R2_BUCKET_NAME=tu_bucket
R2_ENDPOINT_URL=https://tu_id.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=tu_key
R2_SECRET_ACCESS_KEY=tu_secret

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Inicio Rápido (Docker)
```bash
docker-compose up --build
```
*   Frontend: `http://localhost:3000`
*   Backend API: `http://localhost:8000`
*   Acceso Demo: Usa el botón "Demo Access" con el código configurado en tu `.env`.

---

### 🏗️ Arquitectura Senior
El sistema implementa patrones de diseño avanzados:
*   **Service Layer Pattern**: Lógica de negocio desacoplada de los controladores API.
*   **Repository Pattern**: Abstracción de acceso a datos para facilitar testing.
*   **State Machine (LangGraph)**: Ciclos de razonamiento de la IA con memoria persistente.
*   **Real-time Transport**: Detección automática de transporte (Redis -> Postgres) para eventos.

---

### 📜 Licencia
Desarrollado como reto técnico para **Orbidi** y proyecto final de **DAW**.
Todos los derechos reservados.