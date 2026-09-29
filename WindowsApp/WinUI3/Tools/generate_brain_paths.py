"""Erzeugt Domain/BrainPathData.cs aus dem Brain-Asset (deterministisch, einmalig offline).

Somata sind die im Asset sichtbaren hellen Synapsenpunkte. Bahnen sind kürzeste Wege entlang der hellen
Faserzüge des Assets (Dijkstra auf Helligkeitskosten) und bleiben innerhalb der Gehirnkontur. Damit läuft die
Aktivität durch das abgebildete neuronale Material statt über frei erfundene Kurven.

Aufruf: python generate_brain_paths.py   (benötigt numpy, opencv-python-headless, scipy, scikit-image)
"""
import math
import pathlib
import re

import cv2
import numpy as np
from scipy.ndimage import maximum_filter
from skimage.graph import MCP_Geometric

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSET = ROOT / "Resources" / "jarvis-brain-idle.jpg"
GRAPH = ROOT / "Domain" / "BrainNeuralGraph.cs"
OUT = ROOT / "Domain" / "BrainPathData.cs"

img = cv2.imread(str(ASSET)).astype(np.float32)
H, W = img.shape[:2]

# Funktionsknoten (Sollposition, wird auf den nächsten realen Synapsenpunkt gesetzt) und Funktionsbahnen.
# Die Bahnen müssen alle Kanten enthalten, die BrainActivityMapper ansteuert (per Test geprüft).
FUNCTIONAL_NODES = [
    ("input", 0.285, 0.300, "Input"), ("ctx1", 0.335, 0.405, "Context"), ("mem1", 0.345, 0.520, "Memory"),
    ("mem2", 0.445, 0.595, "Memory"), ("ctx2", 0.430, 0.470, "Context"), ("core1", 0.500, 0.375, "Core"),
    ("core2", 0.545, 0.500, "Core"), ("route", 0.530, 0.215, "Routing"), ("inf1", 0.620, 0.300, "Inference"),
    ("inf2", 0.650, 0.440, "Inference"), ("inf3", 0.615, 0.545, "Inference"), ("tool", 0.705, 0.385, "Tool"),
    ("resp1", 0.600, 0.625, "Response"), ("resp2", 0.655, 0.685, "Response"),
]
FUNCTIONAL_EDGES = [
    ("input", "mem1"), ("input", "ctx1"), ("mem1", "mem2"), ("mem1", "ctx1"), ("mem2", "ctx2"), ("ctx1", "core1"),
    ("ctx2", "core1"), ("ctx2", "core2"), ("core1", "core2"), ("core1", "route"), ("route", "inf1"), ("route", "inf2"),
    ("inf1", "inf2"), ("inf2", "inf3"), ("inf1", "tool"), ("tool", "inf2"), ("inf3", "core2"), ("core2", "resp1"),
    ("core1", "resp1"), ("resp1", "resp2"),
]

# Innenkontur aus BrainNeuralGraph.cs (BrainSilhouette.Outline) übernehmen, damit es genau eine Wahrheit gibt.
src = GRAPH.read_text(encoding="utf-8")
outline_src = src.split("Outline =")[1].split("];")[0]
outline = [(float(a), float(b)) for a, b in re.findall(r"\(([\d.]+), ([\d.]+)\)", outline_src)]
mask = np.zeros((H, W), np.uint8)
cv2.fillPoly(mask, [np.array([(x * W, y * H) for x, y in outline], np.int32)], 1)
inner = cv2.erode(mask, np.ones((9, 9), np.uint8))

# Faserhelligkeit: weiß/cyan-Anteil, leicht geglättet. Kosten niedrig auf hellen Fasern, hoch im dunklen Gewebe.
white = np.minimum(img[..., 2], img[..., 1])
fiber = cv2.GaussianBlur(white, (0, 0), 1.2) / 255.0
cost = 1.0 / (0.03 + fiber ** 1.6)
cost[inner == 0] = 1e6

# Synapsenpunkte: kleine helle Blobs (Difference of Gaussians, lokale Maxima).
dog = cv2.GaussianBlur(white, (0, 0), 1.5) - cv2.GaussianBlur(white, (0, 0), 5)
peaks = (dog == maximum_filter(dog, size=25)) & (dog > 14) & (inner == 1)
ys, xs = np.nonzero(peaks)
order = np.argsort(-dog[ys, xs])
candidates = [(int(xs[i]), int(ys[i]), float(dog[ys[i], xs[i]])) for i in order]

# Funktionsknoten auf den stärksten nahen Synapsenpunkt setzen.
functional = FUNCTIONAL_NODES
nodes = {}
used = set()
for node_id, fx, fy, region in functional:
    tx, ty = fx * W, fy * H
    best = None
    for idx, (x, y, s) in enumerate(candidates):
        d = math.hypot(x - tx, y - ty)
        if d < 48 and idx not in used and (best is None or s - d * 0.4 > best[1]):
            best = (idx, s - d * 0.4)
    if best is not None:
        used.add(best[0])
        x, y, s = candidates[best[0]]
    else:
        x, y, s = tx, ty, 20.0
    nodes[node_id] = (x, y, s, region)

# Strukturelle Somata: stärkste Punkte mit Mindestabstand.
MIN_SPACING = 40
somas = []
for idx, (x, y, s) in enumerate(candidates):
    if idx in used:
        continue
    if all(math.hypot(x - nx, y - ny) >= MIN_SPACING for nx, ny, *_ in list(nodes.values()) + somas):
        somas.append((x, y, s))
    if len(somas) >= 84:
        break
for i, (x, y, s) in enumerate(somas):
    nodes[f"n{i:02d}"] = (x, y, s, "Relay")


def route(a, b):
    ax, ay = nodes[a][:2]
    bx, by = nodes[b][:2]
    m = 70
    x0, x1 = int(max(0, min(ax, bx) - m)), int(min(W, max(ax, bx) + m))
    y0, y1 = int(max(0, min(ay, by) - m)), int(min(H, max(ay, by) + m))
    sub = cost[y0:y1, x0:x1]
    mcp = MCP_Geometric(sub)
    start, end = (int(ay) - y0, int(ax) - x0), (int(by) - y0, int(bx) - x0)
    costs, _ = mcp.find_costs([start], [end])
    path = mcp.traceback(end)
    pts = np.array([(p[1] + x0, p[0] + y0) for p in path], np.float64)
    total = costs[end]
    return pts, total


def resample(pts, spacing=9.0):
    # Leicht glätten (Pixeltreppe entfernen), dann in gleichen Bogenabständen neu abtasten.
    k = 5
    if len(pts) > k * 2:
        kernel = np.ones(k) / k
        sm = np.stack([np.convolve(pts[:, i], kernel, mode="same") for i in range(2)], 1)
        sm[: k // 2 + 1] = pts[: k // 2 + 1]
        sm[-(k // 2 + 1):] = pts[-(k // 2 + 1):]
        pts = sm
    seg = np.hypot(*np.diff(pts, axis=0).T)
    arc = np.concatenate([[0], np.cumsum(seg)])
    n = max(4, int(round(arc[-1] / spacing)) + 1)
    t = np.linspace(0, arc[-1], n)
    return np.stack([np.interp(t, arc, pts[:, 0]), np.interp(t, arc, pts[:, 1])], 1)


edges = []
for a, b in FUNCTIONAL_EDGES:
    pts, _ = route(a, b)
    edges.append((a, b, "true", resample(pts)))

# Strukturbahnen: je Soma bis zu drei Nachbarn, nur wenn der Weg tatsächlich über helle Fasern führt.
ids = list(nodes)
pairs = set((a, b) for a, b, *_ in edges) | set((b, a) for a, b, *_ in edges)
for a in ids:
    ax, ay = nodes[a][:2]
    near = sorted((math.hypot(nodes[b][0] - ax, nodes[b][1] - ay), b) for b in ids if b != a)
    added = 0
    for d, b in near:
        if d > 150 or added >= 3:
            break
        if (a, b) in pairs:
            added += 1
            continue
        pts, total = route(a, b)
        length = np.hypot(*np.diff(pts, axis=0).T).sum()
        mean_fiber = np.mean([fiber[int(y), int(x)] for x, y in pts])
        if length > d * 1.7 or mean_fiber < 0.16:
            continue
        pairs.add((a, b)); pairs.add((b, a))
        edges.append((a, b, "false", resample(pts)))
        added += 1

strength = np.array([n[2] for n in nodes.values()])
lo, hi = np.percentile(strength, 10), np.percentile(strength, 95)


def depth(s):
    # Stärkere, schärfere Punkte liegen optisch vorne (1), schwache hinten (0). Nur für Größe/Helligkeit.
    return float(np.clip((s - lo) / (hi - lo), 0, 1))


lines = [
    "// <auto-generated>",
    "// Erzeugt von Tools/generate_brain_paths.py aus Resources/jarvis-brain-idle.jpg. Nicht von Hand ändern.",
    "// </auto-generated>",
    "namespace Jarvis.ControlHub.WinUI.Domain;",
    "",
    "internal static class BrainPathData",
    "{",
    "    /// <summary>Id, X, Y (normalisiert), Tiefe 0..1 (0 = hinten), Region.</summary>",
    "    public static readonly (string Id, double X, double Y, double Depth, BrainRegion Region)[] Nodes =",
    "    [",
]
for nid, (x, y, s, region) in nodes.items():
    lines.append(f'        ("{nid}", {x / W:.4f}, {y / H:.4f}, {depth(s):.2f}, BrainRegion.{region}),')
lines += ["    ];", "", "    /// <summary>Von, Nach, Funktionsbahn, Polylinie (x0, y0, x1, y1, ...) normalisiert.</summary>",
          "    public static readonly (string From, string To, bool Functional, double[] Path)[] Edges =", "    ["]
for a, b, fn, pts in edges:
    flat = ", ".join(f"{x / W:.4f}, {y / H:.4f}" for x, y in pts)
    lines.append(f'        ("{a}", "{b}", {fn}, [{flat}]),')
lines += ["    ];", "}", ""]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"{len(nodes)} Knoten, {len(edges)} Bahnen ({sum(1 for e in edges if e[2] == 'true')} Funktionsbahnen) -> {OUT.name}")
