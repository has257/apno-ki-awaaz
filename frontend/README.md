# Apno Ki Awaaz Web

## Configure

Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the FastAPI
origin. The default is `http://127.0.0.1:8000`. Frontend environment values are
public build-time configuration; do not put credentials or signing secrets in
them.

The Vite development server uses `http://localhost:5173`, which matches the
backend's existing local CORS allow-origin.

## Run

From `frontend/`:

```sh
npm install
npm run dev
```

Run checks with:

```sh
npm test
npm run build
```

Sign-in tokens are kept in `sessionStorage` and cleared on expiration or an API
401. Audio playback is fetched with the bearer token and played from a temporary
blob URL; generated file paths are not exposed to the browser.