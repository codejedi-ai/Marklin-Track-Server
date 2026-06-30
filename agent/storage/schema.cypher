// =============================================================================
// CMDB Knowledge Graph — Neo4j schema + MERGE templates
// Apply once on startup (idempotent). See docs/graph_model.md for rationale.
// =============================================================================

// ----------------------------------------------------------------------------
// 1. Uniqueness constraints (these also create the indexes MERGE relies on)
// ----------------------------------------------------------------------------
CREATE CONSTRAINT device_id   IF NOT EXISTS FOR (d:Device)     REQUIRE d.device_id IS UNIQUE;
CREATE CONSTRAINT user_uid    IF NOT EXISTS FOR (u:User)       REQUIRE u.uid IS UNIQUE;
CREATE CONSTRAINT app_name    IF NOT EXISTS FOR (a:App)        REQUIRE a.name_norm IS UNIQUE;
CREATE CONSTRAINT loc_name    IF NOT EXISTS FOR (l:Location)   REQUIRE l.name IS UNIQUE;
CREATE CONSTRAINT dept_name   IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT team_name   IF NOT EXISTS FOR (t:Team)       REQUIRE t.name IS UNIQUE;

// ----------------------------------------------------------------------------
// 2. Secondary indexes (resolution lookups + /ask query support)
// ----------------------------------------------------------------------------
CREATE INDEX user_email    IF NOT EXISTS FOR (u:User)   ON (u.email);
CREATE INDEX user_empid    IF NOT EXISTS FOR (u:User)   ON (u.employee_id);
CREATE INDEX device_host   IF NOT EXISTS FOR (d:Device) ON (d.hostname);
CREATE INDEX app_appid     IF NOT EXISTS FOR (a:App)    ON (a.app_id);


// =============================================================================
// MERGE TEMPLATES  (parameterized; $param values supplied by the ingest layer
// AFTER normalization + identity resolution). These are the patterns the
// /ingest pipeline emits — included here as the contract between code and graph.
// =============================================================================

// --- Device: create-or-enrich on stable device_id -------------------------
// ON CREATE sets first-seen provenance; ON MATCH only updates last_updated.
// Property SET uses coalesce so a richer source never gets overwritten by null.
// MERGE (d:Device {device_id: $device_id})
//   ON CREATE SET d._first_seen = datetime(), d._sources = [$source]
//   ON MATCH  SET d._sources = CASE WHEN $source IN d._sources
//                                   THEN d._sources ELSE d._sources + $source END
//   SET d._last_updated = datetime(),
//       d.hostname        = coalesce($hostname, d.hostname),
//       d.ip_address      = coalesce($ip_address, d.ip_address),
//       d.os              = coalesce($os, d.os),               // normalized
//       d.os_version      = coalesce($os_version, d.os_version),
//       d.status          = coalesce($status, d.status),       // normalized enum
//       d.encryption      = coalesce($encryption, d.encryption),// bool
//       d.serial_number   = coalesce($serial_number, d.serial_number),
//       // last_checkin: keep the most recent
//       d.last_checkin    = CASE WHEN d.last_checkin IS NULL
//                                 OR datetime($last_checkin) > datetime(d.last_checkin)
//                            THEN $last_checkin ELSE d.last_checkin END;

// --- User: MERGE on the resolved synthetic uid ----------------------------
// $uid is decided by the identity-resolution step (employee_id > email > similarity).
// MERGE (u:User {uid: $uid})
//   ON CREATE SET u._first_seen = datetime(), u._sources = [$source]
//   ON MATCH  SET u._sources = CASE WHEN $source IN u._sources
//                                   THEN u._sources ELSE u._sources + $source END
//   SET u._last_updated = datetime(),
//       u.name        = coalesce($name, u.name),
//       u.email       = coalesce($email, u.email),
//       u.employee_id = coalesce($employee_id, u.employee_id),
//       u.mfa_enabled = coalesce($mfa_enabled, u.mfa_enabled),
//       u.last_login  = coalesce($last_login, u.last_login),
//       u.status      = coalesce($status, u.status),
//       u.groups      = CASE WHEN $groups IS NULL THEN u.groups
//                            ELSE apoc.coll.toSet(coalesce(u.groups,[]) + $groups) END;

// --- App: MERGE on normalized name; references create stubs, inventory enriches
// MERGE (a:App {name_norm: $name_norm})
//   ON CREATE SET a._first_seen = datetime(), a.name = $name, a._stub = true
//   SET a._last_updated = datetime(),
//       a.app_id      = coalesce($app_id, a.app_id),
//       a.vendor      = coalesce($vendor, a.vendor),
//       a.app_type    = coalesce($app_type, a.app_type),
//       a.users_count = coalesce($users_count, a.users_count),
//       a.sso_enabled = coalesce($sso_enabled, a.sso_enabled),
//       // arrival of inventory data clears the stub flag
//       a._stub = CASE WHEN $app_id IS NULL THEN a._stub ELSE false END;

// --- Relationships: idempotent edges, with their own provenance ------------
// Device ownership
// MATCH (d:Device {device_id:$device_id}), (u:User {uid:$uid})
// MERGE (d)-[r:ASSIGNED_TO]->(u)
//   ON CREATE SET r._first_seen = datetime(), r._sources = [$source];

// App usage (User -> App), stub-creating the app if unseen
// MATCH (u:User {uid:$uid})
// MERGE (a:App {name_norm:$app_name_norm})
//   ON CREATE SET a.name = $app_name, a._stub = true, a._first_seen = datetime()
// MERGE (u)-[r:USES]->(a)
//   ON CREATE SET r._first_seen = datetime(), r._sources = [$source];

// App integration (App -> App)
// MATCH (a:App {name_norm:$src_norm})
// MERGE (b:App {name_norm:$dst_norm})
//   ON CREATE SET b.name = $dst_name, b._stub = true
// MERGE (a)-[r:INTEGRATES_WITH]->(b)
//   ON CREATE SET r._first_seen = datetime(), r._sources = [$source];

// Dimension links
// MATCH (d:Device {device_id:$device_id})
// MERGE (l:Location {name:$location}) MERGE (d)-[:LOCATED_AT]->(l);
// MERGE (dep:Department {name:$department}) MERGE (d)-[:BELONGS_TO]->(dep);


// =============================================================================
// EXAMPLE /ask TRANSLATIONS (text -> Cypher; the small fixed schema makes this
// reliable and keeps answers grounded in real data)
// =============================================================================
// "Which users don't have MFA?"
//   MATCH (u:User) WHERE u.mfa_enabled = false RETURN u.name, u.email;
//
// "What is affected if Slack goes down?"
//   MATCH (a:App {name_norm:'slack'})<-[:USES]-(u:User) RETURN u.name;
//   MATCH (a:App {name_norm:'slack'})<-[:INTEGRATES_WITH]-(b:App) RETURN b.name;
//
// "Which devices are unencrypted?"
//   MATCH (d:Device) WHERE d.encryption = false OR d.encryption IS NULL RETURN d.hostname;
//
// "Show everything about John Doe"
//   MATCH (u:User {name:'John Doe'})-[r]-(n) RETURN u, r, n;
