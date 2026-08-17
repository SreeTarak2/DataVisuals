# Security & SaaS-Readiness Roadmap — DataSage

**Date:** August 6, 2026 (v2 — refreshed competitor research + verified codebase audit)
**Scope:** Competitor-derived security feature set + audit of DataSage's current implementation + prioritized roadmap to make DataSage a sellable, enterprise-grade SaaS product.

**Grounded in:**
- Competitor research (fresh, Aug 2026): Hex, Mode Analytics, Julius AI, DataChat, Tellius, Akkio, and the AI features inside Tableau, Microsoft Power BI, and Google Looker
- 2026 SaaS security best-practice checklists (SOC 2, ISO 27001, GDPR, HIPAA, OWASP)
- Direct code inspection of `version2/backend` (verified against source, not marketing)

---

## 1. Competitor Security Posture (Aug 2026)

| Feature | Hex | Mode | Julius AI | DataChat | Tellius | Akkio | Tableau AI | Power BI | Looker |
|---|---|---|---|---|---|---|---|---|---|
| **Certifications** | SOC 2 T2, HIPAA | SOC 2 | SOC 2 T2, TX-RAMP | — | SOC 2 T2 | SOC 2 T2, HIPAA controls | SOC 2 T2, HIPAA, GDPR, ISO | SOC 1/2, HIPAA, ISO 27001, GCC High | SOC 1/2/3, ISO |
| **SSO (SAML/OIDC)** | ✅ OIDC/Okta/Google | ✅ | ✅ Enterprise tier | ✅ | ✅ OIDC | ✅ | ✅ | ✅ Entra | ✅ |
| **SCIM provisioning** | ✅ | ✅ | ❌ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| **MFA** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **RBAC** | Fine-grained | ✅ | ✅ | ✅ | ✅ | ✅ | Native | ✅ | ✅ |
| **Row/Column-level security** | RLS on artifacts | — | — | Respects underlying authorization | Row-level | — | **RLS native** | **RLS native** | **RLS via LookML** |
| **Encryption** | AES-256 rest, TLS 1.2+ | AES-256 rest, TLS | Rest + transit | ✅ | ✅ | TLS + disk encryption | ✅ | ✅ | ✅ |
| **Audit logging** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI governance** | ZDR from LLMs, no training | — | Explicit no-training | — | — | — | **Einstein Trust Layer** (ZDR, PII masking, toxicity guardrails) | **Copilot** (no training, Purview DLP) | **Gemini** (prompts not used for training) |
| **Data residency / single-tenant** | EU + single-tenant VPC | — | US regional | — | ✅ | — | ✅ | ✅ | ✅ |
| **Pen test / VDP** | VDP + bug bounty | ✅ | VDP | — | — | Annual pen test | ✅ | ✅ | ✅ |
| **DataSage (today)** | Google OAuth only | App-layer `workspace_id` | Fernet (secrets) | GDPR-aware audit ✅ | Prompt-injection guard ✅ | No certs yet | No MFA/SSO/SCIM | No pen test/VDP | No trust center |

**Key takeaway — two distinct competitive fronts:**

1. **AI-native tools** (Hex, Julius, Mode, DataChat, Tellius, Akkio) compete on **AI governance**: zero data retention from LLM providers, explicit "we never train on your data" guarantees, regional isolation, and AI that respects the user's underlying data permissions.
2. **Enterprise BI giants** (Tableau, Power BI, Looker) compete on **data governance depth**: row/column-level security baked into the semantic layer (Einstein Trust Layer, Purview sensitivity labels/DLP, LookML-enforced RLS).

**DataSage needs both halves to be credible in enterprise procurement.**

---

## 2. AI Governance — the 2026 conversation (competitor detail)

| Competitor | Mechanism |
|---|---|
| **Hex** | LLM providers (OpenAI, Anthropic) under **zero data retention** policies; explicitly guarantees providers **do not train on customer data**; ephemeral analysis in kernel memory |
| **Julius AI** | Explicit "**We never use your data to train AI**"; data stored/processed in regionally isolated US clouds; users can delete all traces |
| **Tableau (Einstein Trust Layer)** | **Zero Data Retention** for prompts/responses sent to external LLMs; automated toxicity + **PII masking before prompts reach models**; AI inherits native RLS — cannot surface data a user can't see |
| **Power BI (Copilot)** | Enterprise boundary isolation; **customer data never used to train foundational models**; Purview sensitivity labels + DLP policies; geographic data residency |
| **Looker (Gemini)** | Prompts/responses isolated to enterprise tenancy; **not used to train core models**; LookML semantic layer enforces RLS/object-level access |

---

## 3. Current State (verified codebase audit — Aug 2026)

### ✅ Already Implemented (verified in source)

| Area | Location |
|---|---|
| JWT + bcrypt password auth | `backend/services/auth/` |
| Google OAuth | `backend/api/auth/routes.py` |
| HttpOnly cookie auth + CSRF middleware | `backend/core/auth.py` |
| RBAC roles (owner/admin/member/viewer, hierarchical) | `backend/core/permissions.py` |
| Workspace multi-tenancy (app layer) | `backend/middleware/workspace.py` |
| Fernet encryption of DB creds + API keys (dedicated `DB_ENCRYPTION_KEY` separate from `SECRET_KEY`) | `backend/services/encryption.py`, `services/databases/db_connection_service.py` |
| **BYOK — SHIPPED** (encrypted user LLM keys, provider routing, safe metadata-only responses) | `backend/services/api_keys/service.py`, `api/api_keys/routes.py`, `llm/router.py` (BYOKLookup), `llm/providers/`, `db/models/user_api_key.py` |
| PII detection / auto-redaction / privacy audit trail / sensitive-column gate | `backend/services/privacy/`, `services/semantic/checkpoint_gate.py` |
| Rate limiting (SlowAPI) on all API groups + chat limiter | `backend/core/rate_limiter.py`, `services/rate_limiter_chat.py` |
| Circuit breakers, token budgets, concurrency limits, run timeouts on agents | `backend/agents/resilience/`, `agents/base_agent.py` |
| Prompt-injection guard on every agent run + SQL-injection detection in query layer + CSV formula-injection check | `backend/services/prompt_injection_guard.py`, `core/prompt_sanitizer.py`, `services/query/executor.py`, `services/databases/connectors/base.py`, `services/datasets/file_storage_service.py` |
| GDPR audit service (hashed queries, data export, right-to-be-forgotten, retention cleanup) | `backend/services/audit/service.py` |
| Agent-execution audit logging (fire-and-forget, with tools/iterations) | `backend/agents/base_agent.py` → `services/audit/` |

### ⚠️ Partial / needs hardening

- **Tenant isolation is app-layer only** — datasets/queries filtered by `workspace_id` in code, not enforced at the database. One bug = cross-tenant leak.
  - **Confirmed TODO:** `services/pipeline/process.py` hardcodes `workspace_id` to `user_id` ("Single-tenant default"). **Highest-priority real vulnerability.**
- **Secrets live in `.env`** (`SECRET_KEY`, `DB_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`) — no secret manager / KMS. Key rotation requires re-encrypting all stored BYOK keys.
- **CSRF middleware exists but defaults to disabled** (`CSRF_ENABLED=false`); must be enabled for GA once the frontend sends `X-CSRF-Protection: 1`.
- **HSTS/CSP present** but TLS 1.0/1.1 rejection and HSTS max-age/preload should be verified against production config.
- **BYOK** is built but unadvertised; `COMPETITIVE_STRATEGY.md` §6 still says "don't copy BYOK" — that note is outdated.

### ❌ Missing (hard gaps vs. market)

- MFA (TOTP / WebAuthn)
- Enterprise SSO (SAML 2.0 / OIDC) — Google OAuth only
- SCIM automated user provisioning/deprovisioning
- Session management: idle timeout, account lockout, concurrent-session policy
- Database-level tenant RLS / tenant guard
- Row/column-level data security (RLS/CLS) — the enterprise differentiator
- Centralized secret management / KMS / Vault + key rotation
- Backup encryption + tested restore
- Data retention & hard-deletion policy (soft deletes exist)
- IP allowlisting
- WAF / DDoS protection on public endpoints
- Penetration test program + vulnerability disclosure program (VDP)
- Public trust center, DPAs, sub-processor list, privacy policy
- SOC 2 / ISO 27001 certification track
- Explicit no-training-on-user-data policy + LLM-provider commitments (competitors all advertise this)

---

## 4. Prioritized Roadmap

Priority order follows real-world impact + enterprise procurement requirements, per 2026 SaaS checklists.

### 🛑 Table stakes (required to pass security review / enter RFPs)

| Priority | Capability | Why | Map to |
|---|---|---|---|
| **P0 — Launch/security baseline** | | | |
| 1 | **Close hardcoded `workspace_id = user_id` TODO + DB-layer tenant guard** | Multi-tenant isolation is non-negotiable; app-layer only = cross-tenant leak risk | `db/`, `services/pipeline/process.py` |
| 2 | MFA (TOTP app + optional WebAuthn, recovery codes) | #1 enterprise expectation; every competitor has it | `services/auth`, `db/schemas_auth.py` |
| 3 | Secret manager + key rotation (KMS/Vault); remove secrets from `.env` | Mitigates misconfig (67% of SaaS breaches) | `core/config.py`, deploy scripts |
| 4 | Session security: idle timeout (≤30 min), account lockout (5 attempts), concurrent-session policy | Auth hardening | `core/auth.py` |
| 5 | Enable CSRF in production; verify TLS 1.2+ policy + HSTS preload | Baseline hardening | `core/auth.py`, `main.py`, infra |
| 6 | WAF (Cloudflare free tier) + dependency scanning in CI | Prevents most common attacks | deploy/CI, package manifests |

### 🚀 Differentiators (win enterprise bake-offs)

| Priority | Capability | Why | Map to |
|---|---|---|---|
| **P1 — Enterprise readiness** | | | |
| 7 | **SSO via SAML 2.0 / OIDC (Okta, Azure AD, Google)** | Non-negotiable for deals >$50k ACV | `api/auth`, frontend login |
| 8 | **Row/column-level data security (RLS/CLS) at the semantic layer** — reuse PII detector + column-role classifier | Enterprise ML/BI differentiator; none of the AI-native competitors do this well; DataSage's semantic layer is uniquely positioned | `core/permissions.py`, query layer, `services/privacy/` |
| 9 | **AI governance commitments** — explicit no-training-on-user-data policy + zero-retention posture from LLM providers; AI agents already inherit user permissions via RBAC | Competitor table stakes; turns the 2026 AI-governance conversation into a sales asset | docs, `llm/` config, agent permission wiring |
| 10 | Audit log retention ≥12 mo, immutable/write-only + admin-visible | SOC 2 / compliance | `services/audit/` |
| 11 | Backup encryption + quarterly restore test | SOC 2 | infra, scripts |
| 12 | Pen test (annual) + vulnerability disclosure program + public security page | Trust signal; closes enterprise deals ~3x faster | docs, `/.well-known` |

### ⚖️ Compliance & legal

| Priority | Capability | Why | Map to |
|---|---|---|---|
| **P2** | SOC 2 Type II certification track (start 6 mo ahead) | Table stakes for B2B | org + docs |
| **P2** | Published privacy policy, DPA, sub-processor list, data-subject request handling + retention/deletion policy | GDPR | docs |
| **P2** | Data residency options (EU / US) + single-tenant deployment opt | Residency closes international deals | infra |
| **P2** | SCIM provisioning | Saves IT overhead; most mid-market tools lack it | `api/auth`, identity layer |
| **P2** | Documented + tested incident response plan | SOC 2 / IR | docs |

---

## 5. Recommended immediate next steps

1. **Draft a one-page trust-center story** (SOC 2 in progress, pen-test schedule, VDP, DPA template, no-training commitment) — buyers review this *before* a sales call. Model it on Hex/Julius' public security pages.
2. **Ship MFA (TOTP)** end-to-end: schema, prompt at login, recovery codes, enable-per-workspace.
3. **Close the hardcoded single-tenant TODO** and add a DB-layer tenant guard — the one thing that could sink a security review.
4. **Move `SECRET_KEY`, `DB_ENCRYPTION_KEY`, API keys into a secret manager**; keep `.env.example` as reference only.
5. **Advertise BYOK** (already built) as an enterprise feature; update `COMPETITIVE_STRATEGY.md` §6 accordingly.

---

*Associated doc: `version2/docs/COMPETITIVE_STRATEGY.md` (product positioning). v1 of this doc: Aug 4, 2026.*
