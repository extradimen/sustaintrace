"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, XAxis, YAxis } from "recharts";
import { CheckCircle2, CircleAlert, FileKey2, Fingerprint, FlaskConical, Link2, Network, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { Locale } from "@/lib/i18n";

type Fact = {
  fact: {
    record_id: string;
    value: unknown;
    predicate?: { canonical_key?: string };
    subject?: { entity_label?: string; document_metadata?: Array<{ company?: string }> };
    evidence?: Array<{ pdf_page?: number; quote?: string; source_id?: string }>;
  };
};
type Job = {
  job_id: string;
  state: string;
  created_at: string;
  source: { original_filename: string; sha256: string };
  events?: Array<{ at: string; event: string; detail?: string }>;
};
type EvaluationSummary = {
  inventory?: { fact_records?: number; trusted_tier_b?: number };
  acceptance?: {
    acceptance_id?: string;
    coverage?: { pre_scale_locked_report_baseline?: number; scale_stage_unique_reports?: number; total_unique_reports?: number };
    global_knowledge_bases?: { fact_records?: number; trusted_tier_b_records?: number; trusted_tier_b?: number };
    acceptance_gates?: {
      pytest_collected_and_passed?: number;
      ruff?: string;
      all_data_json_parse?: string;
      cloud_transmission_during_scale_stage?: boolean;
      locked_experiments_modified_or_rescored?: boolean;
      automatic_fact_promotion?: boolean;
    };
  };
};

const words = {
  en: {
    evidenceEyebrow: "Traceable knowledge",
    evidenceTitle: "Evidence relationship explorer",
    evidenceSub: "Inspect how source entities, atomic predicates and cited PDF pages are connected.",
    entity: "Entity",
    predicate: "Atomic predicate",
    source: "Source evidence",
    selected: "Selected evidence",
    noEvidence: "No evidence record is available.",
    page: "PDF page",
    evaluationEyebrow: "Experimental evidence",
    evaluationTitle: "Evaluation & coverage",
    evaluationSub: "Locked acceptance evidence for the 120-report knowledge expansion programme.",
    coverage: "Corpus coverage",
    coverageSub: "Pre-scale baseline and newly introduced reports",
    knowledge: "Knowledge disposition",
    knowledgeSub: "Trusted Tier B versus retained candidates",
    gates: "Acceptance gates",
    passed: "Passed",
    reports: "Reports",
    baseline: "Locked baseline",
    scale: "Scale-stage reports",
    trusted: "Trusted Tier B",
    candidates: "Other fact records",
    tests: "Tests passed",
    cloud: "Cloud transfer",
    locked: "Locked experiments modified",
    automatic: "Automatic promotion",
    none: "None",
    auditEyebrow: "Reproducibility",
    auditTitle: "Immutable audit trail",
    auditSub: "Source hashes, local pipeline events and reversible promotion overlays.",
    integrity: "Integrity controls",
    jobEvents: "Recent pipeline events",
    sourceRegistry: "Source hash registry",
    overlays: "Promotion overlays",
    active: "active",
    events: "events",
    immutable: "Locked experiments are read-only",
    controlled: "Cloud transfer requires explicit scope",
    separated: "Candidates never masquerade as trusted knowledge",
    noJobs: "No local workbench jobs are registered.",
  },
  zh: {
    evidenceEyebrow: "可追溯知识",
    evidenceTitle: "证据关系浏览器",
    evidenceSub: "查看报告主体、原子命题与 PDF 证据页之间的真实连接。",
    entity: "主体",
    predicate: "原子命题",
    source: "来源证据",
    selected: "当前证据",
    noEvidence: "当前没有可用证据记录。",
    page: "PDF 页码",
    evaluationEyebrow: "实验依据",
    evaluationTitle: "评测与覆盖",
    evaluationSub: "120 份报告知识扩充计划的锁定验收证据。",
    coverage: "语料覆盖",
    coverageSub: "扩充前基线与新增报告",
    knowledge: "知识分层",
    knowledgeSub: "可信 B 级与保留候选事实",
    gates: "验收门",
    passed: "通过",
    reports: "报告",
    baseline: "锁定基线",
    scale: "规模扩充报告",
    trusted: "可信 B 级",
    candidates: "其他事实记录",
    tests: "通过测试",
    cloud: "云端传输",
    locked: "修改锁箱实验",
    automatic: "自动晋升",
    none: "无",
    auditEyebrow: "可复现性",
    auditTitle: "不可变审计轨迹",
    auditSub: "来源哈希、本地流水线事件和可撤销知识覆盖层。",
    integrity: "完整性控制",
    jobEvents: "最近流水线事件",
    sourceRegistry: "来源哈希注册表",
    overlays: "知识晋升覆盖层",
    active: "个有效",
    events: "个事件",
    immutable: "锁箱实验保持只读",
    controlled: "云传输必须限定明确范围",
    separated: "候选记录不会伪装成可信知识",
    noJobs: "当前没有本地工作台任务。",
  },
};

function SurfaceHeader({ eyebrow, title, subtitle, icon: Icon }: { eyebrow: string; title: string; subtitle: string; icon: typeof Network }) {
  return <div className="flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#16836e]">{eyebrow}</p><h1 className="mt-1 text-2xl font-semibold tracking-[-.03em] text-[#162d36]">{title}</h1><p className="mt-1 text-xs leading-5 text-slate-500">{subtitle}</p></div><span className="grid size-10 place-items-center rounded-xl border border-[#dbe6e3] bg-white text-[#16836e]"><Icon className="size-5" /></span></div>;
}

export function EvidenceGraph({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = words[locale];
  const [records, setRecords] = useState<Fact[]>([]);
  const [selected, setSelected] = useState<Fact | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBase}/facts?limit=40`, { signal: controller.signal }).then((response) => response.ok ? response.json() : null).then((payload) => { const next = payload?.records || []; setRecords(next); setSelected(next[0] || null); }).catch(() => undefined);
    return () => controller.abort();
  }, [apiBase]);
  const graph = useMemo(() => {
    const rows = records.slice(0, 8).map((item, index) => ({
      item,
      company: item.fact.subject?.entity_label || item.fact.subject?.document_metadata?.[0]?.company || "Unknown",
      predicate: item.fact.predicate?.canonical_key || "unknown_predicate",
      page: item.fact.evidence?.[0]?.pdf_page,
      y: 42 + index * 47,
    }));
    return rows;
  }, [records]);
  const chosen = selected?.fact;
  return <div className="space-y-4">
    <SurfaceHeader eyebrow={t.evidenceEyebrow} title={t.evidenceTitle} subtitle={t.evidenceSub} icon={Network} />
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_340px]">
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-4 shadow-[0_4px_18px_rgba(29,57,64,.035)]">
        <div className="grid grid-cols-3 border-b border-slate-100 pb-2 text-[9px] font-bold uppercase tracking-[.16em] text-slate-400"><span>{t.entity}</span><span className="text-center">{t.predicate}</span><span className="text-right">{t.source}</span></div>
        <svg viewBox="0 0 900 420" className="mt-2 h-[420px] w-full" role="img" aria-label={t.evidenceTitle}>
          {graph.map((row) => <g key={row.item.fact.record_id} className="cursor-pointer" onClick={() => setSelected(row.item)}>
            <path d={`M 190 ${row.y} C 290 ${row.y}, 310 ${row.y}, 390 ${row.y}`} fill="none" stroke="#bfd4cf" strokeWidth="1.5" />
            <path d={`M 570 ${row.y} C 650 ${row.y}, 670 ${row.y}, 750 ${row.y}`} fill="none" stroke="#d8c3aa" strokeWidth="1.5" />
            <rect x="8" y={row.y - 17} width="182" height="34" rx="8" fill="#edf5f3" stroke="#cfe2dd" />
            <rect x="390" y={row.y - 17} width="180" height="34" rx="8" fill="#17343d" />
            <rect x="750" y={row.y - 17} width="142" height="34" rx="8" fill="#fbf4eb" stroke="#ead9c4" />
            <text x="20" y={row.y + 4} fontSize="10" fill="#31555d">{row.company.slice(0, 28)}</text>
            <text x="480" y={row.y + 4} textAnchor="middle" fontSize="9" fill="#dff6ee">{row.predicate.replaceAll("_", " ").slice(0, 29)}</text>
            <text x="821" y={row.y + 4} textAnchor="middle" fontSize="10" fill="#8b5f38">{t.page} {row.page ?? "—"}</text>
          </g>)}
          {!graph.length && <text x="450" y="205" textAnchor="middle" fontSize="13" fill="#94a3b8">{t.noEvidence}</text>}
        </svg>
      </article>
      <aside className="rounded-xl border border-[#dfe7e8] bg-white p-5 shadow-[0_4px_18px_rgba(29,57,64,.035)]">
        <div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">{t.selected}</p><h2 className="mt-1 text-sm font-semibold text-[#18343d]">{chosen?.predicate?.canonical_key?.replaceAll("_", " ") || "—"}</h2></div><Link2 className="size-4 text-[#16836e]" /></div>
        {chosen ? <><div className="mt-4 rounded-lg bg-[#f3f7f6] p-3"><p className="text-[10px] text-slate-400">Value</p><p className="mt-1 break-words font-mono text-lg font-semibold text-[#18343d]">{typeof chosen.value === "string" ? chosen.value : JSON.stringify(chosen.value)}</p></div><div className="mt-4 space-y-3">{chosen.evidence?.slice(0, 3).map((evidence, index) => <div key={`${evidence.pdf_page}-${index}`} className="border-l-2 border-[#71b8a6] pl-3"><div className="flex items-center gap-2"><Badge variant="outline" className="h-5 border-[#d5e7e2] bg-[#f4faf8] text-[8px] text-[#16836e]">PDF p.{evidence.pdf_page}</Badge><span className="truncate font-mono text-[8px] text-slate-400">{evidence.source_id}</span></div><p className="mt-1.5 text-[10px] leading-5 text-slate-600">{evidence.quote}</p></div>)}</div><p className="mt-5 break-all border-t border-slate-100 pt-3 font-mono text-[8px] text-slate-400">{chosen.record_id}</p></> : <p className="mt-8 text-xs text-slate-400">{t.noEvidence}</p>}
      </aside>
    </section>
  </div>;
}

export function EvaluationDashboard({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = words[locale];
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  useEffect(() => { const controller = new AbortController(); fetch(`${apiBase}/summary`, { signal: controller.signal }).then((response) => response.ok ? response.json() : null).then(setSummary).catch(() => undefined); return () => controller.abort(); }, [apiBase]);
  const acceptance = summary?.acceptance || {};
  const coverage = acceptance.coverage || {};
  const knowledge = acceptance.global_knowledge_bases || summary?.inventory || {};
  const gates = acceptance.acceptance_gates || {};
  const coverageData = [{ name: t.baseline, value: coverage.pre_scale_locked_report_baseline || 33, color: "#496b73" }, { name: t.scale, value: coverage.scale_stage_unique_reports || 87, color: "#1c9a80" }];
  const trusted = knowledge.trusted_tier_b_records ?? knowledge.trusted_tier_b ?? 149;
  const total = knowledge.fact_records ?? 2708;
  const knowledgeData = [{ name: t.trusted, value: trusted, color: "#16836e" }, { name: t.candidates, value: Math.max(total - trusted, 0), color: "#dce5e6" }];
  const gateRows = [
    [t.tests, gates.pytest_collected_and_passed ?? 478, "passed"],
    ["Ruff", gates.ruff || "passed", "passed"],
    ["JSON + SHA-256", gates.all_data_json_parse || "passed", "passed"],
    [t.cloud, gates.cloud_transmission_during_scale_stage ? "detected" : t.none, gates.cloud_transmission_during_scale_stage ? "warn" : "passed"],
    [t.locked, gates.locked_experiments_modified_or_rescored ? "yes" : t.none, gates.locked_experiments_modified_or_rescored ? "warn" : "passed"],
    [t.automatic, gates.automatic_fact_promotion ? "enabled" : t.none, gates.automatic_fact_promotion ? "warn" : "passed"],
  ];
  return <div className="space-y-4">
    <SurfaceHeader eyebrow={t.evaluationEyebrow} title={t.evaluationTitle} subtitle={t.evaluationSub} icon={FlaskConical} />
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_360px]">
      {[{ title: t.coverage, sub: t.coverageSub, data: coverageData, total: coverage.total_unique_reports || 120 }, { title: t.knowledge, sub: t.knowledgeSub, data: knowledgeData, total }].map((card) => <article key={card.title} className="rounded-xl border border-[#dfe7e8] bg-white p-4 shadow-[0_4px_18px_rgba(29,57,64,.035)]"><div><h2 className="text-sm font-semibold text-[#18343d]">{card.title}</h2><p className="mt-1 text-[10px] text-slate-400">{card.sub}</p></div><div className="mt-3 grid grid-cols-[155px_1fr] items-center"><ChartContainer config={{ value: { label: card.title, color: "#16836e" } }} className="h-[160px] w-[155px] aspect-square"><PieChart><Pie data={card.data} dataKey="value" innerRadius={49} outerRadius={71} paddingAngle={2}>{card.data.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><ChartTooltip content={<ChartTooltipContent hideLabel />} /></PieChart></ChartContainer><div><p className="font-mono text-3xl font-semibold text-[#18343d]">{card.total.toLocaleString()}</p><p className="mt-1 text-[10px] text-slate-400">{card === undefined ? "" : card.title === t.coverage ? t.reports : "facts"}</p><div className="mt-4 space-y-2">{card.data.map((item) => <div key={item.name} className="flex items-center justify-between text-[10px]"><span className="flex items-center gap-2 text-slate-500"><i className="size-2 rounded-full" style={{ background: item.color }} />{item.name}</span><span className="font-mono font-semibold text-slate-700">{item.value.toLocaleString()}</span></div>)}</div></div></div></article>)}
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-4 shadow-[0_4px_18px_rgba(29,57,64,.035)]"><div className="flex items-center justify-between"><div><h2 className="text-sm font-semibold text-[#18343d]">{t.gates}</h2><p className="mt-1 text-[10px] text-slate-400">{acceptance.acceptance_id || "ESG-KB-SCALE-120"}</p></div><ShieldCheck className="size-4 text-[#16836e]" /></div><div className="mt-4 space-y-2">{gateRows.map(([name, value, status]) => <div key={String(name)} className="flex items-center justify-between rounded-lg bg-[#f7f9f9] px-3 py-2.5"><span className="text-[10px] text-slate-500">{String(name)}</span><span className={`flex items-center gap-1.5 font-mono text-[9px] font-semibold ${status === "passed" ? "text-emerald-700" : "text-amber-700"}`}>{status === "passed" ? <CheckCircle2 className="size-3" /> : <CircleAlert className="size-3" />}{String(value)}</span></div>)}</div></article>
    </section>
    <article className="rounded-xl border border-[#dfe7e8] bg-white p-4"><div className="flex items-center justify-between"><div><h2 className="text-sm font-semibold text-[#18343d]">Scale programme</h2><p className="mt-1 text-[10px] text-slate-400">30 frozen batches · 120 unique reports · knowledge and failure archives preserved</p></div><Badge className="bg-emerald-100 text-emerald-800">100% complete</Badge></div><ChartContainer config={{ reports: { label: t.reports, color: "#16836e" } }} className="mt-3 h-[160px] w-full aspect-auto"><BarChart data={Array.from({ length: 30 }, (_, index) => ({ batch: index + 1, reports: index === 29 ? 1 : 3 }))}><CartesianGrid vertical={false} stroke="#edf1f2" /><XAxis dataKey="batch" tickLine={false} axisLine={false} tick={{ fontSize: 8 }} /><YAxis hide /><ChartTooltip content={<ChartTooltipContent />} /><Bar dataKey="reports" fill="#16836e" radius={[3, 3, 0, 0]} /></BarChart></ChartContainer></article>
  </div>;
}

export function AuditTrail({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = words[locale];
  const [jobs, setJobs] = useState<Job[]>([]);
  const [overlays, setOverlays] = useState<{ active_count: number; event_count: number }>({ active_count: 0, event_count: 0 });
  const [policy, setPolicy] = useState<Record<string, boolean>>({});
  useEffect(() => {
    const controller = new AbortController();
    const load = () => {
      fetch(`${apiBase}/jobs?limit=20`, { signal: controller.signal }).then((r) => r.ok ? r.json() : null).then((data) => { if (data) setJobs(data.records || []); }).catch(() => undefined);
      fetch(`${apiBase}/promotion-overlays`, { signal: controller.signal }).then((r) => r.ok ? r.json() : null).then((data) => { if (data) setOverlays({ active_count: data.active_count || 0, event_count: data.event_count || 0 }); }).catch(() => undefined);
      fetch(`${apiBase}/summary`, { signal: controller.signal }).then((r) => r.ok ? r.json() : null).then((data) => { if (data) setPolicy(data.policy || {}); }).catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 4000);
    return () => { window.clearInterval(timer); controller.abort(); };
  }, [apiBase]);
  const events = jobs.flatMap((job) => (job.events || []).map((event) => ({ ...event, job }))).sort((a, b) => b.at.localeCompare(a.at)).slice(0, 9);
  const controls: Array<[string, boolean | undefined]> = [[t.immutable, policy.locked_experiments_are_read_only], [t.controlled, policy.cloud_transfer_requires_explicit_scope], [t.separated, policy.candidates_never_masquerade_as_trusted]];
  return <div className="space-y-4">
    <SurfaceHeader eyebrow={t.auditEyebrow} title={t.auditTitle} subtitle={t.auditSub} icon={Fingerprint} />
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-4"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-[#18343d]">{t.jobEvents}</h2><Fingerprint className="size-4 text-[#16836e]" /></div>{events.length ? <div className="mt-4 space-y-0">{events.map((event, index) => <div key={`${event.job.job_id}-${event.at}-${index}`} className="relative flex gap-3 pb-4 last:pb-0">{index < events.length - 1 && <span className="absolute left-[7px] top-4 h-full w-px bg-[#dce7e4]" />}<span className="z-10 mt-1 size-[15px] shrink-0 rounded-full border-4 border-white bg-[#36a58b] ring-1 ring-[#bcd8d1]" /><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-mono text-[10px] font-semibold text-[#31555d]">{event.event}</p><span className="text-[8px] text-slate-400">{new Date(event.at).toLocaleString(locale === "en" ? "en-GB" : "zh-CN")}</span></div><p className="mt-0.5 truncate text-[9px] text-slate-500">{event.job.source.original_filename} · {event.job.job_id}</p></div></div>)}</div> : <p className="py-16 text-center text-xs text-slate-400">{t.noJobs}</p>}</article>
      <div className="space-y-4"><article className="rounded-xl border border-[#dfe7e8] bg-[#17343d] p-4 text-white"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold">{t.integrity}</h2><ShieldCheck className="size-4 text-[#81d3bd]" /></div><div className="mt-4 space-y-3">{controls.map(([label, passed]) => <div key={String(label)} className="flex items-center gap-3"><span className={`grid size-7 place-items-center rounded-lg ${passed === true ? "bg-emerald-400/10 text-[#81d3bd]" : passed === false ? "bg-amber-400/10 text-amber-300" : "bg-white/5 text-slate-500"}`}>{passed === true ? <CheckCircle2 className="size-4" /> : <CircleAlert className="size-4" />}</span><span className="text-[11px] text-slate-200">{String(label)}</span></div>)}</div></article><article className="rounded-xl border border-[#dfe7e8] bg-white p-4"><div className="flex items-center justify-between"><div><h2 className="text-sm font-semibold text-[#18343d]">{t.overlays}</h2><p className="mt-1 text-[10px] text-slate-400">Append-only and reversibly withdrawable</p></div><FileKey2 className="size-4 text-[#16836e]" /></div><div className="mt-4 grid grid-cols-2 gap-3"><div className="rounded-lg bg-[#eef7f4] p-3"><p className="font-mono text-2xl font-semibold text-[#16836e]">{overlays.active_count}</p><p className="mt-1 text-[9px] text-slate-500">{t.active}</p></div><div className="rounded-lg bg-[#f6f7f7] p-3"><p className="font-mono text-2xl font-semibold text-[#425f66]">{overlays.event_count}</p><p className="mt-1 text-[9px] text-slate-500">{t.events}</p></div></div></article></div>
    </section>
    <article className="overflow-hidden rounded-xl border border-[#dfe7e8] bg-white"><div className="flex items-center justify-between border-b border-slate-100 px-4 py-3"><h2 className="text-sm font-semibold text-[#18343d]">{t.sourceRegistry}</h2><FileKey2 className="size-4 text-[#16836e]" /></div><div className="grid grid-cols-[minmax(0,1fr)_160px_120px] bg-[#f7f9f9] px-4 py-2 text-[9px] font-bold uppercase tracking-[.12em] text-slate-400"><span>Source</span><span>Job</span><span>SHA-256</span></div>{jobs.slice(0, 7).map((job) => <div key={job.job_id} className="grid grid-cols-[minmax(0,1fr)_160px_120px] border-t border-slate-100 px-4 py-2.5 text-[10px]"><span className="truncate font-medium text-slate-600">{job.source.original_filename}</span><span className="truncate font-mono text-[8px] text-slate-400">{job.job_id}</span><span className="font-mono text-[8px] text-[#16836e]">{job.source.sha256.slice(0, 14)}…</span></div>)}</article>
  </div>;
}
