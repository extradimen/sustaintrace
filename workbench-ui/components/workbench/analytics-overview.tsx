"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowUpRight,
  BookOpenText,
  CheckCircle2,
  CircleAlert,
  Database,
  FileSearch,
  Fingerprint,
  Network,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { Locale } from "@/lib/i18n";

type Inventory = {
  unique_reports: number;
  fact_records: number;
  trusted_tier_b: number;
  failure_records: number;
  failure_signatures: number;
};

type Job = {
  job_id: string;
  state: string;
  created_at: string;
  source: { original_filename: string; sha256: string };
  analysis?: {
    atomic_fact_candidates?: number;
    projection_validated_candidates?: number;
    failure_records?: number;
  };
};

const copy = {
  en: {
    eyebrow: "Research overview",
    title: "Evidence-grounded ESG intelligence",
    intro: "A compact view of what the system extracted, what is reusable, and what still needs repair.",
    reports: "Reports",
    reportsNote: "unique source PDFs",
    facts: "Atomic facts",
    factsNote: "with provenance records",
    trusted: "Trusted knowledge",
    trustedNote: "independently reviewed · Tier B",
    failures: "Failure archive",
    failuresNote: "controlled signatures",
    qualification: "Knowledge qualification",
    qualificationSub: "Candidates retained through trust gates",
    candidate: "Candidate facts",
    accepted: "Trusted Tier B",
    held: "Held for review",
    failureTitle: "Failure intelligence",
    failureSub: "Most frequent deterministic signatures",
    noFailure: "Failure signature data will appear when the local engine is connected.",
    activity: "Analysis activity",
    activitySub: "Recent locally registered reports",
    viewAll: "View library",
    report: "Report",
    status: "Status",
    factsCol: "Facts",
    issues: "Issues",
    provenance: "Provenance & audit",
    provenanceSub: "Every reusable claim remains connected to source evidence.",
    sourceFrozen: "Source integrity",
    sourceFrozenNote: "SHA-256 registered before analysis",
    evidenceCoords: "Evidence coordinates",
    evidenceCoordsNote: "page · table · row · column · cell",
    refusal: "Controlled refusal",
    refusalNote: "unsupported claims enter the failure archive",
    graph: "Knowledge graph",
    graphNote: "facts, evidence and repair paths stay linked",
    emptyJobs: "No new local analysis jobs yet.",
    completed: "Completed",
    parsing: "Parsing",
    archived: "Archived",
    unavailable: "Engine offline",
    engineText: "Local engine connected",
    rateSuffix: "independently reviewed and reusable.",
    pipelineYield: "Pipeline yield",
    pipelineYieldSub: "Recent candidate and accepted facts",
  },
  zh: {
    eyebrow: "研究总览",
    title: "证据驱动的 ESG 可信知识",
    intro: "在一个页面查看系统提取了什么、哪些知识可复用、哪些仍需修复。",
    reports: "报告",
    reportsNote: "唯一来源 PDF",
    facts: "原子事实",
    factsNote: "均保留来源记录",
    trusted: "可信知识",
    trustedNote: "独立审核 · B 级",
    failures: "失败档案",
    failuresNote: "受控失败签名",
    qualification: "知识资格漏斗",
    qualificationSub: "候选事实通过可信门后的保留情况",
    candidate: "候选事实",
    accepted: "可信 B 级",
    held: "待审核或修复",
    failureTitle: "失败模式分析",
    failureSub: "最常见的确定性失败签名",
    noFailure: "连接本地引擎后显示失败签名分布。",
    activity: "分析活动",
    activitySub: "最近登记的本地报告",
    viewAll: "查看报告库",
    report: "报告",
    status: "状态",
    factsCol: "事实",
    issues: "问题",
    provenance: "来源与审计",
    provenanceSub: "每条可复用事实始终连接到原始证据。",
    sourceFrozen: "来源完整性",
    sourceFrozenNote: "分析前登记 SHA-256",
    evidenceCoords: "证据坐标",
    evidenceCoordsNote: "页 · 表 · 行 · 列 · 单元格",
    refusal: "受控拒绝",
    refusalNote: "无充分证据的主张进入失败库",
    graph: "知识关系",
    graphNote: "事实、证据与修复路径保持关联",
    emptyJobs: "尚无新的本地分析任务。",
    completed: "已完成",
    parsing: "解析中",
    archived: "已归档",
    unavailable: "引擎离线",
    engineText: "本地引擎已连接",
    rateSuffix: "已完成独立审核，可直接复用。",
    pipelineYield: "流水线产出",
    pipelineYieldSub: "最近任务的候选事实与通过事实",
  },
};

function stateLabel(state: string, locale: Locale) {
  const t = copy[locale];
  if (state === "local_analysis_completed") return t.completed;
  if (state === "parsing" || state === "source_frozen" || state === "parsed") return t.parsing;
  return t.archived;
}

export function AnalyticsOverview({
  apiBase,
  locale,
  inventory,
  engineOnline,
  onOpenLibrary,
}: {
  apiBase: string;
  locale: Locale;
  inventory: Inventory;
  engineOnline: boolean;
  onOpenLibrary: () => void;
}) {
  const t = copy[locale];
  const [jobs, setJobs] = useState<Job[]>([]);
  const [signatures, setSignatures] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!engineOnline) return;
    const controller = new AbortController();
    Promise.all([
      fetch(`${apiBase}/jobs?limit=6`, { signal: controller.signal }).then((response) => response.ok ? response.json() : null),
      fetch(`${apiBase}/failures?limit=20`, { signal: controller.signal }).then((response) => response.ok ? response.json() : null),
    ]).then(([jobPayload, failurePayload]) => {
      setJobs(jobPayload?.records || []);
      setSignatures(failurePayload?.signature_counts || {});
    }).catch(() => undefined);
    return () => controller.abort();
  }, [apiBase, engineOnline]);

  const held = Math.max(inventory.fact_records - inventory.trusted_tier_b, 0);
  const qualification = [
    { name: t.accepted, value: inventory.trusted_tier_b, color: "#0e8f78" },
    { name: t.held, value: held, color: "#d9e2e5" },
  ];
  const failureData = useMemo(() => Object.entries(signatures)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, value]) => ({ name: name.replaceAll("_", " "), value })), [signatures]);
  const activityData = [...jobs].reverse().map((item, index) => ({
    index: index + 1,
    facts: item.analysis?.atomic_fact_candidates || 0,
    accepted: item.analysis?.projection_validated_candidates || 0,
  }));
  const metrics = [
    { label: t.reports, value: inventory.unique_reports, note: t.reportsNote, icon: BookOpenText, accent: "text-[#246b72]", tint: "bg-[#e7f2f1]" },
    { label: t.facts, value: inventory.fact_records, note: t.factsNote, icon: FileSearch, accent: "text-[#375a7f]", tint: "bg-[#edf2f8]" },
    { label: t.trusted, value: inventory.trusted_tier_b, note: t.trustedNote, icon: ShieldCheck, accent: "text-[#16836e]", tint: "bg-[#e9f5ef]" },
    { label: t.failures, value: inventory.failure_records, note: `${inventory.failure_signatures} ${t.failuresNote}`, icon: CircleAlert, accent: "text-[#a15f2c]", tint: "bg-[#f9efe5]" },
  ];

  return (
    <div className="space-y-4">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#16836e]">{t.eyebrow}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-[-.03em] text-[#162d36]">{t.title}</h1>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{t.intro}</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <span className={`size-2 rounded-full ${engineOnline ? "bg-emerald-500" : "bg-amber-500"}`} />
          {engineOnline ? t.engineText : t.unavailable}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {metrics.map((metric) => (
          <article key={metric.label} className="rounded-xl border border-[#dfe7e8] bg-white px-4 py-3 shadow-[0_4px_18px_rgba(29,57,64,.035)]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold text-slate-500">{metric.label}</p>
                <p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-[#18343d]">{metric.value.toLocaleString()}</p>
              </div>
              <span className={`grid size-9 place-items-center rounded-lg ${metric.tint} ${metric.accent}`}><metric.icon className="size-[17px]" /></span>
            </div>
            <p className="mt-2 truncate text-[10px] text-slate-400">{metric.note}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_270px]">
        <article className="rounded-xl border border-[#dfe7e8] bg-white p-4 shadow-[0_4px_18px_rgba(29,57,64,.035)]">
          <div className="flex items-start justify-between">
            <div><h2 className="text-sm font-semibold text-[#18343d]">{t.qualification}</h2><p className="mt-1 text-[10px] text-slate-400">{t.qualificationSub}</p></div>
            <Database className="size-4 text-[#16836e]" />
          </div>
          <div className="mt-3 grid grid-cols-[150px_minmax(0,1fr)] items-center gap-2">
            <ChartContainer config={{ value: { label: t.facts, color: "#0e8f78" } }} className="h-[150px] w-[150px] aspect-square">
              <PieChart><Pie data={qualification} dataKey="value" nameKey="name" innerRadius={47} outerRadius={68} paddingAngle={2}>{qualification.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><ChartTooltip content={<ChartTooltipContent hideLabel />} /></PieChart>
            </ChartContainer>
            <div className="space-y-3">
              <div><div className="flex justify-between text-[11px]"><span className="text-slate-500">{t.candidate}</span><span className="font-mono font-semibold">{inventory.fact_records.toLocaleString()}</span></div><div className="mt-1.5 h-1.5 rounded-full bg-slate-100"><div className="h-full w-full rounded-full bg-[#355f68]" /></div></div>
              <div><div className="flex justify-between text-[11px]"><span className="text-slate-500">{t.accepted}</span><span className="font-mono font-semibold text-[#16836e]">{inventory.trusted_tier_b.toLocaleString()}</span></div><div className="mt-1.5 h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-[#0e8f78]" style={{ width: `${Math.max(4, inventory.fact_records ? inventory.trusted_tier_b / inventory.fact_records * 100 : 0)}%` }} /></div></div>
              <p className="text-[10px] leading-4 text-slate-400">{((inventory.trusted_tier_b / Math.max(inventory.fact_records, 1)) * 100).toFixed(1)}% {t.rateSuffix}</p>
            </div>
          </div>
        </article>

        <article className="rounded-xl border border-[#dfe7e8] bg-white p-4 shadow-[0_4px_18px_rgba(29,57,64,.035)]">
          <div className="flex items-start justify-between"><div><h2 className="text-sm font-semibold text-[#18343d]">{t.failureTitle}</h2><p className="mt-1 text-[10px] text-slate-400">{t.failureSub}</p></div><CircleAlert className="size-4 text-[#b26a32]" /></div>
          {failureData.length ? <ChartContainer config={{ value: { label: t.failures, color: "#b26a32" } }} className="mt-3 h-[150px] w-full aspect-auto">
            <BarChart data={failureData} layout="vertical" margin={{ left: 0, right: 10, top: 0, bottom: 0 }}><CartesianGrid horizontal={false} stroke="#edf1f2" /><XAxis type="number" hide /><YAxis type="category" dataKey="name" width={110} tickLine={false} axisLine={false} tick={{ fontSize: 8 }} tickFormatter={(value) => String(value).slice(0, 18)} /><ChartTooltip content={<ChartTooltipContent hideLabel />} /><Bar dataKey="value" fill="#b26a32" radius={[0, 4, 4, 0]} barSize={11} /></BarChart>
          </ChartContainer> : <div className="mt-3 grid h-[150px] place-items-center rounded-lg bg-[#faf8f5] px-6 text-center text-[11px] leading-5 text-slate-400">{t.noFailure}</div>}
        </article>

        <article className="rounded-xl border border-[#dfe7e8] bg-[#17343d] p-4 text-white shadow-[0_7px_24px_rgba(23,52,61,.12)]">
          <div className="flex items-start justify-between"><div><h2 className="text-sm font-semibold">{t.provenance}</h2><p className="mt-1 text-[10px] leading-4 text-slate-300">{t.provenanceSub}</p></div><Fingerprint className="size-4 text-[#81d3bd]" /></div>
          <div className="mt-4 space-y-3">
            {[
              [ShieldCheck, t.sourceFrozen, t.sourceFrozenNote],
              [Fingerprint, t.evidenceCoords, t.evidenceCoordsNote],
              [CircleAlert, t.refusal, t.refusalNote],
              [Network, t.graph, t.graphNote],
            ].map(([Icon, title, note]) => {
              const Glyph = Icon as typeof ShieldCheck;
              return <div key={String(title)} className="flex gap-2.5"><span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-md bg-white/8 text-[#81d3bd]"><Glyph className="size-3.5" /></span><div><p className="text-[11px] font-medium text-slate-100">{String(title)}</p><p className="mt-0.5 text-[9px] leading-4 text-slate-400">{String(note)}</p></div></div>;
            })}
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(300px,.7fr)]">
        <article className="overflow-hidden rounded-xl border border-[#dfe7e8] bg-white shadow-[0_4px_18px_rgba(29,57,64,.035)]">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3"><div><h2 className="text-sm font-semibold text-[#18343d]">{t.activity}</h2><p className="mt-0.5 text-[10px] text-slate-400">{t.activitySub}</p></div><Button variant="ghost" size="sm" className="h-7 text-[10px] text-[#16836e]" onClick={onOpenLibrary}>{t.viewAll}<ArrowUpRight className="size-3" /></Button></div>
          {jobs.length ? <div><div className="grid grid-cols-[minmax(0,1fr)_100px_60px_60px] border-b border-slate-100 bg-[#f7f9f9] px-4 py-2 text-[9px] font-bold uppercase tracking-[.12em] text-slate-400"><span>{t.report}</span><span>{t.status}</span><span className="text-right">{t.factsCol}</span><span className="text-right">{t.issues}</span></div>{jobs.slice(0, 4).map((item) => <div key={item.job_id} className="grid grid-cols-[minmax(0,1fr)_100px_60px_60px] items-center border-b border-slate-100 px-4 py-2.5 text-[11px] last:border-0"><div className="min-w-0"><p className="truncate font-medium text-slate-700">{item.source.original_filename}</p><p className="mt-0.5 truncate font-mono text-[8px] text-slate-400">{item.source.sha256?.slice(0, 18)}…</p></div><Badge variant="outline" className="w-fit border-emerald-200 bg-emerald-50 text-[9px] text-emerald-700">{stateLabel(item.state, locale)}</Badge><span className="text-right font-mono text-slate-600">{item.analysis?.atomic_fact_candidates ?? "—"}</span><span className="text-right font-mono text-[#a15f2c]">{item.analysis?.failure_records ?? "—"}</span></div>)}</div> : <div className="grid h-[150px] place-items-center text-xs text-slate-400">{t.emptyJobs}</div>}
        </article>

        <article className="rounded-xl border border-[#dfe7e8] bg-white p-4 shadow-[0_4px_18px_rgba(29,57,64,.035)]">
          <div className="flex items-start justify-between"><div><h2 className="text-sm font-semibold text-[#18343d]">{t.pipelineYield}</h2><p className="mt-1 text-[10px] text-slate-400">{t.pipelineYieldSub}</p></div><CheckCircle2 className="size-4 text-[#16836e]" /></div>
          {activityData.length ? <ChartContainer config={{ facts: { label: t.factsCol, color: "#486b73" }, accepted: { label: t.accepted, color: "#0e8f78" } }} className="mt-3 h-[126px] w-full aspect-auto"><AreaChart data={activityData} margin={{ left: -20, right: 5, top: 5, bottom: 0 }}><defs><linearGradient id="fillFacts" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#486b73" stopOpacity={0.25}/><stop offset="95%" stopColor="#486b73" stopOpacity={0.02}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#edf1f2" /><XAxis dataKey="index" tickLine={false} axisLine={false} tick={{ fontSize: 9 }} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 9 }} /><ChartTooltip content={<ChartTooltipContent />} /><Area type="monotone" dataKey="facts" stroke="#486b73" fill="url(#fillFacts)" strokeWidth={2} /><Area type="monotone" dataKey="accepted" stroke="#0e8f78" fill="transparent" strokeWidth={2} /></AreaChart></ChartContainer> : <div className="mt-3 grid h-[126px] place-items-center text-[11px] text-slate-400">{t.emptyJobs}</div>}
        </article>
      </section>
    </div>
  );
}
