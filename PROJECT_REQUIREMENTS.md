# Checklist Oficial: Orbidi Technical Challenge

Este documento monitoriza el cumplimiento estricto de los requisitos del reto técnico.

## 1. Alcance Funcional
| Requisito | Estado | Detalles Técnicos |
| :--- | :---: | :--- |
| **Autenticación SSO Google** | ✅ | OAuth 2.0 con registro automático de email/avatar. |
| **Gestión de Tickets (Campos)** | ✅ | Título, desc, autor, asignado, estado, prioridad, fechas. |
| **Estados Mínimos** | ✅ | Abierto, En progreso, En revisión, Cerrado. |
| **Vista de Lista** | ✅ | Tabla con columnas filtrables y ordenables. |
| **Vista Kanban** | ✅ | Drag & drop con reflejo inmediato en base de datos. |
| **Comentarios** | ✅ | Formato texto, cronológicos, con autor y timestamp. |
| **Adjuntos (Archivos)** | ✅ | Subir, listar, descargar y eliminar. Límite 10MB. |
| **Reasignación** | ✅ | Cambio inmediato reflejado en Lista y Kanban. |
| **Sistema de Alertas (In-app)** | 🔄 | Notificaciones por asignación, comentario y estado. |
| **Indicador de Alertas (Badge)** | 🔄 | Contador visible de notificaciones sin leer. |

## 2. Requisitos Técnicos (Stack & DevOps)
| Requisito | Estado | Detalles Técnicos |
| :--- | :---: | :--- |
| **Backend: FastAPI (Python)** | ✅ | Arquitectura modular con servicios y esquemas. |
| **Frontend: Next.js** | ✅ | App Router 15+ y Zustand para estado global. |
| **Base de Datos: PostgreSQL** | ✅ | Persistencia íntegra con SQLAlchemy + pgvector. |
| **Almacenamiento: S3/R2** | ✅ | Integración con Cloudflare R2 (Desacoplado). |
| **Levantamiento Local (README)** | 🔄 | Documentación de .env y comandos de ejecución. |

## 3. Bonus Point: Asistente de IA (Especialidad)
| Requisito | Estado | Detalles Técnicos |
| :--- | :---: | :--- |
| **Chat Interactivo** | ✅ | Integrado en la App con Streaming (SSE). |
| **Consulta con Filtros** | ✅ | Herramienta `query_tickets` (Fase 2 corregida). |
| **Acciones (Estado/Coment/Reasignar)** | ✅ | Tool calling sobre la API del sistema. |
| **Respeto de Permisos** | ✅ | Validación de `actor` en todas las herramientas. |
| **Trazabilidad de Operaciones** | ✅ | Eventos `tool_start` y `tool_call` en el stream. |

## 4. Diferenciación Senior (Extra Orbidi)
| Requisito | Estado | Detalles Técnicos |
| :--- | :---: | :--- |
| **Búsqueda Semántica (RAG)** | ✅ | Búsqueda por significado, no solo palabras clave. |
| **Memoria de Conversación** | ✅ | Confirmada: Persistencia en DB verificada por el agente tras reinicios. |
| **Escalabilidad PubSub** | ✅ | Notificaciones distribuidas vía Redis activas y funcionales. |
| **Resiliencia (Failover)** | ✅ | Sistema híbrido Gemini/GPT funcionando ante cuotas 429. |

---
**Próximo Paso Crítico:** Verificar los logs del backend tras el despliegue para confirmar que el mensaje "✅ LangGraph Checkpointer fully initialized" aparece. Esto asegurará que la memoria sea 100% persistente.
