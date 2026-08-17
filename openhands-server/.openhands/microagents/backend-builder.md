---
name: backend-builder
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- backend
- API
- REST
- database
- auth
- server
- endpoint
- CRUD
- schema
- middleware
- routes
- express
- fastapi
- prisma
- supabase
---

# Backend Builder — Server & API Generation Rules

## Default Stack

- **Runtime:** Node.js with Express.js (TypeScript preferred)
- **Database:** SQLite (via better-sqlite3) for simple apps, Supabase/Postgres for production
- **ORM:** Prisma (if using Postgres) or Drizzle
- **Auth:** JWT tokens or Supabase Auth
- **Validation:** Zod for request validation
- **CORS:** Enable with `cors` package

## Project Structure

```
project/
├── src/
│   ├── app.ts              # Express app setup, middleware
│   ├── server.ts           # Server entry point (port $APP_PORT, host 0.0.0.0)
│   ├── routes/
│   │   ├── auth.ts         # Auth routes (login, register, me)
│   │   ├── users.ts        # User CRUD
│   │   └── [resource].ts   # Resource-specific routes
│   ├── middleware/
│   │   ├── auth.ts         # JWT verification middleware
│   │   ├── validate.ts     # Zod validation middleware
│   │   └── error.ts        # Global error handler
│   ├── db/
│   │   ├── index.ts        # Database connection
│   │   ├── schema.ts       # Table definitions
│   │   └── seed.ts         # Sample data
│   └── types/
│       └── index.ts        # Shared TypeScript types
├── package.json
├── tsconfig.json
└── .env
```

## Server Setup (CRITICAL)

```typescript
// src/server.ts
import app from './app';

const PORT = Number(process.env.APP_PORT);
const HOST = '0.0.0.0';  // MUST be 0.0.0.0 for Docker

app.listen(Number(PORT), HOST, () => {
  console.log(`Server is running on http://${HOST}:${PORT}`);
});
```

**ALWAYS:**
- Port $APP_PORT (the only proxied port)
- Host 0.0.0.0 (not localhost, not 127.0.0.1)
- Log the URL on startup

## API Response Format

```typescript
// Success
{ "data": { ... }, "message": "Resource created" }

// Error
{ "error": { "code": "NOT_FOUND", "message": "User not found" } }

// List with pagination
{ "data": [...], "meta": { "total": 100, "page": 1, "limit": 20 } }
```

## Auth Pattern

```typescript
// middleware/auth.ts
import jwt from 'jsonwebtoken';

export function authMiddleware(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: { message: 'No token provided' } });

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'dev-secret');
    req.user = decoded;
    next();
  } catch {
    res.status(401).json({ error: { message: 'Invalid token' } });
  }
}
```

## Database (SQLite for Simple Apps)

```typescript
// db/index.ts
import Database from 'better-sqlite3';
const db = new Database('database.sqlite');
db.pragma('journal_mode = WAL');
export default db;
```

## Error Handling

```typescript
// middleware/error.ts
export function errorHandler(err, req, res, next) {
  console.error(err.stack);
  res.status(err.status || 500).json({
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: err.message || 'Something went wrong',
    },
  });
}
```

## MANDATORY: Test Every Endpoint (NEVER skip this)

After building the backend, you MUST test every endpoint with curl:

```bash
# 1. Start the server
node src/server.ts &
sleep 2

# 2. Health check
curl -s http://localhost:$APP_PORT/api/health | head -c 200

# 3. Test POST (create)
curl -s -X POST http://localhost:$APP_PORT/api/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Item", "description": "Testing"}' | head -c 500

# 4. Test GET (list)
curl -s http://localhost:$APP_PORT/api/items | head -c 500

# 5. Test GET (single)
curl -s http://localhost:$APP_PORT/api/items/1 | head -c 500

# 6. Test PUT (update)
curl -s -X PUT http://localhost:$APP_PORT/api/items/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Item"}' | head -c 500

# 7. Test DELETE
curl -s -X DELETE http://localhost:$APP_PORT/api/items/1 | head -c 200

# 8. Test validation (should return 400, NOT 500)
curl -s -X POST http://localhost:$APP_PORT/api/items \
  -H "Content-Type: application/json" \
  -d '{}' | head -c 200

# 9. Test 404 (should return proper error, NOT crash)
curl -s http://localhost:$APP_PORT/api/items/99999 | head -c 200
```

If ANY endpoint returns a 500 error or crashes, FIX IT before proceeding.
If a validation test doesn't return a 400 with a clear error message, add proper validation.

## Common Backend Bugs to Avoid

1. **Unhandled async errors** — ALWAYS wrap async route handlers in try/catch
2. **Missing CORS for frontend** — Enable CORS BEFORE defining routes
3. **Database not initialized** — Create tables/seed data on first run
4. **Port already in use** — Check and kill existing processes: `lsof -ti :$APP_PORT | xargs kill -9 2>/dev/null`
5. **JSON body not parsed** — Add `app.use(express.json())` BEFORE routes
6. **No graceful error for missing fields** — Validate with Zod, return 400 not 500
7. **Returning raw database errors to client** — Wrap in generic error response
8. **Not closing database connections** — Use connection pooling or close on shutdown

## Quality Checklist

- [ ] Server listens on port $APP_PORT, host 0.0.0.0
- [ ] CORS enabled
- [ ] Error handling middleware registered
- [ ] Input validation on all POST/PUT routes
- [ ] Auth middleware on protected routes
- [ ] Consistent response format
- [ ] TypeScript types for all request/response shapes
- [ ] Database migrations/seeding if needed
- [ ] ALL endpoints tested with curl and returning correct responses
- [ ] Invalid input returns 400, not 500
- [ ] Missing resources return 404, not crash
- [ ] Server handles concurrent requests without crashing
