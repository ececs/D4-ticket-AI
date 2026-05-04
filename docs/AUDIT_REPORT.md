# INFORME DE AUDITORÍAS TÉCNICAS (D4-Ticket AI)

Este documento resume las auditorías realizadas durante la fase final de desarrollo para garantizar que el sistema cumple con estándares de calidad senior, seguridad y accesibilidad.

---

## 🛡️ AUDITORÍA 1: SEGURIDAD Y HARDENING
**Objetivo:** Eliminar vulnerabilidades comunes y asegurar la gestión de secretos.

### Hallazgos y Correcciones:
- **Gestión de Secretos:** Se verificó la ausencia de API Keys o credenciales "hardcoded". Se implementó validación en `backend/app/core/config.py` que bloquea el inicio si se usan claves débiles o por defecto.
- **Protección de Datos:** Configuración estricta de `.gitignore` para evitar la subida de entornos `.env` o bases de datos SQLite locales.
- **Seguridad en API:** Implementación de CORS restringido y validación de tokens JWT mediante cookies `HttpOnly` para mitigar ataques XSS.

---

## ♿ AUDITORÍA 2: ACCESIBILIDAD (WCAG 2.1)
**Objetivo:** Garantizar que la plataforma sea utilizable por personas con discapacidades y cumpla con los requisitos técnicos de la asignatura de DAW.

### Mejoras Implementadas:
- **Semántica HTML:** Vinculación técnica de todas las etiquetas `<label>` con sus respectivos inputs mediante `id` y `htmlFor`.
- **Navegación por Teclado:** Uso de primitivas de Radix UI para asegurar que modales y dropdowns sean totalmente navegables con el teclado.
- **Lectores de Pantalla (ARIA):** 
    - Añadidos atributos `aria-label` descriptivos a todos los botones que solo contienen iconos (Cerrar, Eliminar, Notificaciones).
    - Implementación de `aria-sort` en las tablas para indicar el estado de ordenación.
    - Notificaciones dinámicas sobre el número de mensajes no leídos.
- **Página de Login:** Adaptación completa del formulario de acceso demo para cumplimiento de accesibilidad.

---

## ✨ AUDITORÍA 3: UI/UX Y DISEÑO PROFESIONAL
**Objetivo:** Elevar la experiencia de usuario (UX) y la estética visual a un nivel premium.

### Mejoras Implementadas:
- **Confirmación de Acciones Críticas:** Sustitución de `confirm()` nativo por un componente `ConfirmDialog` personalizado con Radix UI, proporcionando una estética coherente y advertencias visuales claras.
- **Empty States (Estados Vacíos):** Implementación de feedback visual rico (iconografía y copys descriptivos) cuando no hay datos, evitando pantallas en blanco.
- **Streaming UX (AI):** Mejora de la retroalimentación visual durante el procesamiento de lenguaje natural del Co-pilot (animaciones de "Thinking").
- **Human-in-the-Loop Feedback:** Animación de los chips de herramientas ("Tool Actions") para que el usuario perciba claramente cuándo la IA realiza una acción en segundo plano.
- **Consistencia Visual:** Uso de una paleta de colores profesional (Slate/Blue/Indigo) y tipografía moderna para una sensación premium.

---

## 🔩 AUDITORÍA 4: RESILIENCIA Y ROBUSTEZ TÉCNICA
**Objetivo:** Verificar la capacidad del sistema para mantener la disponibilidad y la integridad de los datos ante fallos externos o errores de red.

### Hallazgos y Correcciones:

- **Failover de IA (Gemini → GPT-4o-mini):** El servicio de agente implementa un mecanismo de fallback real mediante `LangChain.with_fallbacks()`. Si el modelo primario (Gemini 2.0 Flash) falla por cuota o red, el sistema conmuta automáticamente a GPT-4o-mini (OpenAI) sin interrumpir la sesión del usuario. El fallback se activa únicamente si `OPENAI_API_KEY` está configurada, evitando errores silenciosos.

- **LLM Singleton:** Refactorización de `backend/app/ai/agent.py` para cachear la instancia del LLM a nivel de módulo (`_llm_singleton`). La construcción del cliente HTTP (importación de dependencias, inicialización de credenciales) se realiza una única vez al primer request y se reutiliza en todas las llamadas posteriores, reduciendo la latencia y la carga del servidor.

- **Rollback Optimista en Borrado:** Corrección de un bug real en `useTickets.ts`: el hook eliminaba el ticket del estado local antes de confirmar la respuesta de la API y no tenía mecanismo de recuperación. Ahora se captura un snapshot del estado previo; si la llamada falla, la lista y el contador se restauran automáticamente y el error se relanza para que el caller pueda notificar al usuario.

- **Integridad Referencial (CASCADE):** Verificado que los modelos de `Comment` y `Attachment` tienen configurado `ondelete="CASCADE"` a nivel de base de datos. La eliminación de un ticket limpia automáticamente todos sus registros dependientes, evitando huérfanos.

- **Tolerancia a Fallos en Scraping:** El servicio de análisis web utiliza `asyncio.to_thread` para ejecutar operaciones síncronas de extracción sin bloquear el event loop de FastAPI. Los errores de red y de contenido vacío están capturados y comunicados al usuario en tiempo real vía WebSocket.

- **Resiliencia del Frontend (Partial Refresh):** El hook `useTickets` implementa una estrategia de actualización parcial ante eventos WebSocket: si el evento identifica un ticket concreto, solo se re-fetcha ese recurso; en caso contrario, se hace un refetch completo como fallback. Esto minimiza la carga de red en escenarios de alta actividad.

---

## 🧪 COBERTURA DE TESTS
**Suite:** 156 tests — 0 fallos.

La batería de tests cubre el 100% de los endpoints del spec de Orbidi: autenticación, tickets (CRUD, filtros, búsqueda semántica), comentarios, adjuntos, usuarios y base de conocimiento. Los tests utilizan SQLite en memoria con `PRAGMA foreign_keys=ON` para validar cascadas, y mocks de almacenamiento y embeddings para garantizar ejecución sin dependencias externas.

---

## 🏁 CONCLUSIÓN
El proyecto **D4-Ticket AI** no solo es funcional, sino que ha sido sometido a cuatro auditorías técnicas que cubren seguridad, accesibilidad, experiencia de usuario y resiliencia. Cada hallazgo fue corregido en código, verificado con TypeScript y con la suite de tests, y commiteado de forma atómica. El sistema está preparado para un entorno de producción real.
