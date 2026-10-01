# WinUI 3 Handoff-Hinweise

Diese Punkte werden im Web-Prototyp bewusst nicht perfektioniert. Sie sind nativ in WinUI 3 umzusetzen.

- Fensterrahmen: Titelbar und Fenstersteuerung sind nur Attrappen. Nativ: `AppWindow`/`ExtendsContentIntoTitleBar`, Snap Layouts, echte Caption Buttons.
- Navigation: Top-Tabs plus System-Menü. Nativ: `NavigationView` mit `PaneDisplayMode="Top"`, Overflow automatisch.
- Material: Verläufe und Schatten simulieren Tiefe. Nativ: Mica/Mica Alt für Fenster, `LayerFillColor`-Ebenen für Panels, keine CSS-Verläufe nachbauen.
- Drawer: seitliche Overlay-Fläche. Nativ: `SplitView` oder `TeachingTip`/`ContentDialog` je nach Kontext.
- Dialoge: nicht implementiert. Nativ: `ContentDialog` mit Primär-/Abbrechen-Aktion.
- Disabled-Controls: Web-Buttons ohne Backend. Nativ: `IsEnabled=false` auf echten `ToggleSwitch`/`ComboBox`, gebunden an Backend-Capabilities.
- Fokus: CSS-Outline. Nativ: System-Fokusrahmen (`UseSystemFocusVisuals`), Tastaturnavigation über `XYFocus`.
- Scrollbars, Hover-Übergänge, Schriftrendering: nativ vom System, nicht nachbauen.
- Responsive Breakpoints: nativ über `VisualStateManager` und `AdaptiveTrigger`, Mindestfenstergröße festlegen statt Mobile-Layout.
- Gehirnbild: statisches Raster. Nativ: Vektor- oder Composition-Visual, das nur echte Backend-Events darstellt.
- Ablauf-Leisten (Pipeline, Lifecycle, Kopplung, Recovery): nativ als eigenes Control mit `ItemsRepeater` und horizontalem Layout, Zustände aus dem Backend gebunden.
- Settings: nativ als `SettingsCard`/`SettingsExpander` (Windows Community Toolkit) statt Web-Zeilen.
