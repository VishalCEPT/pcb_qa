"""
Throwaway end-to-end GUI verification script (not a pytest test, not meant to
be committed). Shows the REAL app window (not withdrawn) and drives it across
all 8 real uploaded boards, taking PNG screenshots via an external PowerShell
helper at each step so a human/multimodal reviewer can actually look at the
rendered UI, not just assert on widget state.
"""
import subprocess
import sys
import time
import tkinter as tk

from dotenv import load_dotenv
load_dotenv()

from backend import board_service
from gui import app as app_module
from gui.app import App

dialogs = []
app_module.messagebox.showinfo = lambda *a, **_k: dialogs.append(a)
app_module.messagebox.showerror = lambda *a, **_k: dialogs.append(a)

SHOT_DIR = r"C:\Users\vishalkr\AppData\Local\Temp\gui_shots"
PS_SCRIPT = r"C:\Users\vishalkr\AppData\Local\Temp\screenshot.ps1"

ALL_BOARDS = board_service.list_boards()
QA_BENCHMARK_BOARDS = ["stack-chan", "AcornRobotElectronics", "HadesFCS"]

failures = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}", flush=True)
    if not cond:
        failures.append(label)


def pump_until(root, predicate, timeout=90.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def shot(name):
    # Must NOT use subprocess.run() (blocking) here: screenshot.ps1 uses
    # PrintWindow, which sends the target window a WM_PRINT message that its
    # owning thread's message loop must process to respond. That thread is
    # *this* one -- so blocking it on subprocess.run() while waiting for
    # PrintWindow to return deadlocks forever (confirmed: the window then
    # shows as "Not Responding" in Task Manager / Get-Process). Use Popen +
    # a polling loop that keeps calling root.update() instead, so the
    # message loop stays alive while the screenshot is being taken.
    out_path = f"{SHOT_DIR}\\{name}.png"
    proc = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS_SCRIPT, "-OutPath", out_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    deadline = time.monotonic() + 15.0
    while proc.poll() is None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    if proc.poll() is None:
        proc.kill()
    stdout, stderr = proc.communicate(timeout=5)
    result = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    ok = "OK" in result.stdout
    check(f"screenshot captured: {name}", ok)
    if not ok:
        print("  ps stdout:", result.stdout.strip())
        print("  ps stderr:", result.stderr.strip())


root = tk.Tk()
root.title("PCB-QA Desktop")
app = App(root)
notebook = app.board_tab.master
root.deiconify()
root.lift()
root.attributes("-topmost", True)
root.update()
root.attributes("-topmost", False)
root.update()
time.sleep(0.5)

print(f"Boards discovered: {ALL_BOARDS}")
check("all 8 uploaded boards discovered", len(ALL_BOARDS) == 8)

shot("00_initial_launch")

for board_name in ALL_BOARDS:
    print(f"\n=== {board_name} ===")
    app.board_var.set(board_name)
    root.update()

    # ---- Board tab ----
    notebook.select(app.board_tab)
    app.board_tab._on_load()
    root.update()
    if board_name == ALL_BOARDS[0]:
        shot(f"board_{board_name}_mid_busy")
        check("progress bar visible while board loads", bool(app.board_tab.progress.bar.winfo_manager()))
        check("status bar shows Working during board load", app.status_bar_label.cget("text").startswith("Working:"))
        check("board combo disabled during board load", str(app.board_combo.cget("state")) == "disabled")

    ok = pump_until(root, lambda: app.board_tab.status_label.cget("text").startswith("Loaded"))
    check(f"[{board_name}] board load finished", ok)
    shot(f"board_{board_name}")
    check(f"[{board_name}] status label styled Success.TLabel", app.board_tab.status_label.cget("style") == "Success.TLabel")

    # ---- SPICE tab ----
    notebook.select(app.spice_tab)
    app.spice_tab._on_run()
    ok = pump_until(root, lambda: app.spice_tab.status_label.cget("text") in ("Simulation complete.", "Operation failed."), timeout=60.0)
    check(f"[{board_name}] spice run finished", ok)
    shot(f"spice_{board_name}")
    check(f"[{board_name}] spice simulation succeeded", app.spice_tab.status_label.cget("text") == "Simulation complete.")

    if board_name not in QA_BENCHMARK_BOARDS:
        continue

    # ---- Q&A tab ----
    notebook.select(app.qa_tab)
    app.qa_tab.question_entry.delete(0, tk.END)
    app.qa_tab.question_entry.insert(0, "In one sentence, what is the overall purpose of this board based on its netlist?")
    app.qa_tab._on_ask()
    root.update()
    if board_name == QA_BENCHMARK_BOARDS[0]:
        shot(f"qa_{board_name}_mid_busy")
        check("qa progress bar visible while asking", bool(app.qa_tab.progress.bar.winfo_manager()))
    ok = pump_until(root, lambda: app.qa_tab.status_label.cget("text") in ("Done.", "Request failed."), timeout=90.0)
    check(f"[{board_name}] qa request finished", ok)
    shot(f"qa_{board_name}")
    check(f"[{board_name}] qa answered successfully", app.qa_tab.status_label.cget("text") == "Done.")

    # ---- Benchmark tab ----
    notebook.select(app.benchmark_tab)
    app.benchmark_tab.limit_entry.delete(0, tk.END)
    app.benchmark_tab.limit_entry.insert(0, "3")
    app.benchmark_tab._on_run()
    root.update()
    if board_name == QA_BENCHMARK_BOARDS[0]:
        shot(f"benchmark_{board_name}_mid_busy")
        check("benchmark progress bar visible while running", bool(app.benchmark_tab.progress.bar.winfo_manager()))

    first_len = len(app.benchmark_tab.output.get("1.0", tk.END))
    grew = False
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        root.update()
        text = app.benchmark_tab.status_label.cget("text")
        if text in ("Benchmark complete.", "Benchmark failed."):
            break
        if len(app.benchmark_tab.output.get("1.0", tk.END)) > first_len:
            grew = True
        time.sleep(0.02)
    check(f"[{board_name}] benchmark rows streamed live", grew)
    check(f"[{board_name}] benchmark finished", app.benchmark_tab.status_label.cget("text") == "Benchmark complete.")
    shot(f"benchmark_{board_name}")

root.destroy()

print()
if dialogs:
    print(f"{len(dialogs)} dialog(s) were shown (would have blocked a real run):")
    for d in dialogs:
        print(" -", d)
print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:")
    for f in failures:
        print(f" - {f}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
