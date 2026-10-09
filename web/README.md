# PETAdvice frontend

React 19, TypeScript, Vite and a PWA shell. See the [project README](../README.md) for backend setup, session authentication and production deployment requirements.

```sh
npm ci
npm run dev -- --host 127.0.0.1
npm test
npm run lint
npm run build
```

Development requests use `/api`, proxied to `http://127.0.0.1:8000`. Production hosting needs its own same-origin proxy or a same-site HTTPS API. The default uses HttpOnly cookies rather than browser-readable stored tokens.
