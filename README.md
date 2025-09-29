# CaamañoPOS Demo (BAC-style compliant)

Minimal POS to demo datáfono integration patterns expected by CR acquirers (e.g., BAC):
- POS never handles PAN/CVV/expiry.
- POS sends only `amount + reference` to the terminal.
- POS stores only `status, auth_code, masked_card (last4), terminal_ref`.

## Quick start (Docker Compose)
```bash
docker compose up --build
```
Open http://localhost:5173 
Backend API at http://localhost:8000/docs

## Dev (manual)
Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Frontend:
```bash
cd frontend
npm install
npm run dev
```

## PCI notes
- Keep the integration to **amount push** only.
- Do not log/store full PAN, CVV, or expiry.
- Receipts must show last 4 digits only.
- Annual SAQ C + possible quarterly ASV scans (your acquirer will instruct you).

## Next steps toward real terminals
- Replace the mock terminal with the bank's certified LAN/USB SDK once you enter their certification program.
- Add EOD summaries that match acquirer batch reporting.
- Implement reversals/voids, partial auth, tip adjustment flows required by the cert test plan.
