"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, BookOpenCheck, CheckCircle2, FileSearch, LoaderCircle, RefreshCw, ShieldCheck, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { Locale } from "@/lib/i18n";

type Fact = {
  effective_trust: string;
  fact: {
    record_id: string;
    value: unknown;
    predicate?: { canonical_key?: string };
    subject?: { entity_label?: string; document_metadata?: Array<{ company?: string; title?: string }> };
    qualifiers?: { reference_period?: number | string; normalized_unit?: string; scope_boundary?: string };
    evidence?: Array<{ pdf_page?: number; quote?: string; row_header?: string; column_header?: string }>;
  };
};
type Preview = { pdf_page: number; quote?: string; coordinates?: number[]; coordinate_space?: { width: number; height: number }; highlight_precision: string; image_url: string; source_sha256: string };
type Analytics = {
  inventory: { fact_count: number; company_count: number };
  facets: { companies: Record<string, number>; predicates: Record<string, number>; years: Record<string, number>; units: Record<string, number>; categories: Record<string, number> };
  company_profiles: Array<{ company: string; fact_count: number; predicate_count: number; years: Array<number | string>; category_counts: Record<string, number>; evidence_items: number }>;
  series: Array<{ predicate: string; unit: string; points: Array<{ company: string; year: number | string; value: number; record_id: string; pdf_page?: number }> }>;
};

const labels = {
  en: { explorer: "Knowledge explorer", explorerSub: "Browse the controlled ESG ontology and verify every trusted fact against its source page.", schema: "Knowledge taxonomy", facts: "Trusted facts", preview: "Source verification", search: "Filter company or predicate", page: "PDF page", exact: "Evidence highlight", pageOnly: "Page-level evidence", company: "Company analysis", companySub: "Compare verified issuer disclosures without imputing missing values or claiming external truth.", profile: "Disclosure profile", trends: "Comparable numeric series", noSeries: "No multi-point numeric series is available for this filter.", reliability: "Reliability center", reliabilitySub: "Observe failures, controlled repair plans, validation and promotion as separate auditable states.", failures: "Recorded failures", plans: "Repair plans", executions: "Executions", observations: "Post-validation", policy: "Control policy", executionStates: "Execution states", executionStatesSub: "Auditable outcomes from controlled repair runs", strategies: "Top repair strategies", strategiesSub: "Reusable actions selected from the repair knowledge base", noStates: "No repair execution has been recorded.", noStrategies: "No repair strategy has been registered.", noRetry: "No silent retry", deterministic: "Deterministic post-validation", rollback: "Rollback evidence preserved", promotion: "Human-gated Tier B promotion" },
  zh: { explorer: "知识浏览器", explorerSub: "浏览受控 ESG 分类，并将每条可信事实直接核对到报告原页。", schema: "知识分类", facts: "可信事实", preview: "来源核验", search: "筛选公司或命题", page: "PDF 页", exact: "证据高亮", pageOnly: "仅页级证据", company: "公司分析", companySub: "仅比较已核验的发行人披露；不填补缺失值，也不宣称外部真实性。", profile: "披露画像", trends: "可比较数值序列", noSeries: "当前筛选没有多点数值序列。", reliability: "可靠性中心", reliabilitySub: "将失败、受控修复、验证与知识晋升分成可审计状态。", failures: "失败记录", plans: "修复计划", executions: "执行记录", observations: "验证观察", policy: "控制策略", executionStates: "执行状态", executionStatesSub: "受控修复运行产生的可审计结果", strategies: "主要修复策略", strategiesSub: "从失败—修复知识库选择的可复用动作", noStates: "尚无修复执行记录。", noStrategies: "尚未登记修复策略。", noRetry: "禁止静默重试", deterministic: "确定性后验证", rollback: "保留回滚证据", promotion: "人工把关的 B 级晋升" },
};

function Header({ title, sub, icon: Icon }: { title: string; sub: string; icon: typeof BookOpenCheck }) {
  return <div className="flex items-end justify-between"><div><h1 className="text-2xl font-semibold tracking-[-.03em] text-[#162d36]">{title}</h1><p className="mt-1 text-xs text-slate-500">{sub}</p></div><span className="grid size-10 place-items-center rounded-xl border border-[#dbe6e3] bg-white text-[#16836e]"><Icon className="size-5" /></span></div>;
}
function companyOf(item: Fact) { return item.fact.subject?.entity_label || item.fact.subject?.document_metadata?.[0]?.company || "Unknown entity"; }
function display(value: unknown) { return typeof value === "string" || typeof value === "number" ? String(value) : JSON.stringify(value); }
function factClaim(item: Fact, locale: Locale) {
  const company = companyOf(item);
  const predicate = item.fact.predicate?.canonical_key || "reported value";
  const value = display(item.fact.value);
  const unit = item.fact.qualifiers?.normalized_unit ? ` ${item.fact.qualifiers.normalized_unit}` : "";
  const period = item.fact.qualifiers?.reference_period;
  if (predicate === "governing_standard") return locale === "zh" ? `${company} 的独立鉴证业务采用 ${value} 标准。` : `${company}'s independent assurance engagement was conducted under ${value}.`;
  if (predicate === "assurance_provider") return locale === "zh" ? `${value} 为 ${company} 提供独立鉴证。` : `${value} provided independent assurance for ${company}.`;
  if (predicate === "incorporated_reference_pages") return locale === "zh" ? `${company} 的鉴证范围纳入报告第 ${value} 页。` : `${company}'s assurance scope incorporates report pages ${value}.`;
  const readable = predicate.replaceAll("_", " ").replaceAll("::", ", ");
  return locale === "zh"
    ? `${company}${period ? `在 ${period} 年` : ""}披露的“${readable}”为 ${value}${unit}。`
    : `${company} reported ${readable} of ${value}${unit}${period ? ` for ${period}` : ""}.`;
}

export function KnowledgeExplorer({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = labels[locale];
  const [facts, setFacts] = useState<Fact[]>([]);
  const [categories, setCategories] = useState<Array<{ category: string; fact_count: number; predicates: Record<string, number> }>>([]);
  const [query, setQuery] = useState("");
  const [predicate, setPredicate] = useState<string | null>(null);
  const [selected, setSelected] = useState<Fact | null>(null);
  const [evidenceIndex, setEvidenceIndex] = useState(0);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch(`${apiBase}/trusted-facts?limit=500`, { signal: controller.signal }).then((r) => r.json()),
      fetch(`${apiBase}/knowledge-schema`, { signal: controller.signal }).then((r) => r.json()),
    ]).then(([factPayload, schema]) => { const next = factPayload.records || []; setFacts(next); setSelected(next[0] || null); setCategories(schema.categories || []); }).catch(() => undefined);
    return () => controller.abort();
  }, [apiBase]);
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => fetch(`${apiBase}/facts/${selected.fact.record_id}/evidence/${evidenceIndex}/preview`).then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail || "Preview unavailable"); return r.json(); }).then((payload: Preview) => {
      if (cancelled) return;
      setPreview(payload);
      if (payload.highlight_precision === "resolving") timer = setTimeout(load, 650);
    }).catch((error) => { if (!cancelled) setPreviewError(error.message); });
    void load();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [apiBase, selected, evidenceIndex]);
  const filtered = useMemo(() => facts.filter((item) => {
    const haystack = `${companyOf(item)} ${item.fact.predicate?.canonical_key || ""}`.toLowerCase();
    return (!query || haystack.includes(query.toLowerCase())) && (!predicate || item.fact.predicate?.canonical_key === predicate);
  }), [facts, predicate, query]);
  const box = preview?.coordinates && preview.coordinate_space ? {
    left: `${preview.coordinates[0] / preview.coordinate_space.width * 100}%`, top: `${preview.coordinates[1] / preview.coordinate_space.height * 100}%`, width: `${(preview.coordinates[2] - preview.coordinates[0]) / preview.coordinate_space.width * 100}%`, height: `${(preview.coordinates[3] - preview.coordinates[1]) / preview.coordinate_space.height * 100}%`,
  } : null;
  return <div className="space-y-4"><Header title={t.explorer} sub={t.explorerSub} icon={BookOpenCheck} />
    <section className="grid min-h-[680px] gap-3 xl:grid-cols-[230px_390px_minmax(440px,1fr)]">
      <aside className="rounded-xl border border-[#dfe7e8] bg-white p-3"><p className="px-2 text-[9px] font-bold uppercase tracking-[.18em] text-slate-400">{t.schema}</p><button onClick={() => setPredicate(null)} className={`mt-2 flex w-full justify-between rounded-lg px-2 py-2 text-left text-[10px] ${predicate === null ? "bg-[#eaf5f2] text-[#126f60]" : "text-slate-500"}`}><span>All trusted knowledge</span><b>{facts.length}</b></button>{categories.map((category) => <div key={category.category} className="mt-2"><div className="flex justify-between px-2 py-1 text-[10px] font-semibold text-[#294951]"><span>{category.category}</span><span className="font-mono text-slate-400">{category.fact_count}</span></div>{Object.entries(category.predicates).slice(0, 7).map(([key, count]) => <button key={key} onClick={() => setPredicate(key)} className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[9px] ${predicate === key ? "bg-[#17343d] text-white" : "text-slate-500 hover:bg-slate-50"}`}><span className="truncate">{key.replaceAll("_", " ")}</span><span className="ml-2 font-mono">{count}</span></button>)}</div>)}</aside>
      <article className="overflow-hidden rounded-xl border border-[#dfe7e8] bg-white"><div className="border-b border-slate-100 p-3"><p className="text-[9px] font-bold uppercase tracking-[.18em] text-slate-400">{t.facts} · {filtered.length}</p><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.search} className="mt-2 h-8 text-[10px]" /></div><div className="max-h-[620px] overflow-y-auto">{filtered.map((item) => <button key={item.fact.record_id} onClick={() => { setSelected(item); setEvidenceIndex(0); setPreview(null); setPreviewError(null); }} className={`w-full border-b border-slate-100 p-3 text-left ${selected?.fact.record_id === item.fact.record_id ? "bg-[#eef7f4]" : "hover:bg-slate-50"}`}><div className="flex items-center gap-2"><Badge className="bg-emerald-100 text-[8px] text-emerald-800">Tier B</Badge><span className="truncate text-[9px] text-slate-500">{companyOf(item)}</span><span className="ml-auto font-mono text-[8px] text-slate-400">{item.fact.qualifiers?.reference_period || "—"}</span></div><p className="mt-2 line-clamp-2 text-[11px] font-semibold leading-4 text-[#18343d]">{factClaim(item, locale)}</p><p className="mt-1 truncate font-mono text-[8px] text-[#16836e]">{item.fact.predicate?.canonical_key} · {display(item.fact.value)} {item.fact.qualifiers?.normalized_unit}</p></button>)}</div></article>
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-3"><div className="flex items-center justify-between"><div><p className="text-[9px] font-bold uppercase tracking-[.18em] text-slate-400">{t.preview}</p><p className="mt-1 text-[10px] text-slate-500">{selected?.fact.subject?.document_metadata?.[0]?.title}</p></div>{preview && <Badge variant="outline" className="text-[8px]">{t.page} {preview.pdf_page} · {preview.highlight_precision === "resolving" ? "Locating evidence" : preview.coordinates ? t.exact : t.pageOnly}</Badge>}</div>{selected && <div className="mt-3 rounded-lg border border-[#cfe3de] bg-[#eef7f4] p-3"><p className="text-[8px] font-bold uppercase tracking-[.16em] text-[#16836e]">Knowledge claim</p><p className="mt-1 text-sm font-semibold leading-5 text-[#18343d]">{factClaim(selected, locale)}</p><div className="mt-2 flex flex-wrap gap-2 font-mono text-[8px] text-slate-500"><span>subject: {companyOf(selected)}</span><span>predicate: {selected.fact.predicate?.canonical_key}</span><span>value: {display(selected.fact.value)}</span></div></div>}{selected && (selected.fact.evidence?.length || 0) > 1 && <div className="mt-2 flex gap-1 overflow-x-auto">{selected.fact.evidence?.map((item, index) => <button key={index} onClick={() => { setEvidenceIndex(index); setPreview(null); setPreviewError(null); }} className={`rounded px-2 py-1 font-mono text-[8px] ${evidenceIndex === index ? "bg-[#17343d] text-white" : "bg-slate-100 text-slate-500"}`}>E{index + 1} · p.{item.pdf_page}</button>)}</div>}
        <div className="mt-3 flex min-h-[520px] items-start justify-center overflow-auto rounded-lg bg-[#e8edeb] p-3">{preview ? <div className="relative w-full max-w-[720px] shadow-xl"><img src={`${apiBase}${preview.image_url}`} alt={`PDF page ${preview.pdf_page}`} className="block h-auto w-full" />{box && <span className="pointer-events-none absolute border-2 border-[#e33d55] bg-[#ffef66]/45 shadow-[0_0_0_1px_rgba(255,255,255,.8)]" style={box} />}</div> : previewError ? <div className="m-auto max-w-sm text-center"><AlertTriangle className="mx-auto size-5 text-amber-600" /><p className="mt-2 text-[10px] text-slate-500">{previewError}</p></div> : <LoaderCircle className="m-auto size-5 animate-spin text-[#16836e]" />}</div>{selected?.fact.evidence?.[evidenceIndex] && <div className="mt-3 rounded-lg border border-slate-100 bg-[#f8faf9] p-3"><p className="text-[10px] leading-5 text-slate-600">{selected.fact.evidence[evidenceIndex].quote}</p><p className="mt-2 font-mono text-[8px] text-slate-400">{preview?.highlight_precision || "resolving"} · {preview?.source_sha256?.slice(0, 16)}…</p></div>}</article>
    </section>
  </div>;
}

export function CompanyAnalysis({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = labels[locale]; const [data, setData] = useState<Analytics | null>(null); const [company, setCompany] = useState("");
  useEffect(() => { fetch(`${apiBase}/analytics`).then((r) => r.json()).then(setData).catch(() => undefined); }, [apiBase]);
  const effectiveCompany = company || data?.company_profiles[0]?.company || "";
  const profile = data?.company_profiles.find((item) => item.company === effectiveCompany) || data?.company_profiles[0];
  const maxCategory = Math.max(1, ...Object.values(profile?.category_counts || {}));
  const series = data?.series.filter((item) => item.points.some((point) => point.company === effectiveCompany)).slice(0, 6) || [];
  return <div className="space-y-4"><Header title={t.company} sub={t.companySub} icon={BarChart3} /><section className="rounded-xl border border-[#dfe7e8] bg-white p-4"><div className="flex flex-wrap items-center gap-3"><select className="h-9 min-w-72 rounded-md border border-slate-200 bg-white px-3 text-xs" value={effectiveCompany} onChange={(e) => setCompany(e.target.value)}>{data?.company_profiles.map((item) => <option key={item.company}>{item.company}</option>)}</select><span className="ml-auto text-[9px] text-slate-400">Tier B only · missing values not imputed</span></div><div className="mt-4 grid gap-3 sm:grid-cols-4">{[["Facts", profile?.fact_count], ["Predicates", profile?.predicate_count], ["Evidence", profile?.evidence_items], ["Periods", profile?.years.length]].map(([name, value]) => <div key={String(name)} className="rounded-lg bg-[#f4f8f7] p-3"><p className="text-[9px] uppercase tracking-wider text-slate-400">{name}</p><p className="mt-1 font-mono text-2xl font-semibold text-[#18343d]">{value ?? "—"}</p></div>)}</div></section><section className="grid gap-4 xl:grid-cols-2"><article className="rounded-xl border border-[#dfe7e8] bg-white p-4"><h2 className="text-sm font-semibold text-[#18343d]">{t.profile}</h2><div className="mt-4 space-y-3">{Object.entries(profile?.category_counts || {}).sort((a,b) => b[1]-a[1]).map(([name, value]) => <div key={name}><div className="flex justify-between text-[10px]"><span className="text-slate-500">{name}</span><b className="font-mono">{value}</b></div><div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-[#16836e]" style={{ width: `${value / maxCategory * 100}%` }} /></div></div>)}</div></article><article className="rounded-xl border border-[#dfe7e8] bg-white p-4"><h2 className="text-sm font-semibold text-[#18343d]">{t.trends}</h2>{series.length ? <div className="mt-3 space-y-2">{series.map((item) => <div key={`${item.predicate}-${item.unit}`} className="rounded-lg border border-slate-100 p-3"><div className="flex justify-between"><span className="truncate font-mono text-[9px] text-[#16836e]">{item.predicate}</span><span className="text-[8px] text-slate-400">{item.unit}</span></div><div className="mt-2 flex gap-2 overflow-x-auto">{item.points.filter((point) => point.company === effectiveCompany).map((point) => <span key={point.record_id} className="rounded bg-[#f3f7f6] px-2 py-1 font-mono text-[9px] text-slate-600">{point.year}: <b>{point.value}</b></span>)}</div></div>)}</div> : <p className="mt-12 text-center text-xs text-slate-400">{t.noSeries}</p>}</article></section></div>;
}

export function ReliabilityCenter({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = labels[locale];
  const [data, setData] = useState<{ counts: Record<string, number>; states: Record<string, number>; strategies: Record<string, number>; recent_events: Array<Record<string, unknown>> } | null>(null);
  useEffect(() => { fetch(`${apiBase}/repair-lifecycle`).then((r) => r.json()).then(setData).catch(() => undefined); }, [apiBase]);
  const states = Object.entries(data?.states || {});
  const strategies = Object.entries(data?.strategies || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxState = Math.max(1, ...states.map(([, count]) => count));
  const maxStrategy = Math.max(1, ...strategies.map(([, count]) => count));
  const policyItems = [t.noRetry, t.deterministic, t.rollback, t.promotion];
  const stateColors: Record<string, string> = {
    promoted: "bg-[#16836e]",
    rolled_back: "bg-[#c87838]",
    blocked_preflight: "bg-[#526f78]",
  };
  return <div className="space-y-3">
    <Header title={t.reliability} sub={t.reliabilitySub} icon={Wrench} />
    <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {[[t.failures, data?.counts.failures, AlertTriangle], [t.plans, data?.counts.plans, FileSearch], [t.executions, data?.counts.executions, RefreshCw], [t.observations, data?.counts.observations, CheckCircle2]].map(([name, value, Icon]) => <article key={String(name)} className="flex items-center gap-3 rounded-xl border border-[#dfe7e8] bg-white px-4 py-2.5 shadow-[0_4px_18px_rgba(29,57,64,.025)]"><span className="grid size-8 shrink-0 place-items-center rounded-lg bg-[#edf7f4] text-[#16836e]"><Icon className="size-4" /></span><div><p className="font-mono text-xl font-semibold leading-none text-[#18343d]">{String(value ?? "—")}</p><p className="mt-1 text-[9px] text-slate-500">{String(name)}</p></div></article>)}
    </section>
    <section className="grid items-stretch gap-4 xl:grid-cols-[.95fr_1.05fr_1.35fr]">
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-3.5 shadow-[0_4px_18px_rgba(29,57,64,.025)]">
        <h2 className="text-sm font-semibold text-[#18343d]">{t.executionStates}</h2>
        <p className="mt-1 text-[9px] text-slate-400">{t.executionStatesSub}</p>
        <div className="mt-3 space-y-2.5">{states.length ? states.map(([name, count]) => <div key={name}><div className="flex items-center justify-between text-[9px]"><span className="capitalize text-slate-600">{name.replaceAll("_", " ")}</span><b className="font-mono text-[#18343d]">{count}</b></div><div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${stateColors[name] || "bg-[#527984]"}`} style={{ width: `${Math.max(8, count / maxState * 100)}%` }} /></div></div>) : <p className="py-6 text-center text-[10px] text-slate-400">{t.noStates}</p>}</div>
      </article>
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-3.5 shadow-[0_4px_18px_rgba(29,57,64,.025)]">
        <h2 className="text-sm font-semibold text-[#18343d]">{t.policy}</h2>
        <div className="mt-3 grid grid-cols-2 gap-2">{policyItems.map((item) => <div key={item} className="flex min-h-12 items-center gap-2 rounded-lg border border-emerald-100 bg-emerald-50/55 px-2.5 py-2 text-[9px] font-medium leading-4 text-emerald-800"><span className="grid size-5 shrink-0 place-items-center rounded-md bg-white text-[#16836e]"><ShieldCheck className="size-3" /></span>{item}</div>)}</div>
      </article>
      <article className="rounded-xl border border-[#dfe7e8] bg-white p-3.5 shadow-[0_4px_18px_rgba(29,57,64,.025)]">
        <h2 className="text-sm font-semibold text-[#18343d]">{t.strategies}</h2>
        <p className="mt-1 text-[9px] text-slate-400">{t.strategiesSub}</p>
        <div className="mt-2.5 space-y-1.5">{strategies.length ? strategies.map(([name, count], index) => <div key={name} className="grid grid-cols-[18px_minmax(0,1fr)_28px] items-center gap-2"><span className="font-mono text-[8px] text-slate-400">{String(index + 1).padStart(2, "0")}</span><div className="min-w-0"><div className="flex items-center justify-between gap-2"><span className="truncate font-mono text-[8px] text-slate-600">{name.replace(/^RS-/, "").replaceAll("-", " ")}</span></div><div className="mt-1 h-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-[#16836e]" style={{ width: `${Math.max(5, count / maxStrategy * 100)}%` }} /></div></div><b className="text-right font-mono text-[9px] text-[#18343d]">{count}</b></div>) : <p className="py-6 text-center text-[10px] text-slate-400">{t.noStrategies}</p>}</div>
      </article>
    </section>
  </div>;
}
