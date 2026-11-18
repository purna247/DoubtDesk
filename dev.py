#!/usr/bin/env python3
"""
DoubtDesk Developer CLI Runner
Implements the 'deep module' design pattern: hides environment discovery,
port checks, migrations, and process orchestration behind a single minimal interface.

Usage:
    python dev.py backend       # Starts backend API (auto-checks DB & migrations)
    python dev.py frontend      # Starts frontend Vite dev server
    python dev.py worker        # Starts background ingestion worker
    python dev.py seed          # Seeds initial database data
    python dev.py all           # Runs both backend and frontend concurrently
"""

import os
import sys
import socket
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def get_backend_python() -> Path:
    """Finds the virtualenv Python binary, falling back to sys.executable."""
    # Windows virtualenv
    win_venv = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if win_venv.exists():
        return win_venv
    
    # Unix/macOS virtualenv
    unix_venv = BACKEND_DIR / ".venv" / "bin" / "python"
    if unix_venv.exists():
        return unix_venv
    
    # Fallback to current python
    return Path(sys.executable)


def is_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    """Checks if a TCP port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False


def ensure_database():
    """Verifies that the PostgreSQL database is reachable."""
    print("[*] Checking PostgreSQL connectivity (localhost:5432)...")
    if is_port_open("127.0.0.1", 5432):
        print("[✓] PostgreSQL is active and listening on port 5432.")
        return True

    print("[!] PostgreSQL is not responding on port 5432.")
    print("[*] Attempting to start PostgreSQL via Docker Compose...")
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "db"],
            cwd=str(ROOT_DIR),
            check=True
        )
        # Give it a few seconds to initialize
        import time
        for _ in range(10):
            time.sleep(1)
            if is_port_open("127.0.0.1", 5432):
                print("[✓] PostgreSQL container is ready!")
                return True
        print("[!] Warning: PostgreSQL container started but port 5432 is not answering yet.")
    except Exception as e:
        print(f"[!] Could not start PostgreSQL container: {e}")
        print("    Please ensure your local PostgreSQL service or Docker is running.")
    return False


def run_migrations(py_bin: Path):
    """Executes database migrations automatically."""
    print("[*] Checking database migrations (alembic upgrade head)...")
    result = subprocess.run(
        [str(py_bin), "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("[✓] Database schema is up to date.")
    else:
        print(f"[!] Alembic migration warning:\n{result.stderr.strip() or result.stdout.strip()}")


def run_backend():
    """Runs the FastAPI backend dev server with hot reload."""
    py_bin = get_backend_python()
    print(f"[*] Using Python: {py_bin}")
    ensure_database()
    run_migrations(py_bin)
    
    print("\n" + "=" * 60)
    print("  🚀 Starting DoubtDesk Backend API")
    print("  API Docs:  http://localhost:8000/docs")
    print("  Health:    http://localhost:8000/health")
    print("=" * 60 + "\n")
    
    cmd = [
        str(py_bin),
        "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    try:
        subprocess.run(cmd, cwd=str(BACKEND_DIR))
    except KeyboardInterrupt:
        print("\n[*] Backend server stopped.")


def run_worker():
    """Runs the background job processing worker."""
    py_bin = get_backend_python()
    print(f"[*] Starting DoubtDesk Background Worker with {py_bin}...")
    try:
        subprocess.run([str(py_bin), "-m", "app.worker"], cwd=str(BACKEND_DIR))
    except KeyboardInterrupt:
        print("\n[*] Background worker stopped.")


def run_seed():
    """Seeds the database."""
    py_bin = get_backend_python()
    print(f"[*] Seeding database using {py_bin}...")
    subprocess.run([str(py_bin), "-m", "app.seed"], cwd=str(BACKEND_DIR))


def run_frontend():
    """Runs the Vite React frontend dev server."""
    print("\n" + "=" * 60)
    print("  ⚛️ Starting DoubtDesk Frontend")
    print("  App URL: http://localhost:3000")
    print("=" * 60 + "\n")
    
    # Use npm.cmd on Windows, npm on Unix
    npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
    try:
        subprocess.run([npm_bin, "run", "dev"], cwd=str(FRONTEND_DIR))
    except KeyboardInterrupt:
        print("\n[*] Frontend server stopped.")


def run_all():
    """Runs backend API, background worker, and frontend dev server concurrently."""
    print("\n" + "=" * 60)
    print("  🌟 Starting DoubtDesk Full Stack (Backend + Worker + Frontend)")
    print("  Frontend: http://localhost:3000")
    print("  Backend:  http://localhost:8000")
    print("  Worker:   Active (processing queued uploads & extractions)")
    print("  Press Ctrl+C at any time to stop all services.")
    print("=" * 60 + "\n")

    py_bin = get_backend_python()
    ensure_database()
    run_migrations(py_bin)

    backend_proc = None
    worker_proc = None
    frontend_proc = None

    try:
        npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
        backend_cmd = [
            str(py_bin), "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", "8000", "--reload"
        ]
        backend_proc = subprocess.Popen(backend_cmd, cwd=str(BACKEND_DIR))

        worker_cmd = [str(py_bin), "-m", "app.worker"]
        worker_proc = subprocess.Popen(worker_cmd, cwd=str(BACKEND_DIR))

        frontend_proc = subprocess.Popen([npm_bin, "run", "dev"], cwd=str(FRONTEND_DIR))

        backend_proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Shutting down servers...")
    finally:
        for proc in (backend_proc, worker_proc, frontend_proc):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        print("[✓] All services stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(
        description="DoubtDesk Developer Runner (Unified Deep Interface)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dev.py backend    # Run API server (with DB check & auto-migration)
  python dev.py frontend   # Run Vite frontend server
  python dev.py all        # Run both backend and frontend together
  python dev.py worker     # Run background ingestion worker
  python dev.py seed       # Run database seed script
        """
    )
    parser.add_argument(
        "service",
        nargs="?",
        default="backend",
        choices=["backend", "frontend", "all", "worker", "seed"],
        help="Target service to run (default: backend)"
    )

    args = parser.parse_args()

    if args.service == "backend":
        run_backend()
    elif args.service == "frontend":
        run_frontend()
    elif args.service == "all":
        run_all()
    elif args.service == "worker":
        run_worker()
    elif args.service == "seed":
        run_seed()


if __name__ == "__main__":
    main()
