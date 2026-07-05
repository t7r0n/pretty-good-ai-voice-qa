# Local Agent Instructions

- Use only the workspace-local Python environment for this project.
- Install or run Python packages with `uv` from this directory: `uv sync`, `uv add ...`, `uv run ...`.
- Keep uv and model caches local when running commands:
  `UV_CACHE_DIR=$PWD/.codex_local_memory/uv-cache UV_PYTHON_INSTALL_DIR=$PWD/.codex_local_memory/python XDG_CACHE_HOME=$PWD/.codex_local_memory/cache HF_HOME=$PWD/.codex_local_memory/cache/huggingface uv run ...`
- Do not use global `pip`, `pipx`, `uv tool install`, global MCP config, or sibling workspace files for this project.
- Never print or commit secrets from `.env`; only report whether required keys are present.
- Keep memory data under `.codex_local_memory/` and project knowledge under `docs/wiki/`.
- Before ending substantial work, write important decisions or durable facts into local memory with `uv run pg-memory remember "..." --title "..."`.
- For recall, prefer `uv run pg-memory search "query"` and `uv run pg-memory context "query"` before assuming prior decisions are lost.
- If MCP is used, launch the local server only with `uv run pg-memory-mcp` from this directory.
- For the Pretty Good AI challenge harness, use `uv run voiceqa ...` from this directory for local simulation, artifact generation, and Groq transcription checks.
