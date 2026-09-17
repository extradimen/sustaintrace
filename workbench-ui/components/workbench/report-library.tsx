"use client";

import { useCallback, useEffect, useState } from "react";
import { Archive, Eye, FileText, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FactEvidenceSheet, type JobFactPayload } from "@/components/workbench/fact-evidence-sheet";
import type { Locale } from "@/lib/i18n";

type Job = {
  job_id: string;
  state: string;
  created_at: string;
  source: { original_filename: string; bytes: number; sha256: string };
  analysis?: {
    candidate_records: number;
    atomic_fact_candidates?: number;
    projection_validated_candidates?: number;
    projection_quarantined?: number;
    failure_records: number;
    repair_plan_records?: number;
    repair_plans_supervised?: number;
    repair_dispatch_ready?: number;
    repaired_fact_candidates?: number;
    repair_executions_postvalidated?: number;
    trusted_promotions: number;
  };
};

const copy = {
  en: {
    title: "Local report library", subtitle: "Every uploaded report keeps its own source hash, parser artefacts and analysis archive.", refresh: "Refresh", upload: "Upload report", unavailableTitle: "Report jobs unavailable", unavailableDesc: "The local analysis service is not responding. Saved data has not been changed.", reconnect: "Reconnect", emptyTitle: "No workbench reports yet", emptyDesc: "The 120 historical research reports remain locked; newly uploaded reports appear here as independent jobs.", first: "Upload first report", report: "Report", status: "Status", facts: "Atomic facts", validated: "Projection passed", quarantined: "Quarantined", plans: "Repair plans", failures: "Failures", hash: "Source hash", evidence: "Evidence", view: "View", detailUnavailable: "The local analysis archive is not available yet", readFailed: "Unable to read details", refreshFailed: "Unable to refresh local review state",
    states: { source_frozen: "Source frozen", parsing: "Parsing structure", parsed: "Parsing complete", local_analysis_completed: "Local analysis complete", blocked_parser_unavailable: "Parser unavailable", parse_failed: "Parsing failed", analysis_failed: "Analysis failed" } as Record<string, string>,
  },
  zh: {
    title: "本地报告库", subtitle: "每份上传报告都有独立来源哈希、解析产物和分析档案。", refresh: "刷新", upload: "上传新报告", unavailableTitle: "无法读取报告任务", unavailableDesc: "本地分析服务没有响应。已保存的数据不会受到影响。", reconnect: "重新连接", emptyTitle: "还没有工作台报告", emptyDesc: "历史 120 份研究报告保持锁定；新上传的报告会作为独立任务显示在这里。", first: "上传第一份报告", report: "报告", status: "状态", facts: "原子事实", validated: "投影通过", quarantined: "隔离", plans: "修复计划", failures: "失败", hash: "来源哈希", evidence: "证据", view: "查看", detailUnavailable: "本地分析档案尚不可用", readFailed: "读取失败", refreshFailed: "无法刷新本地审核状态",
    states: { source_frozen: "来源已冻结", parsing: "结构解析中", parsed: "解析完成", local_analysis_completed: "本地分析完成", blocked_parser_unavailable: "解析器不可用", parse_failed: "解析失败", analysis_failed: "分析失败" } as Record<string, string>,
  },
};

export function ReportLibrary({ apiBase, locale, onNewAnalysis }: { apiBase: string; locale: Locale; onNewAnalysis: () => void }) {
  const t = copy[locale];
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailPayload, setDetailPayload] = useState<JobFactPayload | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setUnavailable(false);
    try {
      const response = await fetch(`${apiBase}/jobs?limit=100`);
      if (!response.ok) throw new Error("job list unavailable");
      const payload = await response.json();
      setJobs(payload.records || []);
    } catch {
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const openDetails = async (job: Job) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailError(null);
    setDetailPayload(null);
    try {
      const response = await fetch(`${apiBase}/jobs/${job.job_id}/facts?limit=100`);
      if (!response.ok) throw new Error(t.detailUnavailable);
      setDetailPayload(await response.json());
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : t.readFailed);
    } finally {
      setDetailLoading(false);
    }
  };

  const refreshDetails = async () => {
    if (!detailPayload) return;
    const response = await fetch(`${apiBase}/jobs/${detailPayload.job_id}/facts?limit=100`);
    if (!response.ok) throw new Error(t.refreshFailed);
    setDetailPayload(await response.json());
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-6 py-5">
        <div><h2 className="text-xl font-semibold text-[#102330]">{t.title}</h2><p className="mt-1 text-sm text-slate-500">{t.subtitle}</p></div>
        <div className="flex gap-2"><Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "animate-spin" : ""} />{t.refresh}</Button><Button onClick={onNewAnalysis} className="bg-[#0b6e75] hover:bg-[#095d63]">{t.upload}</Button></div>
      </div>
      {loading ? <div className="space-y-3 p-6"><Skeleton className="h-11 w-full" /><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : unavailable ? <Empty className="m-6 border border-amber-200 bg-amber-50"><EmptyHeader><EmptyMedia variant="icon"><Archive /></EmptyMedia><EmptyTitle>{t.unavailableTitle}</EmptyTitle><EmptyDescription>{t.unavailableDesc}</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => void load()}>{t.reconnect}</Button></Empty> : jobs.length === 0 ? <Empty className="m-6 border border-slate-200"><EmptyHeader><EmptyMedia variant="icon"><FileText /></EmptyMedia><EmptyTitle>{t.emptyTitle}</EmptyTitle><EmptyDescription>{t.emptyDesc}</EmptyDescription></EmptyHeader><Button onClick={onNewAnalysis} className="bg-[#0b6e75] hover:bg-[#095d63]">{t.first}</Button></Empty> : <div className="overflow-x-auto"><Table><TableHeader><TableRow className="bg-slate-50/70"><TableHead className="px-6">{t.report}</TableHead><TableHead>{t.status}</TableHead><TableHead>{t.facts}</TableHead><TableHead>{t.validated}</TableHead><TableHead>{t.quarantined}</TableHead><TableHead>{t.plans}</TableHead><TableHead>{t.failures}</TableHead><TableHead>{t.hash}</TableHead><TableHead className="pr-6 text-right">{t.evidence}</TableHead></TableRow></TableHeader><TableBody>{jobs.map((job) => <TableRow key={job.job_id}><TableCell className="max-w-[320px] px-6"><p className="truncate font-medium text-slate-800">{job.source.original_filename}</p><p className="mt-1 font-mono text-[11px] text-slate-400">{job.job_id}</p></TableCell><TableCell><Badge variant="outline" className={job.state === "local_analysis_completed" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : job.state.includes("failed") || job.state.includes("blocked") ? "border-amber-200 bg-amber-50 text-amber-700" : "border-cyan-200 bg-cyan-50 text-cyan-700"}>{t.states[job.state] || job.state}</Badge></TableCell><TableCell className="font-mono">{job.analysis?.atomic_fact_candidates ?? "—"}</TableCell><TableCell className="font-mono text-emerald-700">{job.analysis?.projection_validated_candidates ?? "—"}</TableCell><TableCell className="font-mono text-amber-700">{job.analysis?.projection_quarantined ?? "—"}</TableCell><TableCell className="font-mono text-cyan-700">{job.analysis?.repair_plan_records ?? "—"}</TableCell><TableCell className="font-mono text-amber-700">{job.analysis?.failure_records ?? "—"}</TableCell><TableCell className="font-mono text-xs text-slate-500">{job.source.sha256.slice(0, 12)}…</TableCell><TableCell className="pr-6 text-right"><Button variant="outline" size="sm" disabled={!job.analysis?.atomic_fact_candidates} onClick={() => void openDetails(job)}><Eye />{t.view}</Button></TableCell></TableRow>)}</TableBody></Table></div>}
      <FactEvidenceSheet
        open={detailOpen}
        onOpenChange={setDetailOpen}
        payload={detailPayload}
        loading={detailLoading}
        error={detailError}
        apiBase={apiBase}
        locale={locale}
        onRefresh={refreshDetails}
      />
    </section>
  );
}
