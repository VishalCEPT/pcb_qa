# PCB-QA Desktop App — Visual Manual Testing Guide

This guide is written for a regular person, not a programmer. It walks you
through starting the app and clicking through every screen, step by step, so
you can confirm with your own eyes that everything works. No coding knowledge
required — just follow the steps in order.

There are **8 real circuit boards** already loaded in the `Boards` folder that
you can test with:

1. `stack-chan` (simplest board — start here, everything works end-to-end)
2. `AcornRobotElectronics`
3. `CF-Chef`
4. `HadesFCS`
5. `Meshinger`
6. `OPNhydro-r2`
7. `PortalHardware`
8. `fan_controller`

---

## Part 0 — One-time setup (do this once)

1. **Open a terminal in the project folder.**
   The project lives at `CODE_BASE`. Make sure your terminal is sitting in
   that folder before continuing.

2. **Check there is a `.env` file.**
   This file holds your Gemini API key (needed only for the Q&A and
   Benchmark tabs — the Board and SPICE tabs work without it). If you don't
   have one yet, create a file named `.env` in the project folder with this
   inside:
   ```
   GEMINI_API_KEY=your-key-here
   ```
   Never share this file or paste the key into a chat — treat it like a
   password.

3. **Start the app** by running:
   ```
   python main.py
   ```
   A window titled **"PCB-QA Desktop"** should appear within a few seconds.
   If nothing opens, or you see an error in the terminal, stop here and
   report the exact error text — that's a real bug, not something to work
   around.

---

## Part 1 — What you should see when the app opens

- A window roughly 1000×700 pixels in size.
- Near the top: a **"Board:"** dropdown (already showing `stack-chan`) and a
  **"Reload .env / boards"** button on the right.
- Below that: four tabs in a row — **Board**, **SPICE Simulation**, **Q&A**,
  **Benchmark**.
- At the very bottom: a thin status bar that says **"Ready"**.

✅ **Check:** Click the **Board** dropdown — all 8 board names listed above
should appear in the list. If any are missing, that's a bug.

---

## Part 2 — Testing flow (repeat this flow for each board)

The idea is simple: for **every one of the 8 boards**, pick it from the
dropdown, then click through all 4 tabs in order and confirm what you see
matches the "expected result" for each step. Start with `stack-chan` since
it's the one board guaranteed to fully succeed on every tab; then repeat the
same flow for the other 7 so you've genuinely exercised the whole app against
all your real boards.

### Step 1 — Pick a board
- Open the **Board:** dropdown at the top and select a board (e.g.
  `stack-chan`).
- **While it's selected, the dropdown and the "Reload .env / boards" button
  should be clickable (not greyed out)** — they only grey out while
  something is actively running (see Step 2).

### Step 2 — Board tab
- Click the **Board** tab if it isn't already selected.
- Click **"Load board"**.
- **Expected while it's working:** the button greys out, a progress bar
  appears underneath the status line, and the bottom status bar changes to
  `Working: Loading '<board name>'...`. The Board dropdown should also grey
  out at this moment — that's intentional, so you can't switch boards
  mid-operation.
- **Expected when it finishes (a few seconds):**
  - The status line turns **green** and reads `Loaded '<board name>'.`
  - The progress bar disappears.
  - The bottom status bar goes back to `Ready`.
  - The big text box below shows a summary: file paths for the netlist,
    SPICE file, schematic PDF, questions file, how many datasheets were
    found, and counts of components/nets/subcircuits.
- ✅ **Check:** text box is not empty, status line is green, no popup error
  window appeared.
- ❌ **If something goes wrong:** the status line turns **red** and reads
  `Load failed.`, and a popup window titled "Board load failed" appears with
  details. This IS the app correctly reporting a real problem — note the
  board name and the error message shown.

- Optional: tick **"Force regenerate"** before clicking "Load board" again —
  this forces the app to reprocess the board from scratch instead of using a
  cached result. Confirm it still finishes successfully (just may take a bit
  longer).

### Step 3 — SPICE Simulation tab
- Click the **SPICE Simulation** tab.
- Click **"Convert .cir"** first.
  - **Expected:** status line turns green and reads `Conversion complete.`,
    and the text box shows the path to the generated `.cir` file.
- Click **"Run ngspice simulation"**.
  - **Expected while running:** button(s) grey out, progress bar shows,
    bottom status bar shows `Working: Running ngspice simulation for
    '<board>'...`.
  - **Expected on success:** status line turns green, reads `Simulation
    complete.`, and the text box lists the generated file paths plus a list
    of simulated variables (voltages/currents) with sample counts.
  - **Expected on failure:** status line turns red, reads `Operation
    failed.`, and a popup titled "SPICE operation failed" explains why (for
    most boards other than `stack-chan`, a failure here is a **known,
    already-understood limitation** — see the note at the bottom of this
    guide — not something you need to re-report).
- Try the **"Check expected voltage"** box:
  - Type a net name, e.g. `+3V3`, into **"Net:"**.
  - Type `3.3V` into **"Expected voltage:"**.
  - Click **"Check"**.
  - **Expected:** status line reads either `Result: MATCHES expected
    voltage.` (green) or `Result: does NOT match expected voltage.` — both
    are valid outcomes, it just depends on the board and the net/voltage you
    typed in.

### Step 4 — Q&A tab
*(Needs a working Gemini API key in `.env` — see Part 0.)*
- Click the **Q&A** tab.
- Type a question into the **"Question:"** box, e.g.:
  `In one sentence, what is the overall purpose of this board based on its netlist?`
- Click **"Ask"** (or just press Enter).
- **Expected while working:** button greys out, progress bar shows, status
  line reads `Asking Gemini...`. If the AI needs to look something up (e.g.
  check a connection or a datasheet), you'll see lines like `Calling
  <tool_name>(...) -> ...` appear live in the text box **before** the final
  answer — this is the AI "showing its work."
- **Expected on success:** status line turns green, reads `Done.`, and the
  text box ends with `Answer:` followed by a real, readable sentence.
- **Expected on failure:** status line turns red, reads `Request failed.`,
  and a popup titled "Q&A request failed" explains why (most commonly: no
  API key configured).

### Step 5 — Benchmark tab
*(Needs a working Gemini API key in `.env`.)*
- Click the **Benchmark** tab.
- Choose a **Strategy** from the dropdown (any option is fine to test).
- Set **Limit** to a small number like `3` so the test doesn't take too long.
- Click **"Run benchmark"**.
- **Expected while working:** progress bar fills up question by question,
  status line counts up `Question 1 of 3...`, `Question 2 of 3...`, etc.,
  and each answered question appears live in the text box as a line starting
  with `[OK]` or `[X ]`.
- **Expected on success:** status line turns green, reads `Benchmark
  complete.`, and the text box shows a final summary: Strategy, Accuracy,
  Precision, Recall, F1, a confusion matrix, and where the detailed results
  were saved — followed by the full per-question list.
- **Expected on failure:** status line turns red, reads `Benchmark failed.`,
  and a popup titled "Benchmark failed" explains why.

### Step 6 — Repeat
Go back to Step 1, pick the next board from the dropdown, and repeat Steps
2–5. Do this for all 8 boards.

---

## Part 3 — What "success" looks like overall

By the end you should be able to say, for each of the 8 boards:

| Tab | stack-chan | Other 7 boards |
|---|---|---|
| Board | ✅ loads cleanly | ✅ loads cleanly |
| SPICE Simulation | ✅ fully simulates | ⚠️ may fail — see note below |
| Q&A | ✅ answers | ✅ answers |
| Benchmark | ✅ completes | ✅ completes |

**Note on SPICE failures:** 7 of the 8 boards contain real chips
(microcontrollers, regulators, sensors, etc.) that the app does not have
electrical models for — only LEDs and simple resistor/capacitor/inductor
parts can currently be fully simulated. So a SPICE failure on those 7 boards
is an **expected, already-known limitation**, not a new bug, as long as:
- the app shows a clear red "Operation failed." message with an
  understandable popup explanation (not a crash, not a frozen window, not a
  confusing wall of text).

If you ever see the app **freeze completely** (window stops responding, you
can't click anything, no popup ever appears), that IS a real bug worth
reporting immediately, regardless of which board or tab it happened on.

---

## Part 4 — Quick checklist (print/tick this while testing)

For **each** of the 8 boards:
- [ ] Board dropdown lists it
- [ ] Board tab: "Load board" → green "Loaded '...'" + summary text
- [ ] SPICE tab: "Convert .cir" → green "Conversion complete."
- [ ] SPICE tab: "Run ngspice simulation" → green success OR a clear red
      failure popup (no freeze)
- [ ] SPICE tab: "Check" → shows MATCHES or does NOT match (either is fine)
- [ ] Q&A tab: ask a question → green "Done." + readable answer
- [ ] Benchmark tab: run with limit 3 → rows stream in live → green
      "Benchmark complete." + summary stats
- [ ] No window freezes at any point
- [ ] No popup text is garbled or unreadable

When every box is ticked for every board, the app has been genuinely
end-to-end tested, visually, by a human.
