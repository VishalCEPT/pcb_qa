# Running PCB-QA Desktop in Docker

The app is a Tkinter desktop GUI, not a web server, so the container needs
somewhere to draw its window: an X11 display server. This works the same
way `ssh -X` does — the container doesn't need a GPU or a virtual desktop,
it just draws its window over the network/socket to a display server
running on your host machine.

The `Boards/` sample data and all Python dependencies (including `ngspice`
for the SPICE Simulation tab) are baked into the image, so once your host
is set up to receive the display, `docker compose up` is all you need.

## 1. One-time setup

```
cp .env.example .env
```
Fill in a real `GEMINI_API_KEY` if you want the Q&A/Benchmark tabs to work
(the Board and SPICE Simulation tabs work without one).

## 2. Set up an X server on your host (one-time, per OS)

### Linux
Most desktop Linux distributions already run an X11 (or Xwayland) server,
so there's usually nothing to install. Just allow the local Docker daemon
to connect to it:
```
xhost +local:docker
```
`docker-compose.yml` already targets this setup by default
(`DISPLAY=${DISPLAY}` + the `/tmp/.X11-unix` socket mount) — just make sure
your shell's `$DISPLAY` is exported (it almost always already is in a
graphical session; `echo $DISPLAY` should print something like `:0` /
`:1`).

### Windows
1. Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) (or any other
   X server for Windows, e.g. Xming/X410).
2. Launch it via its "XLaunch" shortcut, choosing **"Multiple windows"**,
   **Display number: 0**, and crucially tick **"Disable access control"**.
3. Edit `docker-compose.yml`:
   - Change `DISPLAY=${DISPLAY}` to `DISPLAY=host.docker.internal:0.0`.
   - Remove the `/tmp/.X11-unix:/tmp/.X11-unix:rw` volume line (Windows has
     no such socket; VcXsrv listens over TCP instead).

### macOS
1. Install [XQuartz](https://www.xquartz.org/) and log out/in (or reboot)
   once after installing.
2. Open XQuartz → Settings → Security → tick **"Allow connections from
   network clients"**, then restart XQuartz.
3. Run `xhost + 127.0.0.1` in a terminal.
4. Edit `docker-compose.yml`:
   - Change `DISPLAY=${DISPLAY}` to `DISPLAY=host.docker.internal:0`.
   - Remove the `/tmp/.X11-unix:/tmp/.X11-unix:rw` volume line.

## 3. Build and run

```
docker compose up --build
```
The "PCB-QA Desktop" window should appear on your host display within a
few seconds of the image finishing its build. Stop it with Ctrl+C, or
`docker compose down` from another terminal.

Plain `docker` (no Compose) works too, once your host's X server is set up
per step 2 — Linux example:
```
docker build -t pcb-qa .
docker run --rm -it \
  --env-file .env \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$(pwd)/Boards:/app/Boards" \
  -v "$(pwd)/outputs:/app/outputs" \
  pcb-qa
```

## 4. Running the test suite in the container instead

```
docker compose run --rm pcb-qa python -m pytest -q
```
This needs no display at all (pytest doesn't open any windows), so it works
regardless of the X11 setup above.

## 5. Optional: self-hosted observability dashboard (Langfuse)

Every Gemini call, datasheet retrieval, and benchmark run is traced via
[Langfuse](https://langfuse.com) (see `backend/observability.py`) when it's
configured — this is entirely optional; the app works identically without
it, just without traces. `docker-compose.langfuse.yml` brings up a full
self-hosted Langfuse instance (web UI + worker + Postgres + ClickHouse +
Redis + MinIO) alongside the app:

```
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up --build
```

As long as `GEMINI_API_KEY` is already set in `.env` as per step 1, this is
genuinely zero-extra-setup: `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` in
`.env` (defaulting to `pk-lf-pcbqa-local`/`sk-lf-pcbqa-local` if left unset)
are used both by the app *and* by `docker-compose.langfuse.yml` itself,
which auto-provisions a matching project with those exact keys on first
boot — no manual "create a project, copy its keys" step. Once it's up:

- Dashboard: <http://localhost:3000> (sign in with `LANGFUSE_INIT_USER_EMAIL`
  / `LANGFUSE_INIT_USER_PASSWORD` from `.env.example`'s defaults, or
  whatever you set them to).
- Every Q&A question, benchmark run, and the Gemini/retrieval calls inside
  them show up as traces, with accuracy/F1/RAG Recall@K/Precision@K/MRR
  attached as scores on each benchmark trace.

To run just the dashboard without the app container:
```
docker compose -f docker-compose.langfuse.yml up
```

The defaults in `.env.example` (`LANGFUSE_SALT`, `LANGFUSE_ENCRYPTION_KEY`,
`*_PASSWORD` values, etc.) are fine for local, single-user use only —
regenerate all of them (each is marked `# CHANGEME` in
`docker-compose.langfuse.yml`) before ever exposing this stack beyond
`localhost`.

## Troubleshooting

- **`_tkinter.TclError: couldn't connect to display` (or window never
  appears, container just exits):** your host's X server isn't reachable
  from the container. Re-check step 2 for your OS — this is almost always
  either a missing `xhost` allowlist entry (Linux/macOS) or VcXsrv not
  running / not started with "Disable access control" (Windows).
- **SPICE Simulation tab fails for a board other than `PortalHardware`:**
  that's a real bug, not expected — see
  [visual_manual_guide_user_testing.md](visual_manual_guide_user_testing.md)
  for which outcomes are expected per board.
- **Q&A/Benchmark tabs show "Request failed." / "Benchmark failed.":**
  check `GEMINI_API_KEY` is set correctly in `.env` and that `docker-compose.yml`
  (or your `--env-file .env` flag) actually picked it up — `docker compose
  run --rm pcb-qa env | grep GEMINI` should show it.
- **Langfuse web container logs `Applying clickhouse migrations failed`
  mentioning Zookeeper:** this means `CLICKHOUSE_CLUSTER_ENABLED` wasn't
  set to `false` somewhere in the stack's config — it's required even for
  this single-node setup, or Langfuse tries to create replicated tables
  that need a Zookeeper cluster this stack doesn't have.

