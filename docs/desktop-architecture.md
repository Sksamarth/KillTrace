# Windows desktop architecture

The Windows desktop prompt supersedes the earlier web-only delivery target.
Existing web, ingestion and source-contract functionality is preserved.
Identifier: `org.killchainai.desktop`; product: KillChain AI; target: Windows x64.

## Desktop Phase 1 scope

The React frontend now has a Tauri 2 shell in frontend/src-tauri. It uses a
1280×850 resizable native window with a 960×640 minimum, product metadata and a
project-owned shield/K icon generated from the checked-in SVG. The shell grants
no filesystem, shell execution or remote IPC permissions. Development uses a
loopback Vite server; the original web workflow remains available.

This shell is not the final standalone product. Production backend startup,
token-authenticated communication, native file grants and PyInstaller packaging
must be completed before a distributable installer is enabled. Bundle generation
is deliberately disabled in this phase rather than publishing a frontend-only
installer that cannot perform investigations. NSIS and WebView2 bootstrapper
configuration establish the intended Windows packaging target.

## Development

Prerequisites: Windows x64, Microsoft C++ tools/Windows SDK, Rust MSVC toolchain,
Node and WebView2. On the development machine, MSVC and WebView2 were already
available; the minimal Rust toolchain was installed for the current user.

From frontend/, with the ordinary local backend running on port 8000:

```powershell
npm ci
npm run desktop:dev
```

For the isolated Docker verification backend instead, set
`$env:KILLCHAIN_DEV_API='http://127.0.0.1:18000'` before running desktop:dev.
This override affects the development Vite proxy only. It is not a production
backend address and is not embedded into the production frontend.

If an existing terminal predates Rust installation, reopen it or prepend
`$env:USERPROFILE\.cargo\bin` to its PATH. This machine also has an older broken
npm shim; `& 'C:\Program Files\nodejs\npm.cmd' run desktop:dev` uses the working
Node installation. Cargo compilation uses one job on the 8 GB laptop.

`npm run desktop:build` builds the native executable without an installer. It
does not establish standalone backend readiness. `npm run build` remains the
ordinary TypeScript/Vite production build; `npm run dev` remains web development.

## Backend lifecycle contract for the packaged phase

1. Tauri owns one backend process per application instance and an OS job/process
   group that also contains its processing worker children. Duplicate instances
   must not open the same writable database concurrently.
2. Allocate a loopback endpoint safely. Generate a fresh random session token;
   pass secrets through an inherited pipe, not command-line arguments or logs.
   The backend's readiness record identifies its bound port and launch identity.
3. Keep port/token in Rust-managed state. A narrowly scoped Tauri command forwards
   allowlisted API calls to that exact backend and attaches its token. The webview
   cannot select arbitrary URLs, start arbitrary programs or read arbitrary files.
   Readiness requires successful authenticated identity verification, not an open
   port alone. Do not add permissive CORS.
4. Native file selection creates explicit path grants. Pass opaque references to
   ingestion; do not loosen existing traversal checks into arbitrary path access.
   No source copying or external transmission occurs automatically.
5. Store persistent databases, Parquet, configuration, logs and temporary files in
   separate directories under LocalAppData/KillChainAI. Export destinations are
   chosen by the user. Installation/upgrade/uninstallation preserves user evidence.
6. On close, request cooperative worker checkpoint/cancellation, authenticated
   backend shutdown, and a bounded wait; use the owned process group only as a
   fallback. Failures surface in the native window with local diagnostic logs.
7. Package and independently test the Python executable before enabling it as a
   Tauri sidecar. Its Python module dispatch must support frozen worker launches;
   the current development `python -m` worker path is not proof of frozen support.

These lifecycle requirements are the implementation contract for later phases,
not a claim that the sidecar is already packaged. Core offline analysis must work
without Gemini and without Docker in the installed desktop product.

## Phase gates

- Original foundation verification: completed and pushed as 5bd4e32.
- Explicit FireX contract: c9c62df; ingestion integration: 107c59e.
- Desktop Phase 1: shell implemented; locked Cargo check, native compilation,
  React rendering and live API connection verified on Windows 11. Help/About and
  close/reopen UI checks remain pending because the user stopped computer control
  with Escape during Help-menu inspection. The phase is not marked fully complete.
- Desktop Phase 2: retain and audit the already tested source contracts.
- Desktop Phase 3: add native file grants without weakening existing ingestion.
- Desktop Phases 4–6: finish detection/correlation/context/optional AI contracts.
- Desktop Phase 7: packaged sidecar, secure IPC, installer and installation tests.

No installer, clean-machine test, Windows 10 runtime test or code signing is
claimed at the shell stage. Installer and packaged-runtime results must be
recorded independently of successful development builds.

Validation at this checkpoint: 109 backend tests passed; TypeScript/Vite build
passed; the frontend security test passed (remote and credential-bearing
development proxy URLs are rejected); locked Cargo check passed; native dev build
completed and opened killchain-ai.exe with the expected title and connected React
interface. Backend and same-origin desktop proxy health checks also passed.
