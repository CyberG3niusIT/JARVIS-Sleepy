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
| `screens/models-screen.tsx` | `feature/system/ModelsScreen.kt` | scaffolded (`JarvisDetailHeader` + real IA copy + `JarvisNotImplementedState`/list skeleton), full row-level port next |
| `screens/agents-screen.tsx` | `feature/system/AgentsScreen.kt` | scaffolded |
| `screens/tools-screen.tsx` | `feature/system/ToolsScreen.kt` | scaffolded |
| `screens/permissions-screen.tsx` | `feature/system/PermissionsScreen.kt` | scaffolded |
| `screens/privacy-screen.tsx` | `feature/system/PrivacyScreen.kt` | scaffolded |
| `screens/runtimes-screen.tsx` | `feature/system/RuntimesScreen.kt` | scaffolded |
| `screens/device-screen.tsx` | `feature/system/DeviceScreen.kt` | scaffolded |
| `screens/diagnostics-screen.tsx` | `feature/system/DiagnosticsScreen.kt` | scaffolded |
| `screens/voice-screen.tsx` | `feature/more/VoiceScreen.kt` | scaffolded |
| `screens/memory-screen.tsx` | `feature/more/MemoryScreen.kt` | scaffolded |
| `screens/automations-screen.tsx` + `automation-editor.tsx` | `feature/more/AutomationsScreen.kt` | scaffolded |
| `screens/settings-screen.tsx` | `feature/more/SettingsScreen.kt` | scaffolded |
| `screens/about-screen.tsx` | `feature/more/AboutScreen.kt` | scaffolded |

"Scaffolded" = real route, real title/subtitle/purpose text taken verbatim
from `src/lib/jarvis/ia.ts`, uses the shared design-system components and the
correct `SystemState`, but does not yet reproduce every row of the web
reference. Row-level parity for these follows in the same branch; each is
tracked as its own small commit so review stays possible.

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
