import { useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import * as Tooltip from "@radix-ui/react-tooltip";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, BookOpenCheck, Check, ChevronRight, CircleHelp, Database,
  ExternalLink, FileSearch, Github, Landmark, LockKeyhole, Menu, ShieldCheck,
  Sparkles, Stethoscope, TimerReset, UserCheck, X
} from "lucide-react";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { cn } from "./lib/utils";

type CaseId = "GOL007" | "GOL027" | "GOL024";

const cases = {
  GOL007: {
    label: "Room-cap deduction",
    member: "Aarav S. · Gold family floater",
    outcome: "APPROVE WITH DEDUCTIONS",
    tone: "amber" as const,
    claimed: "₹120,000",
    payable: "₹79,800",
    confidence: "High",
    summary: "Eligible after applying the room cap, proportionate deduction and mandatory co-pay.",
    lines: [
      ["Room charges", "₹24,000", "₹15,000", "NIA-4.1-A"],
      ["Professional fees", "₹55,000", "₹34,375", "NIA-4.1-NOTE-B"],
      ["Diagnostics + medicines", "₹41,000", "₹34,625", "Policy schedule"],
      ["Mandatory co-pay", "—", "−₹4,200", "NIA-9.5"]
    ]
  },
  GOL027: {
    label: "Missing cost breakup",
    member: "Meera P. · Gold individual",
    outcome: "QUERY",
    tone: "violet" as const,
    claimed: "Not supplied",
    payable: "Pending",
    confidence: "Needs input",
    summary: "The hospital must provide an itemised cost breakup before a payable amount can be calculated.",
    lines: [
      ["Hospital request", "Received", "Incomplete", "Pre-auth form"],
      ["Cost breakup", "Missing", "Required", "Validation rule"],
      ["Next action", "—", "Query hospital", "Human review"]
    ]
  },
  GOL024: {
    label: "PED medical referral",
    member: "Ishaan R. · Gold family floater",
    outcome: "REFER",
    tone: "violet" as const,
    claimed: "₹86,500",
    payable: "Pending",
    confidence: "Medical review",
    summary: "Declared diabetes maps to the 36-month pre-existing disease waiting period and needs medical review.",
    lines: [
      ["Declared condition", "Diabetes", "Review", "Member 360"],
      ["Waiting period", "36 months", "Check tenure", "NIA-6.2-36"],
      ["Next action", "—", "Refer doctor", "Human review"]
    ]
  }
};

const metrics = [
  ["30/30", "Schema-valid", "Every response passed the output contract"],
  ["90%", "Outcome match", "27 of 30 matched the golden decision"],
  ["96.7%", "Amount match", "29 of 30 matched payable amounts"],
  ["41.4s", "Mean latency", "Measured across the evaluation run"]
];

const architecture = [
  { icon: FileSearch, title: "Pre-auth PDFs", body: "AI_PARSE_DOCUMENT + AI_EXTRACT" },
  { icon: Database, title: "Member 360", body: "Semantic View + structured history" },
  { icon: BookOpenCheck, title: "Policy evidence", body: "Cortex Search across 35 clauses" },
  { icon: Landmark, title: "Rules tools", body: "Pure Python, integer rupees" },
  { icon: Sparkles, title: "Cortex Agent", body: "Tool-first orchestration + cited JSON" },
  { icon: UserCheck, title: "Reviewer", body: "Masked views + durable audit trail" }
];

function Logo() {
  return <a href="#top" className="brand-mark" aria-label="CashlessIQ home"><span>Cashless</span><b>IQ</b></a>;
}

function Header() {
  const [open, setOpen] = useState(false);
  return <header className="site-header">
    <Logo />
    <nav className={cn("main-nav", open && "is-open")}>
      <a href="#workspace" onClick={() => setOpen(false)}>Live demo</a>
      <a href="#architecture" onClick={() => setOpen(false)}>Architecture</a>
      <a href="#evidence" onClick={() => setOpen(false)}>Evidence</a>
      <Button variant="outline" size="sm" asChild><a href="https://github.com/hulagerushikesh/cashlessiq"><Github size={15} /> GitHub</a></Button>
    </nav>
    <button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle navigation">{open ? <X /> : <Menu />}</button>
  </header>;
}

function Hero() {
  return <section id="top" className="hero-shell">
    <div className="hero-grid">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }}>
        <Badge className="hero-badge">Snowflake CoCo CLI Hackathon · GCC Edition</Badge>
        <h1>Policy evidence in.<br /><em>Review-ready</em> decisions out.</h1>
        <p className="hero-copy">CashlessIQ assembles the member record, finds the exact policy wording and drafts a cashless pre-authorisation recommendation. Deterministic Python calculates every rupee. A human decides.</p>
        <div className="hero-actions">
          <Button size="lg" asChild><a href="#workspace">Review a case <ArrowRight size={17} /></a></Button>
          <Button size="lg" variant="outline" asChild><a href="https://app.snowflake.com/streamlit/nooirvx/ca31605/#/apps/a3gfspf7joxnsjryt3pd">Snowflake console <ExternalLink size={16} /></a></Button>
        </div>
        <div className="trust-line"><ShieldCheck size={17} /><span>No DENY outcome</span><span>·</span><span>Synthetic data only</span><span>·</span><span>Human approval gate</span></div>
      </motion.div>
      <motion.div className="hero-visual" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: .65, delay: .1 }}>
        <div className="signal-rail"><span>01</span><span>REQUEST</span><i /></div>
        <div className="hero-case">
          <div className="case-top"><div><small>PRE-AUTH REQUEST</small><strong>GOL007</strong></div><Badge variant="neutral"><LockKeyhole size={12} /> governed</Badge></div>
          <div className="patient-line"><div className="patient-avatar">AS</div><div><b>Aarav Sharma</b><span>Member ID •••• 2207</span></div><Stethoscope /></div>
          <div className="mini-rule"><span>Policy evidence</span><b>NIA-4.1-A</b><Check /></div>
          <div className="mini-rule"><span>Member history</span><b>Gold floater · active</b><Check /></div>
          <div className="hero-result"><small>RECOMMENDED PAYABLE</small><strong>₹79,800</strong><span>from ₹120,000 claimed</span></div>
        </div>
        <div className="signal-rail bottom"><span>04</span><span>HUMAN REVIEW</span><i /></div>
      </motion.div>
    </div>
  </section>;
}

function Workspace() {
  const [active, setActive] = useState<CaseId>("GOL007");
  const selected = cases[active];
  const total = useMemo(() => selected.lines.length, [selected]);
  return <section id="workspace" className="section workspace-section">
    <div className="section-heading"><div><span className="kicker">Interactive prototype</span><h2>Review the recommendation, not a black box</h2></div><p>Select a fixed-seed case. The public demo mirrors the governed Snowflake workflow without requiring judge credentials.</p></div>
    <Tabs.Root value={active} onValueChange={(v) => setActive(v as CaseId)} className="workspace">
      <aside className="case-queue">
        <div className="queue-label"><span>Case queue</span><Badge variant="neutral">3 synthetic</Badge></div>
        <Tabs.List aria-label="Demo cases">
          {(Object.keys(cases) as CaseId[]).map((id) => <Tabs.Trigger key={id} value={id} className="case-trigger">
            <span className="case-id">{id}</span><span>{cases[id].label}</span><ChevronRight size={16} />
          </Tabs.Trigger>)}
        </Tabs.List>
        <div className="queue-foot"><TimerReset size={16} /><span>IRDAI one-hour decision context</span></div>
      </aside>
      <main className="review-panel">
        <AnimatePresence mode="wait">
          <motion.div key={active} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .2 }}>
            <div className="review-head"><div><span className="review-meta">{active} · {selected.member}</span><h3>{selected.label}</h3></div><Badge variant={selected.tone}>{selected.outcome}</Badge></div>
            <div className="amount-strip"><div><span>Claimed</span><strong>{selected.claimed}</strong></div><ArrowRight /><div className="payable"><span>Recommended payable</span><strong>{selected.payable}</strong></div><div className="confidence"><span>Confidence</span><b>{selected.confidence}</b></div></div>
            <p className="decision-summary">{selected.summary}</p>
            <div className="line-table">
              <div className="line-row line-header"><span>Assessment</span><span>Submitted</span><span>Decision</span><span>Evidence</span></div>
              {selected.lines.map((line, i) => <div className="line-row" key={line[0]}><span><i>{String(i + 1).padStart(2, "0")}</i>{line[0]}</span><span>{line[1]}</span><strong>{line[2]}</strong><span className="evidence-tag">{line[3]}</span></div>)}
            </div>
            <div className="review-actions"><Button><Check size={16} /> Accept recommendation</Button><Button variant="outline">Edit amount</Button><Button variant="quiet">Raise query</Button><span>{total} evidence checks shown</span></div>
          </motion.div>
        </AnimatePresence>
      </main>
      <aside className="evidence-rail">
        <div className="evidence-title"><FileSearch size={18} /><span>Evidence rail</span></div>
        <div className="source-item"><small>POLICY CLAUSE</small><b>{active === "GOL007" ? "Room rent and proportionate deduction" : active === "GOL027" ? "Required cost information" : "Pre-existing disease waiting period"}</b><p>{active === "GOL007" ? "Eligibility is capped by the room category in the schedule." : active === "GOL027" ? "Itemised costs are required before benefit calculation." : "A 36-month waiting period applies to declared PEDs."}</p><span>{active === "GOL007" ? "NIA-4.1-A" : active === "GOL027" ? "Validation rule" : "NIA-6.2-36"}</span></div>
        <div className="source-item"><small>MEMBER 360</small><b>Coverage and history verified</b><p>Structured member facts are resolved before the recommendation is drafted.</p><span>Semantic View</span></div>
        <Tooltip.Provider><Tooltip.Root><Tooltip.Trigger asChild><div className="why-box"><CircleHelp size={17} /><span>Why these sources?</span></div></Tooltip.Trigger><Tooltip.Portal><Tooltip.Content className="tooltip-content" sideOffset={8}>The Agent retrieves evidence. Deterministic tools compute amounts.<Tooltip.Arrow className="tooltip-arrow" /></Tooltip.Content></Tooltip.Portal></Tooltip.Root></Tooltip.Provider>
      </aside>
    </Tabs.Root>
  </section>;
}

function Architecture() {
  return <section id="architecture" className="section architecture-section">
    <div className="section-heading inverse"><div><span className="kicker">System design</span><h2>Snowflake orchestrates. Rules calculate. Humans decide.</h2></div><p>The trust boundary is explicit: language models retrieve and explain; deterministic code owns policy arithmetic.</p></div>
    <div className="architecture-flow">{architecture.map(({ icon: Icon, title, body }, i) => <div className="arch-wrap" key={title}><motion.div className={cn("arch-node", i === 4 && "agent-node")} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * .07 }}><span>{String(i + 1).padStart(2, "0")}</span><Icon /><b>{title}</b><p>{body}</p></motion.div>{i < architecture.length - 1 && <ChevronRight className="arch-arrow" />}</div>)}</div>
    <div className="guardrail-row"><div><ShieldCheck /><span><b>Output contract</b>No DENY. Uncertain cases become QUERY or REFER.</span></div><div><LockKeyhole /><span><b>Policy onboarding</b>Unsupported rules stop for explicit human approval.</span></div></div>
  </section>;
}

function Evidence() {
  return <section id="evidence" className="section evidence-section">
    <div className="section-heading"><div><span className="kicker">Measured evidence</span><h2>Proof, including the gaps</h2></div><p>Results from 30 fixed-seed, hand-calculated golden cases. We report the misses instead of relabelling them.</p></div>
    <div className="metric-grid">{metrics.map(([value, label, note], i) => <motion.div className="metric" key={label} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * .08 }}><span>0{i + 1}</span><strong>{value}</strong><b>{label}</b><p>{note}</p></motion.div>)}</div>
    <div className="honesty-note"><div><Badge variant="amber">Known gap</Badge><h3>Three PED outcomes and one payable amount still need work.</h3></div><p>ICD-10 extraction normalisation affected three waiting-period outcomes. A scenario override affected one amount. Strict citation recall is 55% because QUERY and REFER require decision-level citations.</p><Button variant="outline" asChild><a href="https://github.com/hulagerushikesh/cashlessiq/blob/main/docs/evaluation.md">Read evaluation <ExternalLink size={15} /></a></Button></div>
  </section>;
}

function Footer() {
  return <footer><div><Logo /><p>Cashless pre-authorisation review with cited policy logic.</p></div><div className="footer-links"><a href="#workspace">Demo</a><a href="#architecture">Architecture</a><a href="#evidence">Evidence</a><a href="https://github.com/hulagerushikesh/cashlessiq">GitHub</a></div><div className="footer-note"><span>Built by Team HiggsBosons</span><span>Snowflake CoCo CLI Hackathon 2026</span><span>Synthetic data only</span></div></footer>;
}

export function App() {
  return <><Header /><Hero /><Workspace /><Architecture /><Evidence /><Footer /></>;
}
