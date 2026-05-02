"""
Seed script — crea datos de prueba realistas en producción.

Uso:
  1. En el navegador, abre la consola (F12) y ejecuta:
       document.cookie.match(/access_token=([^;]+)/)?.[1]
  2. Copia el token y ejecuta:
       TOKEN=<pega aquí> python3 seed_data.py
"""

import os
import sys
import json
import urllib.request
import urllib.parse

API = "https://d4-ticket-ai-production.up.railway.app/api/v1"
TOKEN = os.environ.get("TOKEN", "")

if not TOKEN:
    print("❌  Falta el token. Ejecuta:")
    print('   TOKEN=<tu_token> python3 seed_data.py')
    print()
    print("   Para obtener el token, abre la consola del navegador y ejecuta:")
    print("   document.cookie.match(/access_token=([^;]+)/)?.[1]")
    sys.exit(1)


def request(method, path, body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ⚠️  {method} {path} → {e.code}: {body[:200]}")
        return None


def get(path):     return request("GET", path)
def post(path, b): return request("POST", path, b)
def patch(path, b): return request("PATCH", path, b)


# ── 1. Obtener usuarios existentes ─────────────────────────────────────────
print("\n🔍  Buscando usuarios...")
users = get("/users") or []
if not users:
    print("❌  No hay usuarios. Inicia sesión con Google primero.")
    sys.exit(1)

me = users[0]  # Tú eres el primer usuario
other = users[1] if len(users) > 1 else me  # Segundo usuario (o tú mismo)

print(f"   👤  Tú: {me['name']} ({me['email']})")
if len(users) > 1:
    print(f"   👤  Otro usuario: {other['name']} ({other['email']})")
else:
    print("   ℹ️   Solo hay un usuario — los tickets se asignarán a ti mismo")

my_id    = me["id"]
other_id = other["id"]

# ── 2. Crear tickets ────────────────────────────────────────────────────────
print("\n🎫  Creando tickets...")

tickets_data = [
    # --- OPEN ---
    {
        "title": "Rediseño de la página de inicio del portal de clientes",
        "description": (
            "El portal actual tiene una tasa de rebote del 68%. "
            "Necesitamos modernizar el diseño, mejorar la jerarquía visual "
            "y añadir CTAs más claros. Incluir versión mobile-first.\n\n"
            "**Criterios de aceptación:**\n"
            "- Nuevo hero section con video de fondo\n"
            "- Sección de métricas animadas\n"
            "- Testimonios con carrusel\n"
            "- Footer con mapa del sitio completo"
        ),
        "status": "open",
        "priority": "high",
        "assignee_id": my_id,
    },
    {
        "title": "Integrar Stripe para pagos recurrentes",
        "description": (
            "Implementar Stripe Billing para suscripciones mensuales y anuales. "
            "El flujo debe soportar upgrades, downgrades y cancelaciones con "
            "período de gracia de 7 días.\n\n"
            "**Stack:** FastAPI + Stripe SDK Python + webhooks\n"
            "**Documentación:** https://stripe.com/docs/billing"
        ),
        "status": "open",
        "priority": "critical",
        "assignee_id": other_id,
    },
    {
        "title": "Configurar alertas de error en Sentry",
        "description": (
            "Integrar Sentry en el backend y frontend. "
            "Configurar alertas por email cuando el error rate supere el 1% "
            "o cuando haya errores nuevos de tipo crítico."
        ),
        "status": "open",
        "priority": "medium",
        "assignee_id": None,
    },
    # --- IN PROGRESS ---
    {
        "title": "Migración de base de datos a PostgreSQL 16",
        "description": (
            "Migrar la instancia actual de PostgreSQL 14 a PostgreSQL 16. "
            "Beneficios: mejoras de rendimiento en queries complejas (~15%), "
            "nuevas funciones de JSON y soporte mejorado para particionado.\n\n"
            "**Plan de migración:**\n"
            "1. Snapshot de la DB actual\n"
            "2. Levantar nueva instancia PG 16 en Railway\n"
            "3. pg_dump + pg_restore\n"
            "4. Verificar integridad con checksums\n"
            "5. Actualizar DATABASE_URL y reiniciar"
        ),
        "status": "in_progress",
        "priority": "high",
        "assignee_id": my_id,
    },
    {
        "title": "Añadir tests E2E con Playwright",
        "description": (
            "Cubrir los flujos críticos de usuario con tests end-to-end:\n"
            "- Login con Google OAuth\n"
            "- Crear y editar un ticket\n"
            "- Drag & drop en kanban\n"
            "- Subir adjunto\n"
            "- Recibir notificación en tiempo real\n\n"
            "Integrar en el pipeline de CI/CD de GitHub Actions."
        ),
        "status": "in_progress",
        "priority": "medium",
        "assignee_id": other_id,
    },
    {
        "title": "Optimizar queries N+1 en el endpoint de tickets",
        "description": (
            "El endpoint GET /tickets está haciendo queries individuales para "
            "cargar author y assignee de cada ticket. Con 100+ tickets la "
            "latencia sube a >2s.\n\n"
            "**Fix:** Usar `selectinload` o `joinedload` de SQLAlchemy para "
            "cargar las relaciones en una sola query."
        ),
        "status": "in_progress",
        "priority": "high",
        "assignee_id": my_id,
    },
    # --- IN REVIEW ---
    {
        "title": "Implementar rate limiting en endpoints públicos",
        "description": (
            "Añadir slowapi (wrapper de limits para FastAPI) para limitar:\n"
            "- POST /auth/google: 10 req/min por IP\n"
            "- POST /ai/chat: 20 req/min por usuario\n"
            "- GET /tickets: 100 req/min por usuario\n\n"
            "Retornar 429 Too Many Requests con header Retry-After."
        ),
        "status": "in_review",
        "priority": "medium",
        "assignee_id": other_id,
    },
    {
        "title": "Dark mode en el dashboard",
        "description": (
            "Implementar tema oscuro usando Tailwind CSS dark: prefix y "
            "next-themes para persistir la preferencia del usuario.\n\n"
            "Respetar prefers-color-scheme del sistema operativo como valor "
            "por defecto. Añadir toggle en el header."
        ),
        "status": "in_review",
        "priority": "low",
        "assignee_id": my_id,
    },
    # --- CLOSED ---
    {
        "title": "Setup inicial del proyecto — Docker Compose + CI/CD",
        "description": (
            "Configurar el entorno de desarrollo completo:\n"
            "- Docker Compose con FastAPI, PostgreSQL, MinIO\n"
            "- GitHub Actions para lint + tests en cada PR\n"
            "- Pre-commit hooks (ruff, mypy, prettier)\n"
            "- Variables de entorno documentadas en .env.example"
        ),
        "status": "closed",
        "priority": "high",
        "assignee_id": my_id,
    },
    {
        "title": "Autenticación Google OAuth2 — flujo stateless",
        "description": (
            "Implementar login con Google sin estado de servidor:\n"
            "- Authlib reemplazado por httpx directo (sin SessionMiddleware)\n"
            "- JWT firmado con HS256, expiración configurable\n"
            "- Cookie no-httpOnly en dominio Vercel para cross-domain auth\n"
            "- Middleware Next.js para proteger rutas privadas"
        ),
        "status": "closed",
        "priority": "critical",
        "assignee_id": my_id,
    },
    {
        "title": "Notificaciones en tiempo real con WebSocket + PG NOTIFY",
        "description": (
            "Sistema de notificaciones push sin polling:\n"
            "- FastAPI WebSocket endpoint con autenticación por JWT\n"
            "- PostgreSQL LISTEN/NOTIFY para eventos de DB\n"
            "- Keepalive ping cada 30s para evitar timeout de Railway\n"
            "- Reconexión automática en el cliente con backoff"
        ),
        "status": "closed",
        "priority": "high",
        "assignee_id": other_id,
    },
    {
        "title": "Corregir bug: cookie httpOnly bloquea logout",
        "description": (
            "El interceptor de axios no podía borrar una cookie httpOnly, "
            "causando un bucle redirect infinito al recibir un 401.\n\n"
            "**Fix:** Añadir ruta Next.js /api/auth/clear que borra la "
            "cookie server-side y redirige a /login."
        ),
        "status": "closed",
        "priority": "critical",
        "assignee_id": my_id,
    },
]

created_tickets = []
for td in tickets_data:
    t = post("/tickets", td)
    if t:
        created_tickets.append(t)
        print(f"   ✅  [{t['status'].upper():12}] {t['title'][:55]}")
    else:
        print(f"   ❌  Falló: {td['title'][:55]}")

# ── 3. Añadir comentarios ───────────────────────────────────────────────────
print(f"\n💬  Añadiendo comentarios a {min(6, len(created_tickets))} tickets...")

comments_map = {
    "Rediseño de la página": [
        "He revisado los analytics de los últimos 6 meses. El 70% del tráfico mobile rebota en menos de 10 segundos. Necesitamos priorizar la versión móvil.",
        "Propongo usar Framer Motion para las animaciones del hero. El bundle size es manejable (~50KB gzipped) y el DX es excelente.",
        "@Equipo: ¿alguien puede compartir los wireframes del diseño anterior para evitar repetir errores?",
    ],
    "Integrar Stripe": [
        "He creado el entorno de test en Stripe. Las credenciales están en el vault de 1Password bajo 'Stripe Test Keys'.",
        "Cuidado con los webhooks: hay que manejar los eventos de forma idempotente. Stripe puede enviar el mismo evento varias veces.",
        "¿Confirmamos que vamos a soportar SEPA Direct Debit además de tarjeta? Cambia bastante la implementación.",
    ],
    "Migración de base de datos": [
        "He completado el snapshot de la DB actual. Tamaño: 2.3 GB. El dump tardó 8 minutos.",
        "ATENCIÓN: La nueva instancia PG16 no admite la extensión pg_trgm en la versión que teníamos. Hay que actualizar las migraciones.",
        "Primera prueba de migración completada en staging. Tiempo total: 22 minutos. Ningún dato corrupto detectado.",
    ],
    "Optimizar queries": [
        "Confirmado el N+1. Con SQLAlchemy async, `selectinload` es la opción correcta — `joinedload` no funciona bien con AsyncSession.",
        "Después del fix: p95 del endpoint bajó de 2.1s a 187ms con 150 tickets. Brutal.",
    ],
    "Setup inicial": [
        "Docker Compose funcionando. `docker compose up --build` levanta todos los servicios en ~90 segundos en M2.",
        "CI/CD configurado. Los tests corren en ~45 segundos gracias al caché de uv en GitHub Actions.",
        "Merge a main. ¡Base del proyecto lista! 🚀",
    ],
    "Autenticación Google": [
        "El flujo stateless funciona perfectamente. Eliminamos ~300 líneas de código de sesión de servidor.",
        "Probado en Safari, Firefox y Chrome. El SameSite=Lax de la cookie funciona correctamente.",
    ],
}

for ticket in created_tickets:
    for key, comment_list in comments_map.items():
        if key in ticket["title"]:
            for comment_text in comment_list:
                c = post(f"/tickets/{ticket['id']}/comments", {"content": comment_text})
                if c:
                    print(f"   💬  Comentario en '{ticket['title'][:40]}...'")
            break

# ── 4. Resumen final ────────────────────────────────────────────────────────
summary = {"open": 0, "in_progress": 0, "in_review": 0, "closed": 0}
for t in created_tickets:
    summary[t["status"]] = summary.get(t["status"], 0) + 1

print(f"""
✨  ¡Datos de prueba creados!
   📋  Tickets: {len(created_tickets)}/{len(tickets_data)}
       Open:        {summary.get('open', 0)}
       In Progress: {summary.get('in_progress', 0)}
       In Review:   {summary.get('in_review', 0)}
       Closed:      {summary.get('closed', 0)}
   💬  Comentarios en 5 tickets

   🌐  https://frontend-eight-chi-54.vercel.app/board
""")
