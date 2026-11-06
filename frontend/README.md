# Campus Customs Ops Desk (frontend)

React + Vite + TypeScript dashboard for the agent team.

1. Start the backend from `hw5/backend/` (hw5 venv active): `uvicorn main:app --reload --port 8000`
2. Here in `frontend/`: `npm install` once, then `npm run dev`. It opens http://localhost:5173.

The page calls the backend at `http://localhost:8000` (set `VITE_API_BASE` to change it). The design is explained in `../output/design.md`.
