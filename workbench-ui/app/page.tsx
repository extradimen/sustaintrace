"use client";

import { useEffect, useRef, useState } from "react";
import { Archive, ArrowRight, Check, CircleAlert, Database, FileCheck2, FlaskConical, Languages, LayoutDashboard, LockKeyhole, Search, ShieldCheck, UploadCloud, Wrench, BarChart3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnalyticsOverview } from "@/components/workbench/analytics-overview";
import { FailureCenter } from "@/components/workbench/failure-center";
import { ReportLibrary } from "@/components/workbench/report-library";
import { AuditTrail, EvaluationDashboard } from "@/components/workbench/research-surfaces";
import { CompanyAnalysis, KnowledgeExplorer, ReliabilityCenter } from "@/components/workbench/knowledge-workspace";
import { htmlLanguage, languageCatalog, type Locale } from "@/lib/i18n";

const API_BASE = typeof window !== "undefined" && window.location.port === "5173"
  ? "http://127.0.0.1:8787/api/v1"
  : "/api/v1";
type View = "overview" | "library" | "knowledge" | "company" | "failures" | "evaluation" | "audit";
type FactResult = { effective_trust: string; fact: { record_id: string; value: unknown; trust_tier: string; predicate?: { canonical_key?: string }; subject?: { document_metadata?: Array<{ company?: string }>; task_id?: string }; evidence?: Array<{ pdf_page?: number; quote?: string }> } };
type WebMCPContext = { registerTool: (tool: { name: string; title: string; description: string; inputSchema: object; annotations: { readOnlyHint: boolean; untrustedContentHint: boolean }; execute: (input: unknown) => unknown | Promise<unknown> }, options: { signal: AbortSignal }) => void | Promise<void> };

const copy = {
  en: { product: "SustainTrace", productSub: "Evidence-grounded knowledge & controlled repair", workspace: "Analysis workspace", overview: "Overview", library: "Report intake", knowledge: "Knowledge explorer", company: "Company analysis", failures: "Reliability center", evaluation: "Evaluation", audit: "Audit trail", import: "Import PDFs", search: "Search knowledge", local: "Local-first", connected: "Engine connected", offline: "Engine offline", uploadTitle: "Start a report batch", uploadDesc: "Every source hash is frozen before parsing. Reports remain separate, resumable and auditable.", drop: "Drop PDFs here or choose files", dropSub: "Digital, scanned and complex tabular reports are supported.", change: "Choose other files", start: "Freeze sources & analyse", queued: "Analysis registered", uploadError: "The local analysis service is unavailable. The selected files remain on this device.", searchTitle: "Trusted knowledge browser", searchDesc: "Only independently reviewed Tier B records are returned as reusable knowledge.", queryPlaceholder: "Company or entity, e.g. BASF", runSearch: "Search", searching: "Searching", noMatch: "No trusted facts match this query.", tier: "Trusted Tier B", unknown: "Unknown entity", coming: "This analytical surface is connected to the same evidence model and will be enabled in the next UI increment.", selected: "selected", facts: "facts", validated: "validated", sourceHash: "source hash", evidenceCoordinates: "evidence coordinates", immutableAudit: "immutable audit", records: "Tier B records", readOnly: "read-only", provenancePreserved: "provenance preserved" },
  zh: { product: "SustainTrace", productSub: "证据驱动知识与受控修复", workspace: "分析工作台", overview: "总览", library: "报告导入", knowledge: "知识浏览", company: "公司分析", failures: "可靠性中心", evaluation: "实验评测", audit: "审计轨迹", import: "批量导入 PDF", search: "搜索知识", local: "本地优先", connected: "引擎已连接", offline: "引擎离线", uploadTitle: "开始一批报告分析", uploadDesc: "解析前逐份冻结来源哈希；报告任务相互独立、可恢复且可审计。", drop: "拖入多个 PDF 或点击选择", dropSub: "支持数字版、扫描版和复杂表格报告。", change: "重新选择文件", start: "冻结来源并分析", queued: "任务已登记", uploadError: "本地分析服务不可用。已选文件仍保留在本机。", searchTitle: "可信知识浏览器", searchDesc: "仅将完成独立审核的 B 级记录作为可复用知识返回。", queryPlaceholder: "公司或主体，例如 BASF", runSearch: "查询", searching: "查询中", noMatch: "没有匹配的可信事实。", tier: "可信 B 级", unknown: "未知主体", coming: "该分析界面使用同一证据模型，将在下一轮界面集成中启用。", selected: "已选", facts: "条事实", validated: "已验证", sourceHash: "来源哈希", evidenceCoordinates: "证据坐标", immutableAudit: "不可变审计", records: "条 B 级记录", readOnly: "只读", provenancePreserved: "保留来源证据" },
};
const nav: Array<{ id: View; icon: typeof LayoutDashboard }> = [{ id: "overview", icon: LayoutDashboard }, { id: "library", icon: Archive }, { id: "knowledge", icon: Database }, { id: "company", icon: BarChart3 }, { id: "failures", icon: Wrench }, { id: "evaluation", icon: FlaskConical }, { id: "audit", icon: ShieldCheck }];
function formatBytes(bytes: number) { return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`; }

function SustainTraceMark() {
  return <span className="grid size-8 shrink-0 place-items-center overflow-hidden rounded-[10px] bg-[#17343d] shadow-[0_3px_10px_rgba(23,52,61,.16)]" aria-hidden="true">
    <svg viewBox="0 0 32 32" className="size-7" fill="none" role="img">
      <path d="M8 8.5h9.2c3.3 0 5.3 1.7 5.3 4.2 0 2.4-1.9 3.8-5.2 3.8h-2.6c-3.3 0-5.2 1.4-5.2 3.8 0 2.2 1.8 3.7 4.7 3.7H20" stroke="#8CE0C7" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="8" cy="8.5" r="2.25" fill="#F4FFFB" stroke="#8CE0C7" strokeWidth="1.25" />
      <circle cx="17.1" cy="16.5" r="2.25" fill="#17343D" stroke="#8CE0C7" strokeWidth="1.5" />
      <circle cx="9.6" cy="20.3" r="1.4" fill="#8CE0C7" />
      <path d="m19.3 22.2 2 2.1 3.8-4.6" stroke="#F4FFFB" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </span>;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [locale, setLocale] = useState<Locale>("en");
  const [activeView, setActiveView] = useState<View>("overview");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [queued, setQueued] = useState(false);
  const [engineOnline, setEngineOnline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [factResults, setFactResults] = useState<FactResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [job, setJob] = useState<{ job_id: string; state: string; stage_index: number; analysis?: { atomic_fact_candidates?: number; projection_validated_candidates?: number; projection_quarantined?: number } } | null>(null);
  const [inventory, setInventory] = useState({ unique_reports: 120, fact_records: 2708, trusted_tier_b: 149, failure_records: 1032, failure_signatures: 32 });
  const t = copy[locale];
  useEffect(() => { document.documentElement.lang = htmlLanguage(locale); }, [locale]);
  const loadSummary = () => fetch(`${API_BASE}/summary`).then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then((payload) => { setInventory(payload.inventory); setEngineOnline(true); }).catch(() => setEngineOnline(false));
  useEffect(() => {
    void loadSummary();
    const timer = window.setInterval(() => { void loadSummary(); }, 4000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!job || !["parsing", "source_frozen", "parsed"].includes(job.state)) return;
    const timer = window.setInterval(() => fetch(`${API_BASE}/jobs/${job.job_id}`).then((response) => response.json()).then((payload) => { setJob(payload); if (payload.state === "local_analysis_completed") void loadSummary(); }).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [job]);
  const navigate = (view: View) => setActiveView(view);
  const acceptFiles = (candidates?: FileList | File[]) => { const next = Array.from(candidates || []).filter((candidate) => candidate.type === "application/pdf" || candidate.name.toLowerCase().endsWith(".pdf")); if (next.length) { setFiles(next); setQueued(false); setJob(null); setError(null); } };
  const startAnalysis = async () => {
    if (!files.length) return;
    setQueued(true); setError(null);
    try {
      for (const file of files) {
        const response = await fetch(`${API_BASE}/jobs`, { method: "POST", headers: { "Content-Type": "application/pdf", "X-Filename": encodeURIComponent(file.name) }, body: file });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "analysis job failed");
        setJob(payload);
      }
      setEngineOnline(true);
    } catch { setQueued(false); setEngineOnline(false); setError(t.uploadError); }
  };
  const searchFacts = async () => {
    setSearching(true); const query = new URLSearchParams({ limit: "20" }); if (searchQuery.trim()) query.set("company", searchQuery.trim());
    try { const response = await fetch(`${API_BASE}/facts?${query}`); const payload = await response.json(); setFactResults(payload.records || []); } catch { setFactResults([]); } finally { setSearching(false); }
  };
  useEffect(() => {
    const context = (document as Document & { modelContext?: WebMCPContext }).modelContext; if (!context?.registerTool) return; const lifecycle = new AbortController();
    void Promise.resolve(context.registerTool({ name: "read_esg_knowledge_summary", title: "Read ESG knowledge summary", description: "Read report, fact, trusted knowledge and failure counts without modifying data.", inputSchema: { type: "object", properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, untrustedContentHint: false }, execute: () => ({ inventory, engineOnline }) }, { signal: lifecycle.signal })).catch(() => undefined);
    void Promise.resolve(context.registerTool({ name: "search_trusted_esg_facts", title: "Search trusted ESG facts", description: "Search independently reviewed Tier B facts.", inputSchema: { type: "object", properties: { company: { type: "string" } }, required: ["company"], additionalProperties: false }, annotations: { readOnlyHint: true, untrustedContentHint: true }, execute: async (input) => { const company = typeof input === "object" && input !== null && "company" in input ? String((input as { company: unknown }).company).trim() : ""; if (!company) throw new Error("company must be non-empty"); const response = await fetch(`${API_BASE}/facts?${new URLSearchParams({ limit: "20", company })}`); if (!response.ok) throw new Error("query failed"); const payload = await response.json(); setSearchQuery(company); setFactResults(payload.records || []); setSearchOpen(true); return { company, matched: payload.pagination?.matched || 0 }; } }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  }, [engineOnline, inventory]);
  const renderWorkspace = () => {
    if (activeView === "overview") return <AnalyticsOverview apiBase={API_BASE} locale={locale} inventory={inventory} engineOnline={engineOnline} onOpenLibrary={() => setActiveView("library")} />;
    if (activeView === "library") return <ReportLibrary apiBase={API_BASE} locale={locale} onNewAnalysis={() => setUploadOpen(true)} />;
    if (activeView === "knowledge") return <KnowledgeExplorer apiBase={API_BASE} locale={locale} />;
    if (activeView === "company") return <CompanyAnalysis apiBase={API_BASE} locale={locale} />;
    if (activeView === "failures") return <div className="space-y-5"><ReliabilityCenter apiBase={API_BASE} locale={locale} /><FailureCenter apiBase={API_BASE} locale={locale} /></div>;
    if (activeView === "evaluation") return <EvaluationDashboard apiBase={API_BASE} locale={locale} />;
    return <AuditTrail apiBase={API_BASE} locale={locale} />;
  };

  return <div className="min-h-screen bg-[#f3f6f5] text-[#18343d]">
    <header className="sticky top-0 z-30 border-b border-[#dce5e4] bg-white/95 backdrop-blur-xl"><div className="mx-auto flex h-[58px] max-w-[1640px] items-center gap-4 px-4 lg:px-6">
      <div className="flex min-w-[205px] items-center gap-2.5"><SustainTraceMark /><div><p className="text-[12px] font-bold tracking-[.08em] text-[#18343d]">{t.product}</p><p className="text-[9px] text-slate-400">{t.productSub}</p></div></div>
      <div className="hidden h-6 w-px bg-slate-200 md:block" /><p className="hidden text-[11px] font-medium text-slate-500 md:block">{t.workspace}</p>
      <div className="ml-auto flex items-center gap-2"><Badge variant="outline" className="hidden h-8 border-[#d8e4e1] bg-[#f6faf8] text-[10px] font-medium text-[#47736b] sm:flex"><span className={`mr-1.5 size-1.5 rounded-full ${engineOnline ? "bg-emerald-500" : "bg-amber-500"}`} />{engineOnline ? t.connected : t.offline}</Badge><Select value={locale} onValueChange={(value) => setLocale(value as Locale)}><SelectTrigger size="sm" aria-label="Select language" className="h-8 min-w-[82px] border-0 bg-transparent px-2 text-[10px] text-slate-600 shadow-none hover:bg-slate-100"><Languages className="size-3.5" /><SelectValue>{languageCatalog.find((option) => option.value === locale)?.shortLabel}</SelectValue></SelectTrigger><SelectContent align="end" className="min-w-[150px]">{languageCatalog.map((option) => <SelectItem key={option.value} value={option.value} className="text-xs">{option.label}</SelectItem>)}</SelectContent></Select><Button variant="outline" size="sm" className="h-8 border-[#ccd9d8] px-3 text-[10px]" onClick={() => { setSearchOpen(true); if (!factResults.length) void searchFacts(); }}><Search className="size-3.5" /><span className="hidden sm:inline">{t.search}</span></Button><Button size="sm" className="h-8 bg-[#16836e] px-3 text-[10px] text-white hover:bg-[#116e5d]" onClick={() => setUploadOpen(true)}><UploadCloud className="size-3.5" />{t.import}</Button></div>
    </div></header>
    <div className="mx-auto grid max-w-[1640px] gap-0 lg:grid-cols-[184px_minmax(0,1fr)]"><aside className="border-r border-[#dce5e4] bg-[#edf3f1] px-3 py-4 lg:min-h-[calc(100vh-58px)]"><nav className="flex gap-1 overflow-x-auto lg:block lg:space-y-1">{nav.map((item) => { const active = activeView === item.id; return <button key={item.id} onClick={() => navigate(item.id)} className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium transition lg:w-full ${active ? "bg-white text-[#126f60] shadow-[0_2px_9px_rgba(36,70,72,.08)] ring-1 ring-[#dce8e5]" : "text-slate-500 hover:bg-white/60 hover:text-[#18343d]"}`}><item.icon className={`size-3.5 ${active ? "text-[#16836e]" : "text-slate-400"}`} />{t[item.id]}{item.id === "failures" && <span className="ml-auto hidden rounded bg-[#f7e8d9] px-1.5 py-0.5 font-mono text-[8px] text-[#a15f2c] lg:inline">{inventory.failure_signatures}</span>}</button>; })}</nav><div className="mt-5 hidden rounded-lg border border-[#dbe5e3] bg-white/70 p-3 lg:block"><div className="flex items-center gap-2 text-[10px] font-semibold text-[#47736b]"><LockKeyhole className="size-3.5" />{t.local}</div><p className="mt-2 font-mono text-[8px] leading-4 text-slate-400">{t.sourceHash} · {t.evidenceCoordinates} · {t.immutableAudit}</p></div></aside><main className="min-w-0 px-4 py-4 lg:px-5 xl:px-6">{renderWorkspace()}</main></div>

    <Dialog open={uploadOpen} onOpenChange={setUploadOpen}><DialogContent className="border-[#dce5e4] bg-white p-0 sm:max-w-xl"><DialogHeader className="border-b border-slate-100 px-5 py-4"><DialogTitle className="text-[#18343d]">{t.uploadTitle}</DialogTitle><DialogDescription className="text-xs">{t.uploadDesc}</DialogDescription></DialogHeader><div className="p-5">
      <input ref={inputRef} type="file" multiple accept="application/pdf,.pdf" className="hidden" onChange={(event) => acceptFiles(event.target.files || undefined)} /><button type="button" onClick={() => inputRef.current?.click()} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFiles(event.dataTransfer.files); }} className={`flex min-h-[132px] w-full flex-col items-center justify-center rounded-xl border border-dashed px-5 text-center transition ${dragging ? "border-[#16836e] bg-[#edf8f4]" : files.length ? "border-emerald-300 bg-emerald-50/40" : "border-[#cbd8d8] bg-[#f7f9f9] hover:border-[#7eaaa1]"}`}><span className={`mb-2 grid size-9 place-items-center rounded-lg ${files.length ? "bg-emerald-100 text-emerald-700" : "bg-[#17343d] text-[#8ce0c7]"}`}>{files.length ? <FileCheck2 className="size-4" /> : <UploadCloud className="size-4" />}</span><span className="max-w-md truncate text-sm font-semibold text-slate-700">{files.length ? `${files.length} PDF · ${t.selected}` : t.drop}</span><span className="mt-1 text-[10px] text-slate-400">{files.length ? `${formatBytes(files.reduce((sum, file) => sum + file.size, 0))} · ${files.map((file) => file.name).join(", ")}` : t.dropSub}</span></button>
      {error && <div className="mt-3 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-800"><CircleAlert className="size-4 shrink-0" />{error}</div>}{queued && <div className="mt-3 rounded-lg border border-[#d5ebe6] bg-[#f0f8f5] p-3"><div className="flex justify-between text-[10px] font-medium text-[#315f57]"><span>{job?.state === "local_analysis_completed" ? `${job.analysis?.atomic_fact_candidates || 0} ${t.facts} · ${job.analysis?.projection_validated_candidates || 0} ${t.validated}` : t.queued}</span><span className="font-mono">{job ? Math.round((job.stage_index / 5) * 100) : 8}%</span></div><Progress value={job ? (job.stage_index / 5) * 100 : 8} className="mt-2 h-1.5" /></div>}
      <div className="mt-4 flex items-center justify-between"><p className="flex items-center gap-1.5 text-[9px] text-slate-400"><LockKeyhole className="size-3 text-emerald-600" />SHA-256 · {t.provenancePreserved}</p><Button disabled={!files.length || queued} onClick={startAnalysis} className="h-9 bg-[#16836e] text-xs hover:bg-[#116e5d]">{queued ? <><Check />{t.queued}</> : <>{t.start}<ArrowRight /></>}</Button></div>
    </div></DialogContent></Dialog>

    <Dialog open={searchOpen} onOpenChange={setSearchOpen}><DialogContent className="max-h-[82vh] overflow-hidden border-[#dce5e4] bg-white p-0 sm:max-w-3xl"><DialogHeader className="border-b border-slate-100 px-6 py-4"><DialogTitle className="flex items-center gap-2 text-[#18343d]"><Database className="size-4 text-[#16836e]" />{t.searchTitle}</DialogTitle><DialogDescription className="text-xs">{t.searchDesc}</DialogDescription></DialogHeader><div className="flex gap-2 px-6"><Input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void searchFacts(); }} placeholder={t.queryPlaceholder} className="h-9 text-xs" /><Button onClick={() => void searchFacts()} disabled={searching} className="h-9 bg-[#16836e] text-xs hover:bg-[#116e5d]">{searching ? t.searching : t.runSearch}</Button></div><div className="max-h-[55vh] overflow-y-auto border-t border-slate-100 px-6 py-2">{factResults.length ? factResults.map((result) => { const fact = result.fact; const company = fact.subject?.document_metadata?.[0]?.company || t.unknown; const value = typeof fact.value === "string" ? fact.value : JSON.stringify(fact.value); const evidence = fact.evidence?.[0]; return <article key={fact.record_id} className="border-b border-slate-100 py-3 last:border-0"><div className="flex flex-wrap items-center gap-2"><Badge className="bg-emerald-100 text-[9px] text-emerald-800">{t.tier}</Badge><span className="text-[10px] font-medium text-slate-500">{company}</span><span className="ml-auto font-mono text-[8px] text-slate-400">{fact.subject?.task_id}</span></div><div className="mt-2 flex items-baseline gap-3"><p className="font-mono text-[10px] text-[#16836e]">{fact.predicate?.canonical_key}</p><p className="text-xs font-semibold text-slate-800">{value}</p></div>{evidence && <p className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-slate-500"><span className="mr-2 font-mono text-[#16836e]">PDF p.{evidence.pdf_page}</span>{evidence.quote}</p>}</article>; }) : <div className="py-14 text-center text-xs text-slate-400">{searching ? `${t.searching}…` : t.noMatch}</div>}</div><div className="flex justify-between border-t border-slate-100 bg-[#f7f9f9] px-6 py-2.5 text-[9px] text-slate-400"><span>{inventory.trusted_tier_b} {t.records}</span><span className="font-mono">{t.readOnly} · {t.provenancePreserved}</span></div></DialogContent></Dialog>
  </div>;
}
