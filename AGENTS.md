# Project instructions

- All application-owned text must be English: navigation, labels, tooltips, validation, errors, notifications, logs, installer copy, and default content. Never select the UI language from the operating system or browser. Preserve user-entered names and data as entered.
- Keep frontend copy in `frontend/src/locales/en.ts`; use the explicit `en-US` locale for number and date formatting. HTML language is `en`.
- Use `phase-plan.md` for execution order, `step.md` for detailed feature tasks, and `Overall-plan.md` for product vision. See `docs/plan-comparison.md` for resolved differences.
- Finish packaging checkpoints before moving to later product features. Phase 0 is a development bootstrap, not a standalone release.
- Target Windows x64. Keep runtime data under `%LOCALAPPDATA%\VisionStudio`, never in the installation directory or source tree.
- Keep heavy vision dependencies out of the bootstrap. Introduce them at Phase 15, with training in a separate worker process.
- Verify relevant changes with `npm run build`, `npm run test:backend`, `npm run test:e2e`, and desktop checks when Rust code changes. Do not claim native or clean-machine checks passed without executing them.
