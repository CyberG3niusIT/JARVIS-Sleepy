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
  Navigation Compose `NavHost` with 4 top-level destinations
  (`JarvisDestination.Start/Chat/System/More`) hosted in `JarvisAppShell`
  (Scaffold: `JarvisTopBar` + `JarvisRuntimeStrip` + content + `JarvisBottomNavigation`).
- System/More detail navigation (`system-screen.tsx`, `more-screen.tsx`: local
  `useState` detail routing with `ScreenTransition` direction) -> nested
  `NavHost` graphs (`system` / `more` sub-graphs) so each detail screen is its
  own back-stack entry; Android system Back pops the sub-graph before leaving
  the tab, matching the locked Back table in the goal spec.
- Automation editor discard-confirmation -> `JarvisDialog` shown from a
  `BackHandler` when the editor's local state is dirty.

## Screens

| Web screen | Compose screen | Phase 1 status |
|---|---|---|
| `screens/start-screen.tsx` | `feature/start/StartScreen.kt` | ported |
| `screens/chat-screen.tsx` | `feature/chat/ChatScreen.kt` | ported (core layout, message list, composer, execution tags; attachment picker UI deferred, see OPEN_DECISIONS) |
| `screens/system-screen.tsx` (overview) | `feature/system/SystemOverviewScreen.kt` | ported |
| `screens/more-screen.tsx` (overview) | `feature/more/MoreOverviewScreen.kt` | ported |
| `screens/models-screen.tsx` | `feature/system/ModelsScreen.kt` | ported (current-state rows, empty local-model list, management capabilities, add-model sheet entry point); catalog browser / local-file import flows (`models-demo.tsx`) deferred |
| `screens/agents-screen.tsx` | `feature/system/AgentsScreen.kt` | ported (agent model, safety bounds, empty running-tasks state, full demo-agent detail sheet with cancel/retry/fail-demo/error/tool-activity) |
| `screens/tools-screen.tsx` | `feature/system/ToolsScreen.kt` | ported (full `capabilityRows` capability audit list) |
| `screens/permissions-screen.tsx` | `feature/system/PermissionsScreen.kt` | ported (eight access-area groups, detail sheet with why-needed/capabilities/demo-state selector) |
| `screens/privacy-screen.tsx` | `feature/system/PrivacyScreen.kt` | ported (mode selector, explain sheet, PRIVACY_LOCK/relax confirm dialogs, protected groups, guarantees) |
| `screens/runtimes-screen.tsx` | `feature/system/RuntimesScreen.kt` | ported (this-device/trusted-runtime/cloud rows, handoff-package structure); pairing/trust/handoff demo sections (`runtimes-demo.tsx`) deferred, see OPEN_DECISIONS Sec.1 |
| `screens/device-screen.tsx` | `feature/system/DeviceScreen.kt` | ported (real `android.os.Build` fields) |
| `screens/diagnostics-screen.tsx` | `feature/system/DiagnosticsScreen.kt` | ported (empty history/crash states, redaction rules, export notice) |
| `screens/voice-screen.tsx` | `feature/more/VoiceScreen.kt` | ported (full labelled state machine + transition controls, Wake Word/STT/TTS configuration sheets) |
| `screens/memory-screen.tsx` | `feature/more/MemoryScreen.kt` | ported (layers/provenance/rules lists, empty baseline, full demo-entry detail sheet with confirm/correct/discard/supersede/provenance) |
| `screens/automations-screen.tsx` | `feature/more/AutomationsScreen.kt` | ported (types, execution rules, empty baseline state); full step/condition/schedule editor (`automation-editor.tsx`, 685 lines) and the local in-session automation list deferred |
| `screens/settings-screen.tsx` | `feature/more/SettingsScreen.kt` | ported |
| `screens/about-screen.tsx` | `feature/more/AboutScreen.kt` | ported |

All thirteen System/Mehr detail destinations now render their full static
content and locked German copy from the web reference. What remains
deferred everywhere is *interactive* content that needs a real backing
system to mean anything: attachment picking (Chat), the model
catalog/import flows (Modelle), Sleepy pairing/trust (Runtimes), and the
automation editor's step/condition/schedule builder (Automationen). Each is
called out in its screen's doc comment and, where it touches an open
architecture question, in OPEN_DECISIONS.md.

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

## Privacy

`PrivacyGate` (`core/privacy/PrivacyGate.kt`) is the single interface every
feature module must go through to check whether an action is allowed under
`NORMAL` / `PRIVACY` / `PRIVACY_LOCK`. Phase 1 ships the interface plus a
default implementation that mirrors the web's fixed `comparisonBaseline`
privacy mode; it does not invent enforcement rules beyond what the web
specification states.
