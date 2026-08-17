---
name: server-lifecycle
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- server
- start server
- run server
- dev server
- npm start
- npm run dev
- node server
- python manage
- flask run
- uvicorn
- express
- vite
- next dev
- port
- localhost
- http://
---

# Server Lifecycle Management — Start, Track, and Clean Up

## CRITICAL RULE: Every server you start MUST be cleaned up.

When you start a dev server, API server, or any background process, you are responsible
for stopping it before finishing the conversation. Orphaned servers leak ports and memory.

## Starting a Server

ALWAYS start servers with these practices:

```bash
# 1. Kill any existing process on the port FIRST
lsof -ti :$APP_PORT | xargs kill -9 2>/dev/null || true

# 2. Start the server in the background, saving the PID
npx vite --host 0.0.0.0 --port $APP_PORT &
SERVER_PID=$!
echo "Started server PID: $SERVER_PID"

# 3. Wait for it to be ready
sleep 3

# 4. Verify it's running
curl -s http://localhost:$APP_PORT > /dev/null && echo "Server is ready" || echo "Server failed to start"
```

## BEFORE Calling Finish

You MUST clean up ALL background processes:

```bash
# Kill any server you started
kill $SERVER_PID 2>/dev/null || true

# Kill any process on known dev ports (safety net)
for port in "$APP_PORT"; do
  lsof -ti :$port | xargs kill -9 2>/dev/null || true
done

# Kill any node/python dev servers you spawned
pkill -f "vite" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "tsx watch" 2>/dev/null || true
pkill -f "nodemon" 2>/dev/null || true
```

## Full-Stack Apps (Two Servers)

When running both frontend and backend:

```bash
# Kill old processes
lsof -ti :$APP_PORT | xargs kill -9 2>/dev/null || true
lsof -ti :3001 | xargs kill -9 2>/dev/null || true

# Start backend
cd server && node dist/server.js &
BACKEND_PID=$!
sleep 2

# Start frontend (with proxy to backend)
cd .. && npx vite --host 0.0.0.0 --port $APP_PORT &
FRONTEND_PID=$!
sleep 3

# ... do your work ...

# Clean up BOTH
kill $FRONTEND_PID $BACKEND_PID 2>/dev/null || true
```

## Port Conflict Resolution

If you get "EADDRINUSE" or "port already in use":

```bash
# Find what's using the port
lsof -i :$APP_PORT

# Kill it
lsof -ti :$APP_PORT | xargs kill -9

# Wait a moment for the port to be released
sleep 1
```

## Rules

1. **NEVER** start a server without first clearing the port
2. **ALWAYS** save the PID when backgrounding a process (`&` + `$!`)
3. **ALWAYS** kill your servers before calling Finish
4. **ALWAYS** bind to $APP_PORT — it is the only port the proxy can reach
5. **NEVER** start a server on port 3000 (that's the OpenHands server)
6. Need a backend too? Serve it on $APP_PORT as well (same origin, e.g. /api routes) — there is only ONE reachable port
