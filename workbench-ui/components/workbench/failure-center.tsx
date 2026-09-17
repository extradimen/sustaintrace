"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Locale } from "@/lib/i18n";

type FailureRecord = {
  record_id: string;
  experiment_id?: string;
  task_id?: string;
  failure_signature?: string;
  failure_category?: string;
  failure_owner?: string;
  diagnostics?: Array<{ status?: string }>;
  observed_stage_states?: Record<string, unknown>;
};

type FailurePayload = {
  matched: number;
  returned: number;
  signature_counts: Record<string, number>;
  records: FailureRecord[];
};

function stageSummary(states?: Record<string, unknown>) {
  if (!states) return "—";
  return Object.entries(states)
    .filter(([key]) => key !== "semantic_note")
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" · ") || "—";
}

const copy = {
  en: { eyebrow: "Failure–repair knowledge base", title: "Failure patterns and repair entry points", subtitle: "Preserves the stage, owner and original diagnosis for every failure; no silent retries.", filter: "Filter by failure signature", all: "All failure signatures", refresh: "Refresh", unavailable: "Failure archive unavailable", unavailableDesc: "The local service is not responding. Existing failure records have not been modified.", reconnect: "Reconnect", signature: "Failure signature", task: "Task", owner: "Owner", stage: "Stage state", archive: "Archive state", archived: "Archived", matched: "matched", showing: "shown", readOnly: "read-only audit view" },
  zh: { eyebrow: "失败—修复知识库", title: "失败模式与修复入口", subtitle: "保留失败发生在哪个阶段、由谁负责以及原始诊断；不会静默重试。", filter: "按失败签名筛选", all: "全部失败签名", refresh: "刷新", unavailable: "无法读取失败档案", unavailableDesc: "本地服务未响应，已有失败记录没有被修改。", reconnect: "重新连接", signature: "失败签名", task: "任务", owner: "归属", stage: "阶段状态", archive: "档案状态", archived: "已归档", matched: "匹配", showing: "当前显示", readOnly: "只读审计视图" },
};

export function FailureCenter({ apiBase, locale }: { apiBase: string; locale: Locale }) {
  const t = copy[locale];
  const [payload, setPayload] = useState<FailurePayload | null>(null);
  const [signature, setSignature] = useState("");
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setUnavailable(false);
    try {
      const query = new URLSearchParams({ limit: "250" });
      if (signature) query.set("signature", signature);
      const response = await fetch(`${apiBase}/failures?${query}`);
      if (!response.ok) throw new Error("failure archive unavailable");
      setPayload(await response.json());
    } catch {
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, [apiBase, signature]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const signatures = useMemo(() => Object.entries(payload?.signature_counts || {}).sort((a, b) => b[1] - a[1]), [payload]);

  return (
    <section className="space-y-3">
      <div className="rounded-2xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div className="min-w-[360px]"><div className="mb-1 flex items-center gap-2 text-[10px] font-semibold text-amber-700"><Wrench className="size-3.5" />{t.eyebrow}</div><h2 className="text-lg font-semibold text-[#102330]">{t.title}</h2><p className="mt-0.5 text-xs text-slate-500">{t.subtitle}</p></div>
          <div className="flex min-w-[360px] flex-1 justify-end gap-2"><NativeSelect className="max-w-[480px]" value={signature} onChange={(event) => setSignature(event.target.value)} aria-label={t.filter}><NativeSelectOption value="">{t.all}</NativeSelectOption>{signatures.map(([name, count]) => <NativeSelectOption value={name} key={name}>{name} ({count})</NativeSelectOption>)}</NativeSelect><Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "animate-spin" : ""} />{t.refresh}</Button></div>
        </div>
        {loading ? <div className="space-y-3 p-6"><Skeleton className="h-20 w-full" /><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : unavailable ? <Empty className="m-6 border border-amber-200 bg-amber-50"><EmptyHeader><EmptyMedia variant="icon"><AlertTriangle /></EmptyMedia><EmptyTitle>{t.unavailable}</EmptyTitle><EmptyDescription>{t.unavailableDesc}</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => void load()}>{t.reconnect}</Button></Empty> : <>
          <div className="grid gap-3 border-b border-slate-100 p-3.5 sm:grid-cols-2 xl:grid-cols-4">{signatures.slice(0, 4).map(([name, count]) => <button key={name} onClick={() => setSignature(name)} className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-left transition hover:border-amber-300 hover:bg-amber-50"><p className="truncate font-mono text-[9px] leading-4 text-slate-500">{name}</p><p className="mt-1 font-mono text-xl font-semibold text-slate-800">{count}</p></button>)}</div>
          <div className="overflow-x-auto"><Table><TableHeader><TableRow className="bg-slate-50/70"><TableHead className="px-6">{t.signature}</TableHead><TableHead>{t.task}</TableHead><TableHead>{t.owner}</TableHead><TableHead>{t.stage}</TableHead><TableHead className="pr-6">{t.archive}</TableHead></TableRow></TableHeader><TableBody>{(payload?.records || []).map((record) => <TableRow key={record.record_id}><TableCell className="max-w-[250px] px-6"><p className="font-mono text-xs font-semibold text-amber-800">{record.failure_signature || "UNCLASSIFIED"}</p><p className="mt-1 text-[11px] text-slate-400">{record.failure_category || "—"}</p></TableCell><TableCell><p className="text-xs font-medium text-slate-700">{record.task_id || "—"}</p><p className="mt-1 font-mono text-[10px] text-slate-400">{record.experiment_id || "—"}</p></TableCell><TableCell><Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-600">{record.failure_owner || "unknown"}</Badge></TableCell><TableCell className="max-w-[360px] text-xs leading-5 text-slate-500">{stageSummary(record.observed_stage_states)}</TableCell><TableCell className="pr-6"><Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">{record.diagnostics?.[0]?.status || t.archived}</Badge></TableCell></TableRow>)}</TableBody></Table></div>
          <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4 text-xs text-slate-500"><span>{t.matched} {payload?.matched || 0}</span><span>{t.showing} {payload?.returned || 0} · {t.readOnly}</span></div>
        </>}
      </div>
    </section>
  );
}
