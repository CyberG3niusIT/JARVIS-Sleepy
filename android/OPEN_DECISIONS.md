# Open architecture decisions

Real decisions that are out of scope for this branch to make unilaterally,
per the goal spec Sec.18. Each entry: the question, the options seen in the
web specification or the wider codebase, and what was built around it so
work could continue without blocking on an answer.

## 1. Sleepy transport, pairing and trust model

**Question.** How does the Android app actually discover, pair with and
authenticate a Sleepy instance (goal spec Sec.15)?

**What exists today.** The web UI ports the pairing *screen* only; no IP
scheme, pairing code format, QR payload, or certificate/key exchange is
specified anywhere in `src/components/jarvis/` or `src/lib/jarvis/`.

**Options seen in the wider ecosystem, not decided here:**
- Local-network discovery (mDNS/Bonjour) + a short-lived pairing code shown
  on the Sleepy side, similar to typical smart-home pairing flows.
- QR code carrying a signed pairing token (public key + one-time secret),
  scanned by the phone.
- Manual host/port entry plus a long-lived API token pasted by the user.

**What was built instead.** `core/runtime/SleepyRuntimeGateway` describes
only the connection *state* (`SystemState`, paired: Boolean) that the UI
needs. `RuntimesDemoSections.kt` ports the web reference's full abstract
pairing state machine (`SleepyPairingSection`), trust inspection and handoff
review as a clearly labelled Zustandsdemonstration - deliberately without a
pairing code, QR payload, IP address or certificate fingerprint anywhere, per
the web reference itself. No transport, discovery or crypto code exists;
`RuntimesScreen`'s baseline rows and the Sleepy rows on Start/System still
render `UNAVAILABLE` / `NOT_IMPLEMENTED`, matching the web baseline exactly.

## 2. Privacy enforcement rules per capability

**Question.** Which concrete capabilities does `PRIVACY` block, and which
additional ones does `PRIVACY_LOCK` block on top (goal spec Sec.14)? The web
Privacy screen states the *principle* ("PRIVACY blockiert geschützte
Wahrnehmungs- und Datenpfade. PRIVACY_LOCK kann zusätzlich Netzwerk-, Cloud-
und externe Tool-Pfade hart sperren.") but does not enumerate a rule table
mapping each `CapabilityRow` to the mode(s) that block it.

**What was built instead.** `core/privacy/PrivacyGate` is the single
architectural seam every feature must call before a privacy-sensitive
action. `StaticPrivacyGate.isAllowed()` currently returns `true`
unconditionally (matching the web prototype's un-bound state) rather than
guessing a rule table. The per-capability mapping is a product decision to
be authored from the real Privacy screen content, not invented here.

## 3. Real Android permission set and request flow

**Question.** The web Permissions screen names eight capability areas
(Bedienungshilfen, Benachrichtigungen, Mikrofon, Bildschirmzugriff, Kamera,
Dateien, Kontakte/Kommunikation, Standort - see
`PermissionModels.kt: permissionGroups`). Which exact Android permission
strings / special-access settings (`AccessibilityService`,
`MediaProjection`, `NotificationListenerService`, `RECORD_AUDIO`,
`READ_CONTACTS`, location permissions, and so on) back each row, and what is
the request sequence when several are needed for one action?

**What was built instead.** `core/runtime/PermissionGateway` exposes only
`isGranted(permission: String): Boolean`; `DesignStatePermissionGateway`
always returns `false`. `PermissionsScreen` shows the overall "Android-
Berechtigungen" status as `PERMISSION_REQUIRED` and each of the eight
individual access areas as an unbound design state ("Status nicht
gebunden"), matching the web reference exactly, without wiring a real
`ActivityResultContracts.RequestPermission` flow yet. The per-group detail
sheet's demo-state selector is a local Compose preview only, per the web
reference's own `DEMO_AREA_NOTE`.

## 4. Local model runtime binding (LiteRT-LM)

**Question.** Which LiteRT-LM Android integration (AAR, model format,
loading API) actually backs "Lokales Modell" / "Modell-Runtime", and where
do downloaded model files live on disk?

**What was built instead.** `core/runtime/LocalRuntimeGateway` exposes
`state` and `boundModelName` only; `DesignStateLocalRuntimeGateway` reports
`DESIGN_STATE` / `null`, matching `comparisonBaseline.runtimeBound = false`.
No LiteRT dependency was added, since adding one without an actual model
format decision would just be a placeholder dependency.
