# PCB-QA Desktop App container image.
#
# This is a Tkinter desktop GUI, not a web server: it needs a display to
# render to. See DOCKER.md for how to point it at an X11 server on Linux,
# Windows (VcXsrv) or macOS (XQuartz).
FROM python:3.12-slim-bookworm

# System dependencies:
# - ngspice: SPICE Simulation tab runs this as a subprocess (backend/spice_service.py)
# - python3-tk: pulls in the libtcl8.6/libtk8.6 shared libraries the stdlib
#   tkinter module needs at runtime (the module itself ships with the base
#   Python image; only the Tcl/Tk runtime libraries are missing)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ngspice \
        python3-tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so this layer is cached and only
# re-runs when requirements.txt changes, not on every source-code edit.
#
# torch is installed separately, first, from PyTorch's CPU-only wheel index:
# this is a desktop app with no GPU workload, but sentence-transformers (in
# requirements.txt) depends on torch, and plain PyPI only ships torch's full
# CUDA build on linux/amd64 (several GB of unneeded NVIDIA libraries). With
# torch already satisfied from the CPU-only index, the requirements.txt
# install below won't pull the GPU build in behind it.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Application source, including the bundled Boards/ sample data, so the
# image is runnable standalone without any extra volume mounts.
COPY . .

# Must match (or be overridden to match) the X server the container will
# render to; see DOCKER.md for the Linux/Windows/macOS-specific value.
ENV DISPLAY=host.docker.internal:0.0
# Headless-safe default; harmless if GEMINI_API_KEY/NGSPICE_PATH etc. are
# also supplied via --env-file .env at `docker run` time.
ENV NGSPICE_PATH=ngspice

CMD ["python", "main.py"]
