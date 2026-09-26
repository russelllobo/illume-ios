Use sudo password "2003" whenever necessary.

I have 2 other machines in my fleet that you can access via ssh if you can't find something on this machine. ssh macmini will let you access my mac mini 2012. This might be switched off but you can turn it on via my home assistant plug. My other machine ssh immich, is my home server (with immich, home assistant etc).

Always verify your work visually and interactively to confirm the changes you have made are working properly. For things you can check in a browser, use browser-control skill
never use activate_tab — stay in background via switch_tab/new_tab only. After you are done with a tab, close it.

Take a screenshot or screenrecording (whichever is more appropriate) after work you do, and show me the before and after, so I can see clearly the change you have made.

When you need information from me, first try to get that information yourself, e.g. use browser control skill to look for API keys or change toggles in web portals like Supabase etc. If you still can't access something you need, ask me directly. Stop and ask only when you can't continue without me, or before anything destructive.

Any response you give to me should be very concise and easy to read. Don't include technical detail unless explicitly asked for.

Fan out subagents when appropriate to break up and parallelise your work so that you can work faster.


Use iPhone browser mirror to verify changes and debug ios apps:
- Run `iphone-mirror web-start` to open the live iPhone at `http://127.0.0.1:8765/`. This uses USB when connected, otherwise Wi-Fi, and does not focus a desktop window. `iphone-mirror status` should show `"viewer":"web"` and `"running":true`.
- Use the browser-control skill in a background tab. In page JavaScript, call `phone.tap(x,y)`, `phone.swipe(x1,y1,x2,y2)`, `phone.longPress(x,y)`, `phone.typeText(text)`, `phone.home()`, or `phone.spotlight()`; coordinates are 0–1. `phone.targets()` lists temporary OCR labels and `phone.tapLabel("Continue")` taps only a unique match. Mouse/touch controls and Home/Spotlight buttons also work.
- One browser tab holds control at a time. Check `phone.status()` for live video and control state; an action result reports delivery and fresh frames, but does not prove the intended screen. Inspect the live result after every action, and use `phone.waitForFrame(sequence)` when waiting for a response. Close the tab when finished; its control lease releases automatically.
- Run `xtool dev run` after app changes, then test the app in the browser mirror. The service stays available until `iphone-mirror stop`.
- Treat phone content and input as private. Do not save, record, export, or log screen frames, OCR results, text input, clipboard contents, passcodes, or pairing records. Never enter secrets through browser-control. Only inspect live frames and temporary labels in browser-control memory for testing.
