# WinUI 3 migration baseline

This project is a native WinUI 3 / C# / .NET / Windows App SDK shell. The existing WPF project remains beside it as a technical reference.

`WindowsPackageType=None` selects unpackaged execution for this initial development baseline. Production distribution (MSIX, unpackaged, or another supported model) is intentionally undecided and must be reviewed before release.

No backend adapters are implemented or registered here. The section status labels describe implementation availability; they are not runtime observations. The overview says `UNAVAILABLE` because this shell does not yet query the runtime. Mobile Connection is a separate area from Mobility/VVS, with no device or pairing data fabricated.

The WinUI project links (does not copy) the framework-neutral `JarvisApiClient.cs`, `JarvisListItem.cs`, `MetricBreakdown.cs`, and `MetricBucket.cs` source files from the preserved WPF folder. The API client is not yet registered behind an adapter or called by the shell.

## WPF source classification

| Existing file / responsibility | Class | Evidence-based disposition |
|---|---|---|
| `Jarvis.ControlHub.csproj` | C | `UseWPF`, WPF WinExe and publish properties define the old target; retain it and create a separate WinUI project. |
| `App.xaml`, `App.xaml.cs` | C | WPF Application resources, `StartupUri`, and `System.Windows.Application` lifecycle require native WinUI equivalents. |
| `MainWindow.xaml`, `MainWindow.xaml.cs` | C | WPF Window, controls, routed events, visibility/brush APIs and visual-tree calls are framework-specific. |
| `MainWindowViewModel.cs` | B | Useful data shaping and freshness logic exists, but dispatcher, timer and WPF dialog dependencies need extraction behind platform-neutral services. Do not copy wholesale. |
| `JarvisApiClient.cs` | A | Uses BCL HTTP/JSON and fixed loopback endpoint policy; suitable for direct reuse after namespace/project reference review. |
| Runtime snapshot/action contracts in `RuntimeSupervisorClient.cs` | A | Records and action/result data contracts are framework-neutral. |
| Process launch, embedded PowerShell and repository discovery in `RuntimeSupervisorClient.cs` | B | Windows operations and repository-root access need an adapter boundary before reuse. |
| `RepositoryRootValidator` | A | Filesystem and reparse-point validation uses framework-neutral .NET APIs. |
| `JarvisListItem.cs`, `MetricBreakdown.cs`, `MetricBucket.cs` | A | Plain data records without WPF types. |
| `app.manifest` | B | Execution identity may remain relevant, but WinUI packaging/runtime settings need review. |
| `publish.ps1` | D | Current script publishes the WPF project; do not treat it as the WinUI release pipeline. |
| `bin/`, `obj/`, `artifacts/` | D | Generated output, not source to migrate. |

The Lovable project remains a design/interaction reference only. Its React/Tailwind implementation is not a dependency of this project.
