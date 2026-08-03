# Atlas Web

The Atlas web application is the operator-facing shell for infrastructure context,
investigations, recommendations, and governed actions.

## Development

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

The development server runs on `http://localhost:5173` and proxies `/api` requests to
`http://127.0.0.1:8000` by default. Set `ATLAS_API_PROXY_TARGET` to use another API endpoint.

## Quality checks

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```
