import { useCallback, useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { VariantPicker } from "@/components/prototype/variant-picker";
import { PhoneFrame } from "@/components/prototype/phone-frame";
import { VariantA } from "@/components/prototype/variants/variant-a";
import { VariantB } from "@/components/prototype/variants/variant-b";
import { VariantC } from "@/components/prototype/variants/variant-c";
import { VariantD } from "@/components/prototype/variants/variant-d";

export const Route = createFileRoute("/prototypes/shell")({
  head: () => ({
    meta: [
      { title: "Shell-Prototypen: J.A.R.V.I.S Mobile" },
      {
        name: "description",
        content:
          "Drei Android-Shell- und Navigationsvarianten für J.A.R.V.I.S Mobile: Systemleiste, Konsole, Konversation + Systemblatt.",
      },
      { property: "og:title", content: "Shell-Prototypen: J.A.R.V.I.S Mobile" },
      {
        property: "og:description",
        content: "Navigationsvergleich für den lokalen Android-Runtime-Shell von J.A.R.V.I.S.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ShellPrototypes,
});

const variants = [
  {
    name: "Systemleiste",
    caption: "Variante A · Bottom Navigation · 393 × 852 dp",
    axis: "Vertraute Android-Tableiste, vier feste Ziele, mittlere Dichte.",
    render: () => <VariantA />,
  },
  {
    name: "Konsole",
    caption: "Variante B · Drawer + Runtime-Leiste · 393 × 852 dp",
    axis: "Keine Tableiste. Persistente Runtime-Leiste, Drawer für alle Bereiche, maximale Dichte.",
    render: () => <VariantB />,
  },
  {
    name: "Konversation",
    caption: "Variante C · Chat-Root + Systemblatt · 393 × 852 dp",
    axis: "Chat ist die Wurzel; das gesamte System liegt in einem ausklappbaren Bottom Sheet.",
    render: () => <VariantC />,
  },
  {
    name: "Systemleiste + Runtime",
    caption: "Variante D · Bottom Navigation + Runtime-Leiste · 393 × 852 dp",
    axis: "Konsolidierter Kandidat: Tableiste aus A, persistente Runtime-Leiste aus B, Composer nur im Chat.",
    render: () => <VariantD />,
  },
];

function ShellPrototypes() {
  const [current, setCurrent] = useState(0);
  const [mountKey, setMountKey] = useState(0);

  useEffect(() => {
    const v = parseInt(new URLSearchParams(window.location.search).get("v") ?? "", 10);
    if (v >= 1 && v <= variants.length) setCurrent(v - 1);
  }, []);

  const select = useCallback((i: number) => {
    setCurrent(i);
    setMountKey((k) => k + 1);
    const url = new URL(window.location.href);
    url.searchParams.set("v", String(i + 1));
    window.history.replaceState(null, "", url);
  }, []);

  const variant = variants[current]!;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border-soft px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
          <div>
            <h1 className="text-[15px] font-medium text-foreground">Shell-Prototypen</h1>
            <p className="mt-0.5 text-[12px] text-muted-foreground">
              Phase 1 · Navigationsentscheidung · keine Runtime-Anbindung
            </p>
          </div>
          <Link to="/" className="text-[12px] text-primary">
            Grundlagen
          </Link>
        </div>
      </header>

      <main className="mx-auto flex max-w-4xl flex-col items-center gap-6 px-6 py-8 pb-28">
        <p className="max-w-prose text-center text-[12px] leading-5 text-muted-foreground">
          {variant.axis}
        </p>
        <PhoneFrame caption={variant.caption}>
          <div key={mountKey} className="h-full">
            {variant.render()}
          </div>
        </PhoneFrame>
      </main>

      <VariantPicker
        names={variants.map((v) => v.name)}
        current={current}
        onSelect={select}
      />
    </div>
  );
}
