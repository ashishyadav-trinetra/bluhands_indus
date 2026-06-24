# Run a real build (T-A07 live)

This runs the full autonomous pipeline on **your machine** and serves a preview
you can open in a browser:

```
seed products → prepare starter → apply brand → OpenHands customizes
→ npm build → serve preview on a port → Playwright self-test
```

The branding + build are deterministic, so you get a working, branded store even
if the AI step is skipped. The LLM only enhances on top.

## Prerequisites

1. **Medusa running** on `http://localhost:9000` with your admin user (the one you
   created in the Medusa admin) and the publishable key from
   Settings → Publishable API Keys.
2. **Node/npm** on PATH (you have v24).
3. **Python deps** for the agent:
   ```powershell
   cd C:\Users\Admin\Documents\Work\Bucket\bluhandsdk\SDK\bluhands-agent
   python -m venv .venv; .\.venv\Scripts\Activate.ps1
   pip install -e ".[agent]"      # installs openhands-sdk + playwright
   python -m playwright install chromium
   ```
4. **OpenRouter key** (for the AI customization step; optional — skipped if unset):
   ```powershell
   $env:OPENROUTER_API_KEY = "sk-or-..."
   ```

## Run it (one command)

```powershell
python scripts/build_live.py `
  --publishable-key pk_3234...your_key `
  --admin-email ashish.yadav@trinetralabs.ai `
  --admin-password "your-medusa-admin-password" `
  --input sample `
  --preview-port 4321
```

- `--input sample` uses two demo products. To use real onboarding data, export the
  wizard's data object to a JSON file and pass `--input path\to\store.json`
  (shape: `{ "business": {...}, "brand": {...}, "catalog": {"products": [...]} }`).
- On success it prints `Preview: http://127.0.0.1:4321` and **stays running** to keep
  the preview alive. Open that URL. Ctrl+C to stop.

## What each step does

| Step | Module | Notes |
|------|--------|-------|
| Seed products | `agent/medusa_seed.py` | Admin-auths, creates published products priced in your store currency, attaches the default sales channel. Best-effort. |
| Prepare workspace | `agent/pipeline.py` | Copies the golden starter, writes `.env.local` (Medusa URL + publishable key). |
| Apply brand | `agent/brand.py` | Writes your colors into `app/globals.css` tokens. Deterministic. |
| AI customize | `agent/runner.py` + OpenHands | Edits the starter to match brand/catalog. Failures are non-fatal. |
| Build + serve | `agent/preview.py` | `npm install` + `next build` + `next start -p PORT`. |
| Self-test | `agent/tools/playwright_verify.py` | Loads the preview, checks the page renders. Advisory. |

## Publishing later (BYO / buy a domain)

Preview lives on a local port. To publish:

- **BYO domain** — point the merchant's DNS at the host (records shown in the
  onboarding Domain step), then bind the preview behind your reverse proxy.
- **Buy a domain** — purchase + auto-DNS via the **entri.com** API (the onboarding
  Domain "buy" path is stubbed today; real entri wiring is **T-A04**).

## Notes / gotchas

- **Prices on the storefront.** Medusa v2 only returns calculated prices when a
  region/currency is in play. If the storefront shows products without prices, set
  the store region to your currency (INR) in the Medusa admin — that's a config
  step, not code. `medusa_seed` writes prices; region must accept that currency.
- **Price units.** `medusa_seed._to_amount` sends a decimal amount (e.g. `1299.0`).
  If your Medusa build expects minor units, adjust that one function.
- **Same-server previews at scale** = the managed sandbox service (**T-A08**), not
  this single-process server.
