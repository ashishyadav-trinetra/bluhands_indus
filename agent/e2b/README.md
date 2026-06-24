# BluHands E2B sandbox template

A Node-capable E2B template so each build runs in an isolated microVM with Node,
npm, and git already present (no per-build install of the toolchain).

## Build & push (one-time, and whenever the Dockerfile changes)

```bash
npm install -g @e2b/cli     # or: pip install e2b
export E2B_API_KEY=e2b_...   # your E2B key
cd agent/e2b
e2b template build --name bluhands-node
```

The CLI prints a `template_id` and writes it into `e2b.toml`. Commit that file so
every environment uses the same template.

## Wire it up

The agent already defaults to this template:

```
AGENT_SANDBOX_PROVIDER=e2b
AGENT_E2B_TEMPLATE=bluhands-node   # default; matches e2b.toml
E2B_API_KEY=e2b_...
```

## Speed: bake the starter's deps (optional)

The biggest remaining cold-start cost is `npm install` per build. To remove it,
uncomment the `COPY package.json … && npm ci` lines in `e2b.Dockerfile` (copy your
golden starter's lockfile into this dir first), then rebuild the template. Builds
then start with `node_modules` already present. Rebuild the template whenever the
starter's dependencies change.

## Verify

`python -m agent.scripts.e2b_smoke` (needs `E2B_API_KEY`) provisions a sandbox from
this template, checks `node --version`, runs a command, and tears it down.
