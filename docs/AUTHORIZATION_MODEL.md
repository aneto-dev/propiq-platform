# PropIQ Platform — Authorization Model

## Purpose

This document defines the authentication model, authorization philosophy,
ownership rules, role structure, permission matrix, and enforcement strategy
for the PropIQ platform.

This document is architecture only. It contains no FastAPI route implementations,
no SQLAlchemy models, no DTO definitions, no migration scripts, and no
implementation code.

All terminology matches DOMAIN_GLOSSARY.md.
All domain entity lifecycle rules are sourced from DOMAIN_MODEL_ARCHITECTURE.md.
All service enforcement rules align with APPLICATION_SERVICE_ARCHITECTURE.md.
All trust requirements align with TRUST_MODEL.md and DECISIONS.md.

---

## Document Status

Version: 1.0
Phase coverage: Phase 1 complete with Phase 2–5 extension design

---

---

# Part 1 — Authentication Model

---

## 1.1 — Authentication Is Fully Delegated to Supabase Auth

PropIQ does not implement its own authentication system. Token issuance,
password management, session handling, refresh token rotation, and OAuth
provider integration are all delegated to Supabase Auth.

This is a deliberate architectural boundary. Authentication infrastructure
is not a competitive differentiator for this platform. Building it from
scratch would introduce significant security surface area with no business
benefit. Supabase Auth provides a production-hardened implementation with
EU hosting options appropriate for UK GDPR compliance.

---

## 1.2 — JWT Token Flow

```
1. FRONTEND AUTHENTICATION
   User authenticates via Supabase Auth client library.
   Supabase issues a signed JWT (RS256, using Supabase's public/private key pair).
   The JWT contains:
     - sub: Supabase user UUID (stable identifier)
     - email: user's email address
     - exp: expiry timestamp
     - iat: issued-at timestamp
     - role: "authenticated" (for authenticated users)

2. API REQUEST
   Frontend includes JWT in every request:
     Authorization: Bearer <jwt_token>

3. API LAYER VERIFICATION
   The API layer verifies the JWT on every request:
     - Extract the token from the Authorization header
     - Verify the JWT signature using Supabase's public key (JWKS endpoint)
     - Verify exp (expiry) — reject if expired with HTTP 401
     - Extract the sub claim (Supabase user UUID)
     - Reject structurally invalid tokens with HTTP 401

4. USER IDENTITY RESOLUTION
   The verified Supabase user UUID (sub claim) is passed to UserService.
   UserService.get_or_create_user(supabase_auth_id) returns the platform
   user record, creating one on first login if necessary.
   The platform user UUID (our own UUID) is the identity used
   throughout the service and domain layers.

5. REQUEST CONTEXT
   The authenticated platform user UUID is injected into the request context.
   All service methods receive this UUID as an explicit parameter.
   No service method reads identity from global or thread-local state.
```

---

## 1.3 — What the Platform Does With the Identity

The platform receives a verified Supabase user UUID. It uses this to:

- Resolve the platform user record (`users.supabase_auth_id`)
- Verify resource ownership in service operations
- Populate `user_id` fields in audit events and snapshot records
- Scope all data queries to the authenticated user's resources

The platform does not:
- Reimplement JWT parsing or signature verification
- Store JWT tokens server-side
- Manage sessions or refresh tokens
- Store passwords or credentials of any kind

---

## 1.4 — Token Expiry and Refresh

Supabase Auth manages token lifetimes and refresh. The API layer verifies
only that a presented token is valid and not expired. It does not issue
new tokens, does not manage refresh flows, and does not maintain server-side
session state.

If a token expires mid-session, the API responds with HTTP 401. The frontend
uses Supabase Auth client libraries to handle refresh automatically.

---

## 1.5 — Future Authentication Extensions

The following authentication capabilities are not in Phase 1 but the
architecture accommodates them without structural change:

| Capability | Phase | Notes |
|---|---|---|
| OAuth (Google, Apple) | Phase 2+ | Supabase Auth built-in; no platform changes |
| Magic link / passwordless | Available from day 1 | Supabase Auth built-in |
| Multi-factor authentication | Phase 2+ | Supabase Auth built-in |
| SSO / SAML (enterprise) | Phase 4+ | Supabase Auth enterprise tier |
| API key authentication | Phase 3+ | For programmatic API access; separate key management layer |

All additions are configuration or extension of Supabase Auth. The platform's
own JWT verification layer does not change.

---

---

# Part 2 — Authorization Philosophy

---

## 2.1 — Simple Ownership Model, Strictly Enforced

Phase 1 uses the simplest authorization model that correctly serves a
single-user SaaS: ownership. Every resource belongs to exactly one user.
That user has full access to their resources. No other user can access them.

Simplicity in authorization is a security property, not a limitation.
A complex permission model that is difficult to reason about is more likely
to contain privilege escalation vulnerabilities than a simple one that is
easy to audit.

The model is: **you can access what you own, and nothing else.**

---

## 2.2 — Authorization Is Enforced at the Service Layer, Not Only the API Layer

The API layer provides a first line of defence (authentication verification,
coarse role checks on admin routes). The service layer provides the definitive
authorization enforcement (ownership verification on every operation that
touches user-owned data).

The reason for service-layer enforcement: the service layer is where the
domain operation happens. An authorization check in the API layer that is
not also present in the service layer can be bypassed by any code path that
reaches the service layer directly — a future background job, a management
command, a test fixture that calls services without going through routes.
Defense in depth means authorization is enforced where the operation happens.

---

## 2.3 — Non-Disclosure of Existence

A user who attempts to access a resource they do not own receives HTTP 404
(Not Found), not HTTP 403 (Forbidden). Returning 403 would confirm that the
resource exists. Returning 404 reveals nothing about whether the resource
exists at all.

This applies consistently across:
- Deal access by non-owner
- Property access by non-owner
- Snapshot access via a deal non-owner
- Investor profile access by non-owner

The only resource type where 403 is correct is admin-only routes, where
the user is authenticated (their identity is confirmed) but lacks admin
status (their role is insufficient). In this case, the existence of the
endpoint is not a secret — it is a documented admin capability.

---

## 2.4 — Authorization Decisions Are Explicit, Not Implicit

Every service method that accesses user-owned data explicitly passes the
authenticated `user_id` to the ownership-filtered repository variant. There
is no implicit "current user" context or request-scoped security principal
that is automatically applied. The authorization check is visible in the
code at the point where it matters.

This makes authorization auditable: looking at any service method, you can
immediately see whether it performs an ownership check and exactly how.

---

## 2.5 — Configuration Data Is Not User-Owned

SDLT rates, Corporation Tax rates, and assumption defaults are platform-level
resources. They are readable by all authenticated users. They are writable
only by admin users. They have no concept of user ownership.

This is not a security gap — configuration data is intended to be transparent.
Users should be able to see which SDLT rates are in effect and which assumptions
the platform applies by default. Transparency in configuration is part of
the trust model.

---

---

# Part 3 — Ownership Model

---

## 3.1 — Resource Ownership Map

Every user-owned resource stores a `user_id` (FK to the `users` table)
that is set at creation time and never changes.

```
Resource                    Owner field      Ownership established
────────────────────────────────────────────────────────────────────────
User                        (self)           On creation
InvestorProfile             user_id          On creation
Property                    user_id          On creation
Deal                        user_id          On creation
CalculationSnapshot         user_id          On creation (denormalised)
CalculationAuditEvent       user_id          On creation (denormalised)
```

Configuration entities (SDLT, CT, Assumption versions) have no `user_id`.
They are platform-level, not user-level.

---

## 3.2 — Snapshot Ownership Is Mediated Through the Deal

A `CalculationSnapshot` stores `user_id` as a denormalised field for audit
purposes. But snapshot access is always mediated through the parent deal:
a user may access a snapshot only if they own the deal it belongs to.

The authorization check is:
```
1. Load snapshot by snapshot_id
2. Load the snapshot's parent deal by deal_id
3. Verify the deal's user_id matches the requesting user_id
4. If not: return NotFound (never Forbidden)
```

Direct snapshot access without the deal ownership check is not permitted.

---

## 3.3 — Property Ownership Is a Prerequisite for Deal Creation

A deal may only be created against a property that the creating user owns.
The deal creation service verifies property ownership before creating the
deal. A user cannot create a deal against another user's property.

This check is necessary because the `property_id` FK on the deal does not
automatically enforce user ownership — the database allows any valid UUID.
Service-layer ownership verification is the enforcement mechanism.

---

## 3.4 — Ownership Is Immutable

Once established, `user_id` on any resource cannot change. This is both
a domain invariant (DOMAIN_MODEL_ARCHITECTURE.md I-04) and an authorization
invariant. Ownership transfer between users is not supported in Phase 1
and is not designed for in later phases.

If a resource needs to be shared between users (e.g. a team account accesses
a deal), this is modelled as explicit access grants in Phase 2 (see Part 10),
not as ownership transfer.

---

---

# Part 4 — User Roles

Phase 1 defines two roles. The role model is intentionally minimal.

---

## 4.1 — Role: standard_user

**Assignment:** Every authenticated user who has a platform account.

**How assigned:** Created automatically on first login via Supabase Auth.
There is no self-service mechanism to elevate to admin.

**Capabilities:**
- Full CRUD on their own Properties
- Full CRUD on their own Deals (within lifecycle rules)
- Full CRUD on their own Investor Profiles
- Trigger calculations on their own Deals
- Read their own Snapshots and calculation history
- Read all active configuration versions (read-only transparency access)

**Restrictions:**
- No access to any resource owned by another user
- No write access to configuration tables
- No access to platform-wide audit data
- No ability to suspend or manage other users

---

## 4.2 — Role: platform_admin

**Assignment:** Explicitly provisioned by a platform operator. Not
self-assignable. Provisioning in Phase 1 is a direct database operation
on the `users` table (setting an admin flag) performed by a developer
or operator with database access.

**Carries standard_user capabilities plus:**
- Insert new configuration versions (SDLT, CT, Assumption)
- Insert new engine version registry entries
- Read platform-wide calculation audit history
- Suspend and reactivate user accounts
- Read any user's snapshot for audit purposes (admin-only operation,
  logged to server audit trail)

**What admin cannot do:**
- Modify or delete any snapshot record
- Modify or delete any configuration version record
- Delete any user account or their data (GDPR process only, Phase 2)
- Override or manually alter engine outputs

**Admin identity persistence:**
The `users` table holds an `is_admin` boolean column (Phase 1 implementation).
Phase 2 may introduce a more formal role assignment mechanism if admin
capability needs to be more granular.

---

## 4.3 — There Are No Other Roles in Phase 1

The following roles are explicitly deferred:

| Deferred Role | Phase | Description |
|---|---|---|
| team_member | Phase 2 | Member of a shared team account with delegated access |
| team_admin | Phase 2 | Can invite members and manage team deal access |
| advisor | Phase 2 | Read-only access to a client's deals by invitation |
| api_client | Phase 3 | Programmatic API access via API key |
| enterprise_admin | Phase 4 | Multi-organisation administration |

None of these require Phase 1 structural changes beyond what is already
designed. The role and permission model is designed to accommodate them
additively.

---

---

# Part 5 — Permission Matrix

---

## 5.1 — Phase 1 Permission Matrix

The following matrix defines what each role may do with each resource.
Operations are: CREATE, READ_OWN, READ_ANY, UPDATE, DELETE (physical),
ARCHIVE (soft), and TRIGGER (for calculation operations).

```
Resource / Operation                    standard_user   platform_admin
────────────────────────────────────────────────────────────────────────
USER (own record)
  READ own profile                           ✓               ✓
  UPDATE own display_name                    ✓               ✓
  READ any user profile                      ✗               ✓ (admin view only)
  SUSPEND / REACTIVATE user                  ✗               ✓

INVESTOR_PROFILE
  CREATE (own)                               ✓               ✓
  READ own                                   ✓               ✓
  UPDATE own                                 ✓               ✓
  ARCHIVE own                                ✓               ✓
  READ another user's profiles               ✗               ✗ (not required even for admin)

PROPERTY
  CREATE (own)                               ✓               ✓
  READ own (active)                          ✓               ✓
  READ own (archived)                        ✓               ✓
  UPDATE own (mutable fields)                ✓               ✓
  ARCHIVE own                                ✓               ✓
  READ another user's properties             ✗               ✗ (not required even for admin)

DEAL
  CREATE (own)                               ✓               ✓
  READ own (DRAFT/ANALYSED)                  ✓               ✓
  READ own (ARCHIVED)                        ✓               ✓
  UPDATE working inputs (own)                ✓               ✓
  ARCHIVE own                                ✓               ✓
  READ another user's deals                  ✗               ✗ (not required even for admin)

CALCULATION_SNAPSHOT
  TRIGGER calculation on own deal            ✓               ✓
  READ own snapshots (display level)         ✓               ✓
  READ own snapshots (full with intermediates) ✓             ✓
  READ any user's snapshot (admin audit)     ✗               ✓ (logged)
  MODIFY any snapshot field                  ✗               ✗ (nobody)
  DELETE any snapshot                        ✗               ✗ (nobody)

CONFIGURATION (SDLT / CT / Assumptions)
  READ active versions                       ✓               ✓
  READ all historical versions               ✓               ✓
  INSERT new version                         ✗               ✓
  UPDATE existing version                    ✗               ✗ (nobody)
  DELETE existing version                    ✗               ✗ (nobody)

AUDIT_LOG (calculation history)
  READ own calculation history               ✓               ✓
  READ any user's calculation history        ✗               ✓ (admin audit)
  INSERT audit event                         System only     System only
  UPDATE / DELETE audit event                ✗               ✗ (nobody)
```

---

## 5.2 — The "Nobody" Operations

Several operations are marked ✗ for all roles, including platform_admin.
These are not access gaps — they are intentional permanent restrictions.

```
MODIFY snapshot fields (except is_superseded):
  Enforced by: database column-level grants; application-layer INSERT-only
  Reason: snapshot immutability is a trust invariant, not an access control

DELETE snapshots:
  Enforced by: no DELETE privilege on snapshot tables for any application role
  Reason: historical reproducibility requires permanent retention

UPDATE configuration versions:
  Enforced by: database INSERT-only grants on config tables
  Reason: configuration versioning requires append-only records

DELETE configuration versions:
  Enforced by: no DELETE privilege; ON DELETE RESTRICT foreign keys
  Reason: historical snapshots reference configuration by FK; deletion
          would destroy reproducibility
```

These restrictions cannot be overridden by any user action, admin action,
or application code path. They are enforced at the database privilege level,
not just the application level.

---

---

# Part 6 — Resource Access Rules

These rules define the specific access control logic applied for each
resource type.

---

## 6.1 — Property Access Rules

```
RULE P-01: A user may only access (read or write) properties they own.
    Enforcement: PropertyRepository.find_by_id_for_user(property_id, user_id)
    Return on failure: None (service raises NotFoundError → HTTP 404)

RULE P-02: Property tenure cannot be changed after creation.
    Enforcement: PropertyService.update() does not accept tenure as an updatable field.
    The repository update operation does not include tenure in UPDATE columns.

RULE P-03: An archived property cannot be unarchived.
    Enforcement: PropertyService enforces via lifecycle rule.
    Once is_archived = true, no service method sets it back to false.

RULE P-04: A property can only be archived if it belongs to the requesting user.
    Enforcement: ownership check before archival operation.
```

---

## 6.2 — Deal Access Rules

```
RULE D-01: A user may only access deals they own.
    Enforcement: DealRepository.find_by_id_for_user(deal_id, user_id)

RULE D-02: A deal can only be created against a property the user owns.
    Enforcement: DealService verifies property ownership before deal creation.

RULE D-03: An archived deal cannot have its working inputs updated or
    calculations triggered.
    Enforcement: DealService and CalculationService check deal.status != ARCHIVED.

RULE D-04: A deal's user_id and property_id cannot be changed after creation.
    Enforcement: DealRepository.update() does not accept user_id or
    property_id as updatable fields.

RULE D-05: An archived deal cannot be unarchived.
    Enforcement: DealStatusTransitionService rejects ARCHIVED → any transition.
```

---

## 6.3 — Snapshot Access Rules

```
RULE S-01: Snapshot access is mediated through deal ownership.
    A user may access a snapshot only if they own the deal it belongs to.
    Enforcement: SnapshotService verifies deal ownership (via DealRepository)
    before returning any snapshot data.

RULE S-02: No snapshot data may be modified by any user action.
    Enforcement: SnapshotRepository exposes no update operations except
    mark_superseded (is_superseded flag only).

RULE S-03: Snapshots cannot be deleted by any user action.
    Enforcement: No delete operation exists in any repository or service.
    Database DELETE privileges are not granted to the application user.

RULE S-04: Snapshot intermediates are accessible to the snapshot's owner.
    Full snapshot loading (including intermediates) is accessible to the
    deal owner. There is no partial restriction on intermediates within
    an owned snapshot.

RULE S-05: Admin snapshot access is logged.
    When platform_admin accesses a snapshot not belonging to their own
    account (for audit purposes), this access is recorded in the server-side
    audit trail. This is an operational concern, not a database constraint.
    Phase 1 logs this at the application level. Phase 2 may introduce a
    formal admin access log.
```

---

## 6.4 — Investor Profile Access Rules

```
RULE IP-01: A user may only access investor profiles they own.
    Enforcement: InvestorProfileRepository.find_by_id_for_user(profile_id, user_id)

RULE IP-02: An investor profile is informational for deal creation only.
    Snapshots do not reference profiles by FK. Profile changes after
    snapshot creation do not affect historical snapshots.
    Enforcement: Domain design — snapshot stores copied values, not FK references.

RULE IP-03: Profile archival does not affect existing deals or snapshots.
    Enforcement: The FK from deals.investor_profile_id is nullable. Archiving
    a profile does not trigger any cascade behaviour on deals.
```

---

## 6.5 — Configuration Access Rules

```
RULE C-01: All authenticated users may read all configuration versions.
    Configuration transparency is a trust requirement (TRUST_MODEL.md).
    Users must be able to see which rates and assumptions the platform uses.
    Enforcement: ConfigurationService read methods have no user_id parameter.

RULE C-02: Only platform_admin may insert new configuration versions.
    Enforcement: API layer verifies admin role before delegating to admin
    configuration service. Service layer does not perform a second role check.

RULE C-03: No user may modify or delete configuration versions.
    Enforcement: Database-level INSERT-only grants on config tables.
    No service method exposes update or delete operations on configuration.

RULE C-04: Configuration version inserts are recorded in the admin audit log.
    Enforcement: Phase 2+ — admin configuration service writes to
    audit_config_changes table on every configuration insert.
    Phase 1: server-side logging only.
```

---

---

# Part 7 — Admin Boundaries

---

## 7.1 — What Admin Access Is and Is Not

Admin access grants the ability to perform platform operations that
affect all users: configuration management, user status management, and
audit visibility. It is not a backdoor to user data.

The distinction is critical:
- Platform admin **can** insert a new SDLT rate table
- Platform admin **cannot** modify a user's deal assumptions
- Platform admin **can** suspend a user account
- Platform admin **cannot** read or modify a user's investor profiles
- Platform admin **can** view any snapshot for audit purposes
- Platform admin **cannot** modify any snapshot field

Admin authority operates on platform-level concerns, not user-level data.

---

## 7.2 — Admin Routes Are a Separate API Namespace

Admin operations use a distinct route prefix: `/api/v1/admin/`. This
separation makes the admin API surface explicit and auditable. Standard
user routes are under `/api/v1/`.

```
Standard user routes:
    /api/v1/properties/
    /api/v1/deals/
    /api/v1/calculations/
    /api/v1/snapshots/
    /api/v1/users/me/         (own profile only)
    /api/v1/config/           (read-only — any authenticated user)

Admin-only routes:
    /api/v1/admin/config/     (write new config versions)
    /api/v1/admin/users/      (user status management)
    /api/v1/admin/audit/      (platform-wide audit access)
```

---

## 7.3 — Admin Check at the API Layer

The admin role check for admin-only routes occurs at the API layer:

```
1. Extract user_id from verified JWT (same as all requests)
2. Load the platform user record by user_id
3. Check user.is_admin == True
4. If False: return HTTP 403 Forbidden
5. If True: proceed to service delegation
```

This is one of the two contexts where HTTP 403 is correct (the other is
a SUSPENDED user attempting to authenticate — though in practice Supabase
Auth handles this via token invalidation).

The admin check at the API layer is the appropriate layer for this check
because it is a coarse role check on the entire route, not a resource
ownership check. The service layer may additionally confirm admin context
for sensitive admin operations as an additional safeguard.

---

## 7.4 — Admin Provisioning in Phase 1

Admin status is assigned by direct database operation in Phase 1:

```
UPDATE users SET is_admin = TRUE WHERE supabase_auth_id = '<admin_supabase_id>';
```

This is intentionally manual. In Phase 1, there are expected to be one or
two platform admins (the development team). A self-service admin assignment
mechanism would create unnecessary attack surface.

Phase 2 will introduce an admin management UI accessible only to existing
admins, following the principle that only admins can make admins.

---

## 7.5 — Admin Is Not a Superuser

Platform admin is a defined, bounded set of capabilities. It is not
unlimited access to everything. The "nobody" operations in Part 5.2
apply to platform_admin as much as to standard_user.

An admin who attempts to modify a snapshot will receive the same database
constraint violation as any other code path attempting that operation.
Admin status does not override database-level immutability enforcement.

---

---

# Part 8 — Service-Layer Authorization Enforcement

---

## 8.1 — Ownership Verification Pattern

The standard pattern for ownership verification is defined in
APPLICATION_SERVICE_ARCHITECTURE.md Part 10. It is reproduced here as
the authoritative reference for implementation:

```
CORRECT PATTERN — returns None for both "not found" and "wrong owner":

def get_resource_or_raise(resource_id: UUID, user_id: UUID, repository) → Resource:
    resource = repository.find_by_id_for_user(resource_id, user_id)
    if resource is None:
        raise NotFoundError(entity="resource_type", id=resource_id)
    return resource
```

```
INCORRECT PATTERN — never use:

def get_resource_or_raise(resource_id: UUID, user_id: UUID, repository) → Resource:
    resource = repository.find_by_id(resource_id)    # finds any user's resource
    if resource is None:
        raise NotFoundError(entity="resource_type", id=resource_id)
    if resource.user_id != user_id:
        raise ForbiddenError()    # DISCLOSES EXISTENCE — wrong
    return resource
```

The difference: the incorrect pattern discloses existence (returns 403 which
confirms the resource exists). The correct pattern uses the repository's
ownership-aware variant which never distinguishes the two failure modes.

---

## 8.2 — Authorization Is Applied Before Any Business Logic

For every service method, ownership verification is the first substantive
operation. Business logic (calculation, update, archival) only executes
after ownership is confirmed.

```
Service method structure:

1. AUTHORISE           ← first, always
2. DOMAIN CHECK        ← second (status transition validity, etc.)
3. LOAD DEPENDENCIES   ← third
4. EXECUTE OPERATION   ← fourth
5. PERSIST             ← fifth
6. RETURN              ← last
```

This ordering is mandatory. A service method that performs business logic
before ownership verification has an authorization defect.

---

## 8.3 — Calculation Authorization

Triggering a calculation requires ownership of the deal. The ownership
check in `CalculationService.run_calculation` is the first operation after
receiving the request:

```
deal = DealRepository.find_by_id_for_user(deal_id, user_id)
if deal is None:
    raise NotFoundError(entity="deal", id=deal_id)
```

If this check passes, all subsequent operations in the calculation flow
are authorized: the deal belongs to the user, the snapshot will be created
for that deal, and the audit event will record that user's action.

---

## 8.4 — Snapshot Access Authorization

Snapshot access is always verified through the parent deal. The pattern
used in `SnapshotService.get_full_snapshot`:

```
snapshot = SnapshotRepository.find_by_id_outputs_only(snapshot_id)
if snapshot is None:
    raise NotFoundError(entity="snapshot", id=snapshot_id)

# Verify ownership through the deal
deal = DealRepository.find_by_id_for_user(snapshot.deal_id, user_id)
if deal is None:
    raise NotFoundError(entity="snapshot", id=snapshot_id)  # same error; no disclosure
```

The second `NotFoundError` uses `snapshot_id` (not `deal_id`) as the
identifier in the error, so the caller sees a 404 for the snapshot they
requested without any information about the deal.

---

## 8.5 — The is_superseded Mutation Authorization

The `mark_superseded` operation on a snapshot is called by `CalculationService`
after it has already verified ownership of the deal (via the preceding
ownership check in `run_calculation`). Supersession marking does not
require a separate ownership check because:

1. Supersession is triggered by the same `CalculationService.run_calculation`
   call that already verified deal ownership.
2. The snapshot being superseded belongs to the same deal (enforced by
   the snapshot's `deal_id` FK).
3. The only field changed is `is_superseded` — no calculation data is altered.

---

## 8.6 — Configuration Operations Authorization

For write operations on configuration (admin only):

```
The API layer verifies admin status via user.is_admin before delegating.
The service layer does not perform a second admin check.
```

For read operations on configuration (any authenticated user):

```
No ownership check. ConfigurationService methods have no user_id parameter.
Configuration data is intentionally public to all authenticated users.
```

---

---

# Part 9 — API-Layer Authorization Enforcement

---

## 9.1 — Two Layers of Authorization Check

The API layer performs two authorization checks before delegating to
the service layer:

**Layer 1 — Authentication verification (every request):**
Verify the JWT is present, structurally valid, and not expired. Extract
the Supabase user UUID. Reject with HTTP 401 if verification fails.

**Layer 2 — Role check (admin routes only):**
For routes under `/api/v1/admin/`, verify `user.is_admin == True`.
Reject with HTTP 403 if not admin. Standard user routes skip this check.

The service layer performs ownership verification (Layer 3) for user-owned
resources. This is not a third API layer check — it is service-layer
enforcement.

---

## 9.2 — Authentication as FastAPI Dependency

JWT verification is implemented as a FastAPI dependency injected into
every route. The dependency:

1. Extracts the Bearer token from the Authorization header
2. Verifies it using Supabase's JWKS endpoint
3. Extracts the `sub` claim (Supabase user UUID)
4. Calls `UserService.get_or_create_user()` to resolve the platform user
5. Returns the authenticated platform `User` object

If any step fails, the dependency raises an HTTP 401 exception before the
route handler executes.

This dependency is applied to all routes except `/api/v1/health/` (liveness
check, no auth needed) and Supabase Auth callback endpoints.

---

## 9.3 — Admin Check as FastAPI Dependency

Admin route authorization is implemented as an additional FastAPI dependency
that wraps the authentication dependency:

1. Runs authentication dependency (verifying JWT, resolving user)
2. Checks `user.is_admin == True`
3. If False: raises HTTP 403 with `{ "error": "FORBIDDEN" }`
4. If True: returns the admin user object

Admin routes declare both dependencies. Standard user routes declare only
the authentication dependency.

---

## 9.4 — What the API Layer Does Not Do

The API layer does not:
- Check resource ownership (that is the service layer)
- Validate calculation inputs (that is the engine)
- Check deal status (that is the service layer)
- Know about snapshot creation or configuration resolution
- Return different errors for "not found" vs "not yours" — it receives
  NotFoundError from the service layer and maps it to HTTP 404 uniformly

The API layer is a thin translation layer between HTTP and the service layer.
Authorization enforcement at the API layer is limited to authentication
verification and coarse admin role checks.

---

## 9.5 — HTTP Response Codes for Authorization Outcomes

```
Condition                                           HTTP Status
─────────────────────────────────────────────────   ────────────
No Authorization header                              401
Invalid or malformed JWT                             401
Expired JWT                                          401
Valid JWT, user exists, standard route               → proceed
Valid JWT, user is SUSPENDED                         401 (Supabase handles via token invalidation)
Valid JWT, admin route, user.is_admin = False        403
Valid JWT, resource not found (any reason)           404
  (includes: not found + belongs to another user)
```

---

---

# Part 10 — Future Enterprise Extension Points

These extension points are designed here to ensure Phase 1 decisions do
not create structural obstacles to future authorization requirements.

---

## 10.1 — Team Accounts (Phase 2)

Team accounts allow multiple users to share access to a set of deals and
properties. This introduces a new authorization concern: delegated access
within an ownership boundary.

**Design approach:**
A team is a new domain entity that owns properties and deals. Users are
members of teams with defined roles (team_admin, team_member, read_only).
Resource ownership on `properties` and `deals` gains a nullable `team_id`
alongside `user_id`.

```
Access rule:
  A user may access a resource if:
    (resource.user_id == user.id)          ← personal ownership
    OR
    (resource.team_id IN user.team_ids     ← team membership
     AND user's team_role grants this operation)
```

**Service layer impact:**
Ownership verification methods gain a team membership check alongside
the user ownership check. The repository layer gains a team-aware query
variant. Existing `find_by_id_for_user` methods continue to work for
personally-owned resources unchanged.

**Phase 1 compatibility:**
The Phase 1 schema accommodates this by having `user_id` as a required
field today. In Phase 2, `team_id` is added as a nullable field. Resources
without a `team_id` are personal. Resources with a `team_id` are team-owned.
The transition is additive.

---

## 10.2 — Advisor Access (Phase 2)

An advisor is a user granted read-only access to a specific client's deals
by the client's explicit invitation. This is a cross-user access grant,
distinct from team membership.

**Design approach:**
An `access_grant` table records explicit read-only access:

```
access_grants:
    id
    grantor_user_id    (the resource owner)
    grantee_user_id    (the advisor)
    resource_type      (DEAL, PROPERTY)
    resource_id
    permission         (READ_ONLY)
    expires_at         (nullable)
    created_at
```

The authorization check for advisor access:

```
A user may read a resource if:
    (resource.user_id == user.id)           ← personal ownership
    OR
    (access_grant exists for grantee=user.id,
     resource_id=resource.id,
     permission=READ_ONLY,
     not expired)
```

Advisors cannot trigger calculations, update inputs, or see intermediates
(only display-level summary). The permission level in the grant controls
which service operations are available.

---

## 10.3 — API Key Authentication (Phase 3)

For programmatic API access by property professionals building on top of
the platform.

**Design approach:**
API keys are a separate credential type, not Supabase JWTs. An API key
identifies a user (or a team in Phase 2) and has its own rate limits and
scope restrictions.

```
api_keys:
    id
    user_id            (or team_id in Phase 2)
    key_hash           (stored as bcrypt hash; never as plaintext)
    key_prefix         (first 8 chars; shown to user for identification)
    scopes             (list: READ_DEALS, TRIGGER_CALCULATIONS, etc.)
    rate_limit_per_hour
    expires_at         (nullable)
    last_used_at
    is_active
    created_at
```

The API layer gains a second authentication pathway: when no Bearer JWT is
present but an `X-API-Key` header is, the key is validated against the
hashed values in `api_keys`. The resulting user identity is identical to
JWT authentication from the service layer's perspective.

The same service-layer authorization model applies: ownership verification,
NotFoundError for non-owned resources, etc. API keys do not grant additional
capabilities beyond what the user who created them has.

---

## 10.4 — Enterprise SSO and Organisation Accounts (Phase 4)

Enterprise customers may require:
- SAML-based SSO authentication
- Multi-organisation management
- Organisation-level admin roles separate from platform admin
- Bulk user provisioning via SCIM

**Design approach:**
Supabase Auth supports SAML SSO at the enterprise tier. Organisation-level
management extends the team account model with an organisation entity above
teams. Platform admin at the organisation level is a separate role from the
platform-wide `platform_admin`.

Phase 1 and Phase 2 designs do not foreclose this. The user and team
structures are additive layers. Organisation-level authorization extends
the team membership check to include organisation scope.

---

## 10.5 — Row-Level Security (Future Option)

PostgreSQL Row-Level Security (RLS) provides database-level enforcement of
per-row access rules. Supabase uses RLS extensively in its managed clients.

The current PropIQ authorization model enforces ownership at the service
layer, not via RLS. This is intentional for Phase 1 — RLS adds policy
complexity that is difficult to audit and debug, and the service-layer
pattern is sufficient and explicit.

If Phase 2+ introduces team or organisation accounts where the ownership
boundary becomes significantly more complex, RLS on key tables (deals,
properties) may provide an additional defence-in-depth layer. This would
be an additive enforcement layer, not a replacement for service-layer checks.

---

---

# Part 11 — Authorization Invariants

These invariants govern the authorization model. Any implementation
violating them introduces a security defect.

```
AZ-01  JWT verification occurs on every API request to protected routes.
       No route under /api/v1/ (except /health and auth callbacks) is
       accessible without a valid, non-expired JWT.

AZ-02  User identity is extracted from the verified JWT sub claim.
       The sub claim is the Supabase user UUID.
       The platform resolves this to its own user UUID via supabase_auth_id.
       No other JWT claim is used as an identity.

AZ-03  All service methods that access user-owned resources accept user_id
       as an explicit parameter.
       No service method reads identity from global state or thread-local context.

AZ-04  The ownership-filtered repository variant is used for all external
       service operations on user-owned resources.
       find_by_id_for_user is the correct method; find_by_id is for
       internal operations where ownership is already established by context.

AZ-05  NotFoundError is raised for both "not found" and "owned by another user."
       ForbiddenError is never raised for user-owned resources.
       Existence is not disclosed to non-owners.

AZ-06  ForbiddenError (HTTP 403) is raised only for authenticated users
       attempting admin-only routes without admin status.
       It is never raised for resource access attempts.

AZ-07  Ownership check is the first operation in every service method that
       accesses user-owned data. Business logic executes only after ownership
       is confirmed.

AZ-08  Admin role check is performed at the API layer for admin-only routes.
       Admin status does not override database-level immutability constraints.
       Admin cannot modify snapshots or configuration records.

AZ-09  Configuration data is readable by all authenticated users.
       Configuration write operations require platform_admin role.
       No user_id parameter exists on configuration read operations.

AZ-10  Snapshot access is always mediated through deal ownership.
       No direct snapshot access without deal ownership verification.

AZ-11  User ownership (user_id on resources) is set at creation and never
       modified. Ownership transfer is not supported.

AZ-12  Admin provisioning is a manual database operation in Phase 1.
       There is no self-service path to admin status.
       Only existing admins may grant admin status (Phase 2+).

AZ-13  The "nobody" operations (snapshot modification, snapshot deletion,
       configuration record modification) are enforced at the database
       privilege level, not only at the application level.
       These restrictions apply to platform_admin as much as standard_user.

AZ-14  AI services are read-only consumers of data.
       No AI service operation requires or uses elevated privileges.
       AI summaries reference snapshots by FK but write only to ai_summaries.
       This is enforced by the absence of write operations on snapshot or
       calculation tables from any AI service code path.

AZ-15  Phase 2+ team and advisor access models are additive extensions.
       They extend the authorization model; they do not replace it.
       Personal ownership checks continue to work unchanged.
```
