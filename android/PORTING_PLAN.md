# Android Compose Port - Mapping Plan

Kurzes Mapping React/Web (`src/`) -> Kotlin/Compose (`android/`). Die
Web-Spezifikation unter `src/components/jarvis/` und `src/lib/jarvis/` bleibt
verbindliche Quelle fuer Inhalte, Reihenfolge und Verhalten. Diese Datei
dokumentiert nur die technische Uebersetzung, keine neuen Entscheidungen.

## Design tokens

| Web | Android |
|---|---|
| `src/lib/jarvis/tokens.ts` (`colorTokens`, `typeScale`, `spacing`, `radii`, `layout`, `duration`, `easing`, `zIndex`) | `core/designsystem/JarvisColor.kt`, `JarvisType.kt`, `JarvisDimens.kt`, `JarvisMotion.kt` |
| `src/lib/jarvis/ia.ts` (`SystemState`, `ExecutionLocation`, `PrivacyMode`, `NavTabId`, `productAreas`, `routingLadder*`) | `core/model/Ia.kt` (sealed/enum types + the same fixed lists as Kotlin `val`s) |
| `src/lib/jarvis/comparison.ts` (`comparisonBaseline`) | `core/model/ComparisonBaseline.kt` (design-state placeholder object, not runtime data) |

## Shared primitives

| Web component (`src/components/jarvis/`) | Compose composable |
|---|---|
| `primitives.tsx: StatusTag` | `JarvisStatusTag` |
| `primitives.tsx: ExecutionTag` | `JarvisExecutionTag` |
| `primitives.tsx: PrivacyTag` | `JarvisPrivacyTag` |
| `primitives.tsx: SectionHeader` | `JarvisSectionHeader` |
| `primitives.tsx: ListRow` | `JarvisListRow` |
| `primitives.tsx: ListGroup` | `JarvisListGroup` |
| `primitives.tsx: DesignStateBlock` | `JarvisDesignStateBlock` |
| `primitives.tsx: Divider` | `JarvisDivider` |
| `shell.tsx: TopAppBar` | `JarvisTopBar` |
| `shell.tsx: RuntimeStrip` | `JarvisRuntimeStrip` |
| `shell.tsx: BottomNav` | `JarvisBottomNavigation` |
| `controls.tsx: Button` | `JarvisButton` |
| `controls.tsx: Toggle` | `JarvisToggle` |
| `controls.tsx: TextInput` | `JarvisTextField` |
| `controls.tsx: BottomSheet` | `JarvisBottomSheet` |
| `controls.tsx: Dialog` | `JarvisDialog` |
| `controls.tsx: InlineNotice` | `JarvisInlineNotice` |
| `controls.tsx: LoadingState` | `JarvisLoadingState` |
| `controls.tsx: EmptyState` | `JarvisEmptyState` |
| `controls.tsx: ErrorState` | `JarvisErrorState` |
| `controls.tsx: PermissionRequiredState` | `JarvisPermissionRequiredState` |
| `controls.tsx: NotImplementedState` | `JarvisNotImplementedState` |
| `screens/detail-header.tsx: DetailHeader` | `JarvisDetailHeader` |
| `motion.tsx: ScreenTransition` | `AnimatedContent` (slide + fade, same durations/easings) |
| `motion.tsx: ValueTransition` | `AnimatedContent` keyed by value |
| `motion.tsx: SectionEnter` | `AnimatedVisibility` with per-index start delay |
| `prototype-state.tsx: PrototypeBanner/ActionResult/useActionResult` | `PrototypeNotice`, `PrototypeActionResult`, `rememberActionResult()` |

## Navigation / app shell

- `src/App.tsx` + `shell.tsx` bottom nav (`Start`, `Chat`, `System`, `Mehr`) ->
  a single flat Navigation Compose `NavHost` with 4 tab-root routes plus one
  route per detail screen, hosted in `JarvisAppShell` (Scaffold:
  `JarvisTopBar` + `JarvisRuntimeStrip` + content + `JarvisBottomNavigation`).
  Switching tabs pops back to that tab's own root instead of restoring saved
  state, so a detail screen never survives a tab change, matching the web
  reference's per-tab container unmount behaviour and the locked Back table.
- Automationen (`automations-screen.tsx` + `automation-editor.tsx`) is the one
  exception: like the web reference, the editor is not a separate nav route
  but a local Compose state swap inside `AutomationsScreen` (`editorSession`),
  so the in-progress draft never has to cross a navigation boundary. Its
  discard confirmation is a `JarvisDialog` shown from a `BackHandler` that
  fires while the editor is the active composable.

## Screens

Round 2 finished porting every interaction flow the web reference actually
specifies for these fifteen screens - including their `*-demo.tsx`
Zustandsdemonstration sections, which are locked UI, not optional filler.
What stays open is real backend/runtime/transport binding, tracked in
`OPEN_DECISIONS.md`, never the UI itself.

| Web screen | Compose screen | Status |
|---|---|---|
| `screens/start-screen.tsx` | `feature/start/StartScreen.kt` | ported |
| `screens/chat-screen.tsx` + `chat-attachment.tsx` | `feature/chat/ChatScreen.kt` + `ChatAttachment*.kt` | ported, including real file/image picking, ContentResolver-based validation and Coil preview |
| `screens/system-screen.tsx` (overview) | `feature/system/SystemOverviewScreen.kt` | ported |
| `screens/more-screen.tsx` (overview) | `feature/more/MoreOverviewScreen.kt` | ported |
| `screens/models-screen.tsx` + `models-demo.tsx` | `feature/system/ModelsScreen.kt` + `ModelsDemoSection.kt` + `ModelImportCatalog.kt` | ported, including the full demo state machine (load/unload/download/pause/resume/cancel/retry/delete), import wizard and catalog browser |
| `screens/agents-screen.tsx` | `feature/system/AgentsScreen.kt` | ported (agent model, safety bounds, empty running-tasks state, full demo-agent detail sheet with cancel/retry/fail-demo/error/tool-activity) |
| `screens/tools-screen.tsx` | `feature/system/ToolsScreen.kt` | ported (capability list, execution rules, read-only capability detail sheet) |
| `screens/permissions-screen.tsx` | `feature/system/PermissionsScreen.kt` | ported (eight access-area groups, detail sheet with why-needed/capabilities/demo-state selector) |
| `screens/privacy-screen.tsx` | `feature/system/PrivacyScreen.kt` | ported (mode selector, explain sheet, PRIVACY_LOCK/relax confirm dialogs, protected groups, guarantees) |
| `screens/runtimes-screen.tsx` + `runtimes-demo.tsx` | `feature/system/RuntimesScreen.kt` + `RuntimesDemoSections.kt` | ported, including Sleepy pairing state machine, trust inspection and handoff review; no real transport/pairing protocol, see OPEN_DECISIONS Sec.1 |
| `screens/device-screen.tsx` | `feature/system/DeviceScreen.kt` | ported (service section, Android capability list, device-info fields left "Nicht gebunden" exactly as specified) |
| `screens/diagnostics-screen.tsx` + `diagnostics-demo.tsx` | `feature/system/DiagnosticsScreen.kt` + `DiagnosticsDemoSection.kt` | ported, including severity/runtime filters, detail sheet and export-preview sheet |
| `screens/voice-screen.tsx` | `feature/more/VoiceScreen.kt` | ported (full labelled state machine + transition controls, Wake Word/STT/TTS configuration sheets) |
| `screens/memory-screen.tsx` | `feature/more/MemoryScreen.kt` | ported (layers/provenance/rules lists, empty baseline, full demo-entry detail sheet with confirm/correct/discard/supersede/provenance) |
| `screens/automations-screen.tsx` + `automation-editor.tsx` | `feature/more/AutomationsScreen.kt` + `AutomationEditorScreen.kt` | ported, including the full editor (steps, routine conditions with AND/ODER, schedule datetime/interval, validation, save/discard/delete, dirty-state back confirmation) |
| `screens/settings-screen.tsx` | `feature/more/SettingsScreen.kt` | ported |
| `screens/about-screen.tsx` | `feature/more/AboutScreen.kt` | ported |

Deferred, and only where real backend/runtime/transport binding is the
actual blocker (never the UI): Sleepy's transport/pairing protocol (Runtimes,
OPEN_DECISIONS Sec.1), the real permission-grant read (Permissions,
OPEN_DECISIONS Sec.3) and the LiteRT-LM binding (Modelle, OPEN_DECISIONS
Sec.4).

## State layering (goal spec Sec. 13)

Three explicit Kotlin layers, none of them a placeholder for the others:

1. `core/model` - immutable data classes mirroring the web design-state
   objects (`ComparisonBaseline`, `ProductArea`, `CapabilityRow`). Compile-time
   constants, not observable state.
2. `feature/*/*ViewModel` - `StateFlow<XUiState>` holding local Compose-only
   state (selected tab, open sheet, form input, `PrototypeActionResult`
   messages). Equivalent to the web prototype's `useState`.
3. `core/runtime` (interfaces only in Phase 1: `LocalRuntimeGateway`,
   `PermissionGateway`, `PrivacyGate`, `SleepyRuntimeGateway`) - the seam where
   real Android runtime/backend state will be bound later. Phase 1 ViewModels
   depend on these interfaces via Hilt but the only implementations provided
   are `DesignStateOnly` fakes that return the same fixed design-state values
   as the web baseline, never fabricated numbers.

## Lifecycle / process-death robustness

Every screen-local prototype state (drafts, open sheets, filters, demo
entries) uses `rememberSaveable`, not `remember`, so it survives both a
configuration change and full activity recreation (process death), not
rotation alone. The Automationen feature is the deepest case: the open
editor's draft, the local automation list and the open editor session
(`AutomationsScreen.kt`, `AutomationEditorScreen.kt`) all persist through a
single shared string codec (`AutomationModels.kt: encodeAutomationDraft` /
`decodeAutomationDraft`), because a plain `String` is unconditionally
Bundle-safe while a nested `List<List<Any>>` is not. Covered by
`app/src/test/kotlin/.../AutomationDraftCodecTest.kt` (round-trip for every
field, including nested steps/conditions and the list/session separators).

## Chat attachment size resolution

`ChatAttachment.kt: resolveAttachmentSize` is a thin Android wrapper (cursor
query, `AssetFileDescriptor`, content stream) around
`resolveAttachmentSizeFromSources`, the actual decision logic, which takes
plain values and an `InputStream`-opening lambda so it is unit-tested
directly (`ChatAttachmentTest.kt: ResolveAttachmentSizeFromSourcesTest`) -
without Robolectric or any Android framework type - covering: a known
cursor size, the descriptor-length fallback, an unknown size with a small
stream (exact byte count), a stream exactly at the 25 MiB per-file limit,
a stream over the limit (clamped to `MAX_FILE_BYTES + 1`), a stream that
throws while reading, and `openStream()` returning `null` - the last two
both resolve to `MAX_FILE_BYTES + 1`, never `0`, since `0` would let an
oversized file slip past the per-file and total budget checks in
`ChatViewModel.onAddFiles`. Preview URIs are only attached to a
`ChatAttachment` after this resolved size has passed both budget checks.

## Privacy

`PrivacyGate` (`core/privacy/PrivacyGate.kt`) is the single interface every
feature module must go through to check whether an action is allowed under
`NORMAL` / `PRIVACY` / `PRIVACY_LOCK`. Phase 1 ships the interface plus a
default implementation that mirrors the web's fixed `comparisonBaseline`
privacy mode; it does not invent enforcement rules beyond what the web
specification states.
