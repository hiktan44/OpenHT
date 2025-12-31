# OpenHT Full-Stack Coolify Deployment

## Overview
Deploys the OpenHT application to a self-hosted Coolify instance. This involves Dockerizing the full-stack application (FastAPI + Supabase integration), pushing updates to GitHub, and configuring the Coolify project with necessary environment variables and build settings.

## Checklist
- [x] Configure Docker environment
  - [x] Create production `Dockerfile` with multi-stage build
  - [x] Create `docker-compose.yml` for simplified orchestration
  - [x] Update `.dockerignore` to exclude local artifacts
- [x] Manage Dependencies
  - [x] Update `requirements.txt` with production packages (`uvicorn`, `supabase`, `fastapi`, etc.)
- [ ] Git Synchronization <!-- id: 0 -->
  - [ ] Stage and commit deployment configuration files <!-- id: 1 -->
  - [ ] Push changes to GitHub repository <!-- id: 2 -->
- [ ] Coolify Configuration <!-- id: 3 -->
  - [ ] Create new project/service in Coolify <!-- id: 4 -->
  - [ ] set Environment Variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `OPENROUTER_API_KEY`, etc.) <!-- id: 5 -->
  - [ ] Trigger initial deployment <!-- id: 6 -->
- [ ] Verification <!-- id: 7 -->
  - [ ] Verify build logs for success <!-- id: 8 -->
  - [ ] Test public endpoint accessibility <!-- id: 9 -->
