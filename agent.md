Use sudo password "2003" whenever necessary
When using browser-use, never call activate_tab — stay in background via switch_tab/new_tab only.
Any response you give to me should be very concise and easy to read. Don't include technical detail unless explicitally asked for.
Use subagents to parallelise your work, giving you the ability to get more work done faster.

Run `npx expo start` and use the dev build on my iPhone. IAP needs a dev client, not Expo Go.

iOS testing - iPhone 17 Pro (Mac mini Intel):
- Live view: http://localhost:18831 (~1 fps). Ignore Device panel video - it never connects on Intel.
- Control with `agent-device`: `open`, `press/click/fill --settle`, `snapshot`, `screenshot`.
- Booted sim: iPhone 17 Pro `6F00A3B1-51F0-48A6-933B-43FFE0BF7280`
- If stream freezes: `ssh -f -N -L 18831:127.0.0.1:18831 macmini`
- Stop streamer on mini: `ssh macmini 'pkill -f sim-stream.py'`
