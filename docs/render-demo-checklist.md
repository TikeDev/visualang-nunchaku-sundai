# Render Demo Checklist

## Pre-Demo Checklist

- Rotate the exposed key in `backend/.env` and set fresh values only in Render environment variables.
- Use the paid backend from the start. Do not rely on a free backend plus warmup hacks.
- Keep the backend at a single instance for the demo so `/tmp` files and in-memory export jobs keep working.
- Limit live testing to one operator at a time right before the demo. Avoid parallel sessions.
- Pre-pick 2-3 known-good YouTube URLs with reliable transcripts and moderate length. Avoid long videos.
- Prefer YouTube input during the demo unless audio upload is specifically required. Uploads add more variability.
- Keep demo clips short. Fewer transcript concepts means less time spent in serial image generation.
- If possible, reduce the number of generated concepts for demo runs. That directly cuts latency.
- Do one full end-to-end smoke test on the deployed stack: transcript, concepts, image stream, export, and final downloads.
- Do a second smoke test immediately after the first to confirm no stale `/tmp` or job-state issues appear.
- Watch Render logs during the smoke test so you know what failure signatures look like before demo day.
- Have one pre-seeded fallback demo path ready using the existing `backend/demo` fixture route in case live generation stalls.
- Keep one exported video artifact ready to show if export is slow in real time.
- Avoid kicking off a second export while one is already running on the same instance.
- Lock the frontend to the deployed backend URL and tighten CORS to that origin before the demo.
- Confirm the backend health endpoint responds quickly after each deploy.
- Disable or avoid any nonessential background experimentation on the same Render service during the demo window.
- Keep a rollback point: the last known-good deploy should stay available in Render in case the final deploy regresses.

## Highest-Value Risk Reducers

- Short demo input
- One user at a time
- Paid backend
- Pre-seeded fallback
- Fresh deploy smoke test right before showtime
