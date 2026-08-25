import { Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { BookOpen, Feather, Skull, Sparkles, FileDown, PenLine } from "lucide-react";

export default function Landing() {
  const { user } = useAuth();
  const ctaTarget = user ? "/dashboard" : "/register";

  return (
    <div className="bg-background text-foreground" data-testid="landing-page">
      {/* Hero */}
      <section className="relative border-b border-border overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-20"
          style={{ backgroundImage: "url('https://images.pexels.com/photos/16217953/pexels-photo-16217953.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940')" }}
        />
        <div className="absolute inset-0 bg-black/70" />
        <div className="relative max-w-6xl mx-auto px-6 py-28 md:py-36">
          <p className="font-mono text-primary text-sm mb-4 tracking-widest">// AI BOOK GENERATION ENGINE</p>
          <h1 className="font-serif text-4xl sm:text-5xl lg:text-6xl leading-[1.05] tracking-tighter max-w-3xl mb-6">
            Your novel is <span className="text-primary crt-glow">already written</span>.
            <br />It just hasn't been generated yet.
          </h1>
          <p className="font-mono text-base md:text-lg text-muted-foreground max-w-xl mb-10">
            Feed the machine a prompt. Watch a full-length novel, memoir, or biography assemble itself
            chapter by chapter — coherent, haunting, complete.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link
              to={ctaTarget}
              className="px-8 py-4 bg-primary text-primary-foreground font-mono uppercase text-sm hover:bg-primary/80 transition-colors"
              data-testid="hero-cta-button"
            >
              Start Generating →
            </Link>
            <a
              href="#how-it-works"
              className="px-8 py-4 border border-primary text-primary font-mono uppercase text-sm hover:bg-primary hover:text-primary-foreground transition-colors"
              data-testid="hero-learn-more-button"
            >
              How it works
            </a>
          </div>
        </div>
      </section>

      {/* Terminal feature showcase */}
      <section id="how-it-works" className="max-w-6xl mx-auto px-6 py-24 grid md:grid-cols-2 gap-10 items-center">
        <div>
          <p className="font-mono text-primary text-xs tracking-widest mb-3">// THE ALGORITHM</p>
          <h2 className="font-serif text-3xl md:text-4xl mb-6 tracking-tight">Block-based coherent generation</h2>
          <p className="font-mono text-sm text-muted-foreground leading-relaxed mb-6">
            Each chapter is generated with full awareness of what came before — a running summary,
            tracked characters, and open plot threads carried forward block by block. No forgetting.
            No contradictions. Just a story that holds together across hundreds of pages.
          </p>
          <ul className="space-y-3 font-mono text-sm">
            <li className="flex items-center gap-3"><Sparkles className="w-4 h-4 text-primary" /> Prompt → outline → chapters, live</li>
            <li className="flex items-center gap-3"><PenLine className="w-4 h-4 text-primary" /> Edit any chapter (Premium)</li>
            <li className="flex items-center gap-3"><FileDown className="w-4 h-4 text-primary" /> Export a clean A5 PDF (Premium)</li>
          </ul>
        </div>
        <div className="border border-primary bg-card p-6 font-mono text-sm shadow-[0_0_20px_rgba(57,255,20,0.08)]">
          <p className="text-muted-foreground mb-2">$ fantm generate --type novel</p>
          <p className="text-primary">[1/8] outlining premise... <span className="blink-cursor">█</span></p>
          <p className="text-primary/70">[2/8] chapter one: "The Arrival"... done</p>
          <p className="text-primary/70">[3/8] chapter two: "Old Debts"... done</p>
          <p className="text-muted-foreground">tracking 4 characters, 3 plot threads</p>
          <p className="text-accent mt-4">status: generating</p>
        </div>
      </section>

      {/* Book types */}
      <section className="border-t border-border bg-secondary/40">
        <div className="max-w-6xl mx-auto px-6 py-24">
          <p className="font-mono text-primary text-xs tracking-widest mb-3">// PICK YOUR FORM</p>
          <h2 className="font-serif text-3xl md:text-4xl mb-12 tracking-tight">Three kinds of manuscript</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: BookOpen, title: "Novel", desc: "Full-length fiction across any genre — fantasy, horror, romance, thriller." },
              { icon: Feather, title: "Memoir", desc: "Chronicle a life story with narrative arc, voice, and emotional truth." },
              { icon: Skull, title: "Biography", desc: "A researched-feeling account of a life, real or imagined, told in full." },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="border border-border p-8 hover:border-primary transition-colors bg-card" data-testid={`booktype-card-${title.toLowerCase()}`}>
                <Icon className="w-7 h-7 text-primary mb-4" />
                <h3 className="font-serif text-2xl mb-2">{title}</h3>
                <p className="font-mono text-sm text-muted-foreground">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing teaser */}
      <section className="max-w-6xl mx-auto px-6 py-24">
        <p className="font-mono text-primary text-xs tracking-widest mb-3">// THE NEURAL CREDIT ECONOMY</p>
        <h2 className="font-serif text-3xl md:text-4xl mb-12 tracking-tight">Pay in Neural Credits (NC)</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="border border-border p-8 bg-card">
            <p className="font-mono text-xs uppercase text-muted-foreground mb-2">Limited basic styles</p>
            <p className="font-serif text-3xl mb-1">Apprentice</p>
            <p className="font-mono text-2xl mb-4">Free</p>
            <ul className="font-mono text-sm text-muted-foreground space-y-2">
              <li>— 3,333 NC / month, rolls over</li>
              <li>— House writer style</li>
            </ul>
          </div>
          <div className="border border-border p-8 bg-card">
            <p className="font-mono text-xs uppercase text-muted-foreground mb-2">Selected advanced styles</p>
            <p className="font-serif text-3xl mb-1">Wordsmith</p>
            <p className="font-mono text-2xl mb-4">$9<span className="text-sm text-muted-foreground">/mo</span></p>
            <ul className="font-mono text-sm text-muted-foreground space-y-2">
              <li>— 40,000 NC / month, rolls over</li>
              <li>— Gothic Romantic & Noir Detective styles</li>
            </ul>
          </div>
          <div className="border border-accent p-8 bg-card shadow-[0_0_20px_rgba(138,3,3,0.15)]">
            <p className="font-mono text-xs uppercase text-accent mb-2">Full agency access</p>
            <p className="font-serif text-3xl mb-1">Laureate</p>
            <p className="font-mono text-2xl mb-4">$33<span className="text-sm text-muted-foreground">/mo</span></p>
            <ul className="font-mono text-sm text-muted-foreground space-y-2">
              <li>— 150,000 NC / month, rolls over</li>
              <li>— Every style + Chimera Blend</li>
            </ul>
          </div>
        </div>
        <p className="font-mono text-xs text-muted-foreground mt-8">
          Illustrations, PDF export and credit top-ups are purchased à la carte in the Agency Store.
        </p>
      </section>

      <footer className="border-t border-border py-10 text-center font-mono text-xs text-muted-foreground">
        fantm.ink — generated, not written.
      </footer>
    </div>
  );
}
