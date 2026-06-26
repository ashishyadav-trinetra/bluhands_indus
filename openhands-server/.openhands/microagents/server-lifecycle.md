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
lsof -ti :8011 | xargs kill -9 2>/dev/null || true

# 2. Start the server in the background, saving the PID
npx vite --host 0.0.0.0 --port 8011 &
SERVER_PID=$!
echo "Started server PID: $SERVER_PID"

# 3. Wait for it to be ready
sleep 3

# 4. Verify it's running
curl -s http://localhost:8011 > /dev/null && echo "Server is ready" || echo "Server failed to start"
```

## BEFORE Calling Finish

You MUST clean up ALL background processes:

```bash
# Kill any server you started
kill $SERVER_PID 2>/dev/null || true

# Kill any process on known dev ports (safety net)
for port in 8011 3000 3001 5173 5174 8080 8000 4000; do
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
lsof -ti :8011 | xargs kill -9 2>/dev/null || true
lsof -ti :3001 | xargs kill -9 2>/dev/null || true

# Start backend
cd server && node dist/server.js &
BACKEND_PID=$!
sleep 2

# Start frontend (with proxy to backend)
cd .. && npx vite --host 0.0.0.0 --port 8011 &
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
lsof -i :8011

# Kill it
lsof -ti :8011 | xargs kill -9

# Wait a moment for the port to be released
sleep 1
```

## Rules

1. **NEVER** start a server without first clearing the port
2. **ALWAYS** save the PID when backgrounding a process (`&` + `$!`)
3. **ALWAYS** kill your servers before calling Finish
4. **PREFER** port 8011 for all dev servers (the exposed sandbox port)
5. **NEVER** start a server on port 3000 (that's the OpenHands server)
6. If you need multiple ports, use 8011 (frontend) and 3001 (backend API)
