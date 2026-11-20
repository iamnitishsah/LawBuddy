# LawBuddy web client

React + Vite + Tailwind client for the LawBuddy API.

## Configuration

`frontend/.env` (see `.env.example`):

```bash
VITE_API_BASE_URL=http://localhost:8000   # the LawBuddy API
VITE_API_KEY=                             # only if the API sets LAWBUDDY_API_KEY
```

The API key can also be set in the app (header → API key); it is stored in the browser's localStorage.

## Running

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build in dist/
```
