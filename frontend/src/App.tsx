import { useState } from "react";
import { Music, ExternalLink } from "lucide-react";
import { MetadataBar } from "@/components/MetadataBar";
import { CanonicalGrid } from "@/components/CanonicalGrid";
import { AskBox } from "@/components/AskBox";
import { ActionsHistory } from "@/components/ActionsHistory";

export default function App() {
  const [bump, setBump] = useState(0);                    // forces remount of grid after reload

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-8">
        <Hero />
        <MetadataBar onRefreshed={() => setBump((b) => b + 1)} />

        <section className="space-y-3">
          <SectionHeader
            kicker="Weekly automation"
            title="Recent GitHub Action runs"
            subtitle="Each successful run commits fresh data to the repo. Download the exact data snapshot from any past run below."
          />
          <ActionsHistory />
        </section>

        <section className="space-y-3">
          <SectionHeader
            kicker="Pre-computed RAG synthesis"
            title="The 6 canonical questions"
            subtitle="Click a card to read the full synthesis and the supporting reviews."
          />
          <CanonicalGrid key={bump} />
        </section>

        <section className="space-y-3">
          <SectionHeader
            kicker="In-scope only · grounded in user reviews"
            title="Ask your own question"
            subtitle="The scope wrapper accepts paraphrases of the 6 canonical questions and refuses everything else."
          />
          <AskBox />
        </section>

        <Footer />
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-10 backdrop-blur bg-bg/70 border-b border-border">
      <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-brand/15 border border-brand/30 flex items-center justify-center">
          <Music className="w-4 h-4 text-brand" />
        </div>
        <div>
          <div className="text-sm font-semibold text-fg leading-tight">Spotify Discovery · AI Review Engine</div>
          <div className="text-[11px] text-fg-subtle leading-tight">RAG over App Store · Play Store · YouTube</div>
        </div>
        <div className="ml-auto flex items-center gap-3 text-[12px]">
          <a className="text-fg-muted hover:text-fg inline-flex items-center gap-1"
             href="https://github.com/mmishra0321/NL_AIReviewDiscoveryEngine" target="_blank" rel="noreferrer">
            <ExternalLink className="w-3.5 h-3.5" /> repo
          </a>
          <a className="text-fg-muted hover:text-fg inline-flex items-center gap-1"
             href="/api/health" target="_blank" rel="noreferrer">
            <ExternalLink className="w-3.5 h-3.5" /> API
          </a>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="rounded-2xl border border-border bg-gradient-to-br from-bg-elevated via-bg-elevated to-bg-subtle p-6 md:p-8 shadow-card">
      <div className="max-w-3xl">
        <div className="text-[11px] uppercase tracking-wider text-brand">PM Capstone · Spotify Growth</div>
        <h1 className="text-2xl md:text-3xl font-bold mt-1.5 text-fg leading-tight">
          Why meaningful music discovery still fails at scale, in users' own words.
        </h1>
        <p className="text-[14px] text-fg-muted mt-2 leading-relaxed">
          This engine scrapes, normalizes, classifies, embeds, and RAG-synthesizes thousands
          of real reviews to answer six canonical PM questions about discovery, recommendations,
          and repetitive listening. Every answer cites the exact reviews that support it.
        </p>
      </div>
    </section>
  );
}

function SectionHeader({ kicker, title, subtitle }: { kicker: string; title: string; subtitle?: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-brand">{kicker}</div>
      <h2 className="text-lg md:text-xl font-semibold text-fg mt-0.5">{title}</h2>
      {subtitle && <p className="text-[13px] text-fg-muted">{subtitle}</p>}
    </div>
  );
}

function Footer() {
  return (
    <footer className="py-8 border-t border-border mt-8">
      <div className="text-[11px] text-fg-subtle flex flex-wrap items-center justify-between gap-3">
        <div>Powered by Groq (Llama-3.x) · Sentence-Transformers · ChromaDB · FastAPI · React + Vite</div>
        <div>Local dev: backend :8000 · frontend :5173</div>
      </div>
    </footer>
  );
}
