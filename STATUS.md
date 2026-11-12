# STATUS
- [done] Sign-in: seed-personas reads DEMO_PASSWORD (or DEMO_PERSONA_PASSWORD) from env; never written to file/commit. Test added.
- [done] LICENSE placeholder with TODO.
- [next] Mark I/Q data "simulated" in the app; consent text stays demo-1.
- [blockers] Wave-3 worker reports (BRIDGE-1, PERF-1, F6-SLEEP, F4-SYMPTOM, FE-5) not yet received.
- [done] Badge "Synthetic data" -> "Simulated data" (AppShell + test). vitest NOT run here (no node_modules in main); merge_ready will run it.
- [next] Merge wave-3 reports as they arrive; FE-5 "/" mount in backend/main.py; verify vitest.
