# LungSight AI — standing rules

Stack: Streamlit web app (hospital-facing), Expo/React Native mobile companion, Supabase (auth, Postgres, RLS), PayMongo payments. No PyQt. No architecture rewrites.

## Git
- Work on a feature branch created from current HEAD. Never touch main, never push, never force-push, never reset/stash/discard my uncommitted changes.
- Run `git grep -n -e "<<<<<<<" -e ">>>>>>>"` first; an earlier main had committed merge-conflict markers.
- Commit on the feature branch only after a milestone is verified.

## Safety
- Never print, log, commit or document secrets (service-role, PayMongo, email, webhook keys) or patient data. Refer to env vars by name. Never put secrets in EXPO_PUBLIC_* or browser code. Never ask me to paste credentials.
- Supabase inspection is read-only. Do not apply migrations, DDL, RLS/grant changes, cron jobs or Edge Function deployments without my explicit approval. Show full SQL first. Prefer a Supabase branch or local instance for tests.
- Service-role access stays server-side and narrowly scoped. No public SECURITY DEFINER shortcuts. Hospital isolation must be enforced in the data-access layer/RLS, not by hiding UI. Never trust client-supplied hospital_id, actor_id or role.
- Known issues to re-verify, not silently change: `patients`/`examinations` SELECT policies with USING (true); 16 tables with RLS enabled but no policies.

## Honesty
- Never invent tables, columns, statuses, roles or business rules; verify against live schema and code.
- Never claim tests passed, a migration/webhook/scheduler is deployed, or an email was delivered unless actually verified. Mark unrun items UNVERIFIED with the reason.
- An AI prediction is not a diagnosis.
- Audit-write or email failures must never change the result of the primary business operation, and must not be silent.

## Workflow for each phase
Stage 0 pre-flight (read-only report) → Stage 1 plan (STOP for my approval) → Stage 2 implement in the stated order → tests → concise final report. Stop after the phase; do not start the next one.

## Final report format
What was built; files changed; migration contents and real deployment status; auth/isolation approach; existing security issues (changed/deferred/unresolved); tests run with actual results; setup/env vars; limitations; manual steps for me.