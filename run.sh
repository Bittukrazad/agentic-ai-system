#!/usr/bin/env bash
# run.sh — Start the Agentic AI System locally
# Usage:
#   ./run.sh          → start API + dashboard
#   ./run.sh api      → API only
#   ./run.sh dash     → dashboard only
#   ./run.sh test     → run all tests
#   ./run.sh docker   → docker-compose up

set -e
MODE=${1:-all}

# ── Helpers ────────────────────────────────────────────────────────────────
check_env() {
    if [ ! -f .env ]; then
        echo "[INFO] .env not found — copying .env.example to .env"
        cp .env.example .env
        echo "[WARN] Edit .env and set your OPENAI_API_KEY or ANTHROPIC_API_KEY"
        echo "       Without a key the system runs in mock LLM mode (great for demos)"
    fi
}

install_deps() {
    echo "[INFO] Installing Python dependencies..."
    pip install -r requirements.txt -q
}

start_api() {
    echo "[INFO] Starting FastAPI server on http://localhost:8000"
    echo "[INFO] Interactive docs: http://localhost:8000/docs"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}

start_dashboard() {
    echo "[INFO] Starting Streamlit dashboard on http://localhost:8501"
    streamlit run dashboard/streamlit_app.py --server.port 8501
}

run_tests() {
    echo "[INFO] Running all tests..."
    python -m pytest tests/ -v --tb=short
}

# ── Main ───────────────────────────────────────────────────────────────────
check_env

case $MODE in
    api)
        install_deps
        start_api
        ;;
    dash|dashboard)
        install_deps
        start_dashboard
        ;;
    test)
        install_deps
        run_tests
        ;;
    docker)
        docker-compose up --build
        ;;
    all)
        install_deps
        # Start API in background, then dashboard in foreground
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
        API_PID=$!
        echo "[INFO] API started (PID $API_PID)"
        sleep 2
        echo "[INFO] Starting Streamlit dashboard..."
        streamlit run dashboard/streamlit_app.py --server.port 8501
        kill $API_PID 2>/dev/null || true
        ;;
    *)
        echo "Usage: ./run.sh [api|dash|test|docker|all]"
        exit 1
        ;;
esac
