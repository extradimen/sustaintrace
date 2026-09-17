"use client";

import { useState } from "react";

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileSearch,
  RotateCcw,
  ShieldAlert,
  Wrench,
} from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { Locale } from "@/lib/i18n";

type Qualifiers = {
  reference_period?: number | null;
  normalized_unit?: string | null;
  scope_boundary?: string | null;
};

const tx = (locale: Locale, en: string, zh: string) => locale === "zh" ? zh : en;

type RepairExecution = {
  state: string;
  validator_id: string;
  checks?: Record<string, boolean>;
  candidate_cell_handles?: string[];
  rollback_performed?: boolean;
  rollback_action?: string;
  selected_cell?: {
    row_header?: string;
    column_header?: string;
    raw_value?: string;
    cell_handle?: string;
  } | null;
  derived_fact?: {
    value?: unknown;
    trust_tier?: string;
    qualifiers?: Qualifiers;
  } | null;
  promotion_review?: {
    review_id: string;
    state: string;
    version: number;
    decision_history?: Array<{
      decision: string;
      reviewer: string;
      rationale: string;
      at: string;
    }>;
    promotion_performed: boolean;
    trusted_layer_modified: boolean;
  } | null;
  promotion_staging?: {
    staging_id: string;
    state: string;
    checks: Record<string, boolean>;
    blocking_reasons: string[];
    source_ids: string[];
    promotion_performed: boolean;
    trusted_layer_modified: boolean;
  } | null;
  promotion_overlay?: {
    overlay_id: string;
    trust_tier: string;
    knowledge_status: string;
    promotion?: { committed?: boolean; commit_event_id?: string };
  } | null;
};

type FactDetail = {
  fact: {
    record_id: string;
    knowledge_status: string;
    trust_tier: string;
    predicate: { canonical_key: string };
    value: unknown;
    qualifiers?: Qualifiers;
    evidence: Array<{
      pdf_page: number;
      quote: string;
      coordinates?: number[] | null;
      block_type?: string;
      verbatim_value?: string;
    }>;
  };
  projection_audit?: {
    status: string;
    blocking_reasons: string[];
    bindings?: Record<string, unknown>;
  };
  promotion_gate?: {
    decision: string;
    dimensions: Record<string, string>;
    blocking_reasons: string[];
    promotion_performed: boolean;
  };
  repair_plan?: {
    plan_state: string;
    decision: string;
    routes: Array<{
      blocking_reason: string;
      strategy_id: string;
      strategy_name: string;
      risk_level: string;
      execution_policy: string;
      actions: string[];
      validation_gates: string[];
    }>;
    unresolved_blocking_reasons: string[];
    postvalidation_requirements: string[];
    execution_performed: boolean;
    promotion_performed: boolean;
  };
  repair_dispatch?: {
    decision: string;
    checks: Record<string, boolean>;
    blocking_reasons: string[];
    execution_started: boolean;
    execution_state: string;
  };
  repair_executions?: RepairExecution[];
  failures?: Array<{ failure_signature?: string }>;
};

export type JobFactPayload = {
  job_id: string;
  source: { original_filename: string; sha256: string };
  matched: number;
  returned: number;
  records: FactDetail[];
};

function displayValue(value: unknown) {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : JSON.stringify(value);
}

function displayPeriod(period: number | null | undefined, locale: Locale) {
  return period ?? tx(locale, "Period unbound", "期间未绑定");
}

function RepairExecutionCard({
  execution,
  originalValue,
  originalQualifiers,
  apiBase,
  jobId,
  onReviewUpdated,
  locale,
}: {
  execution: RepairExecution;
  originalValue: unknown;
  originalQualifiers?: Qualifiers;
  apiBase: string;
  jobId: string;
  onReviewUpdated: () => Promise<void>;
  locale: Locale;
}) {
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [overlayRationale, setOverlayRationale] = useState("");
  const [overlaySubmitting, setOverlaySubmitting] = useState(false);
  const rolledBack = execution.state === "rolled_back" || execution.rollback_performed;
  const failedChecks = Object.entries(execution.checks || {})
    .filter(([, passed]) => !passed)
    .map(([name]) => name);

  if (rolledBack) {
    return (
      <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <RotateCcw className="size-4 text-amber-700" />
          <span className="text-sm font-semibold text-amber-950">{tx(locale, "Repair rolled back; the original fact is unchanged", "修复已撤销，原事实保持不变")}</span>
          <Badge variant="outline" className="border-amber-300 bg-white text-amber-800">
            {tx(locale, "Not written to the knowledge base", "未写入知识库")}
          </Badge>
        </div>
        <p className="mt-2 text-sm leading-6 text-amber-900">
          {execution.rollback_action || tx(locale, "Candidate evidence failed uniqueness or completeness checks.", "候选证据未通过唯一性或完整性检查。")}
        </p>
        {failedChecks.length ? (
          <div className="mt-3">
            <p className="text-xs font-semibold text-amber-950">{tx(locale, "Failed checks", "未通过检查")}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {failedChecks.map((check) => (
                <Badge key={check} variant="outline" className="border-amber-300 bg-white text-amber-800">
                  {check}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        {execution.candidate_cell_handles?.length ? (
          <p className="mt-3 break-all font-mono text-xs text-amber-800">
            {tx(locale, "Candidate cells", "候选单元格")}: {execution.candidate_cell_handles.join(", ")}
          </p>
        ) : null}
      </div>
    );
  }

  const repaired = execution.derived_fact;
  const review = execution.promotion_review;
  const staging = execution.promotion_staging;
  const overlay = execution.promotion_overlay;
  const submitDecision = async (decision: string) => {
    if (!review || !rationale.trim()) {
      setSubmissionError(tx(locale, "Enter a review rationale before submitting a decision.", "请填写审核依据后再提交决定。"));
      return;
    }
    setSubmitting(true);
    setSubmissionError(null);
    try {
      const response = await fetch(
        `${apiBase}/jobs/${jobId}/promotion-reviews/${review.review_id}/decision`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            decision,
            reviewer: "local_workbench_user",
            rationale: rationale.trim(),
            expected_version: review.version,
          }),
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || tx(locale, "Unable to save the review decision", "审核决定保存失败"));
      }
      setRationale("");
      await onReviewUpdated();
    } catch (reason) {
      setSubmissionError(reason instanceof Error ? reason.message : tx(locale, "Unable to save the review decision", "审核决定保存失败"));
    } finally {
      setSubmitting(false);
    }
  };
  const submitOverlayAction = async (action: "commit" | "withdraw") => {
    if (!staging || !overlayRationale.trim()) {
      setSubmissionError(tx(locale, "Enter a rationale for committing or withdrawing the overlay.", "请填写正式提交或撤回依据。"));
      return;
    }
    setOverlaySubmitting(true);
    setSubmissionError(null);
    const url = action === "commit"
      ? `${apiBase}/jobs/${jobId}/promotion-staging/${staging.staging_id}/commit`
      : `${apiBase}/promotion-overlays/${overlay?.overlay_id}/withdraw`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor: "local_workbench_user",
          rationale: overlayRationale.trim(),
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || tx(locale, "Overlay operation failed", "覆盖层操作失败"));
      }
      setOverlayRationale("");
      await onReviewUpdated();
    } catch (reason) {
      setSubmissionError(reason instanceof Error ? reason.message : tx(locale, "Overlay operation failed", "覆盖层操作失败"));
    } finally {
      setOverlaySubmitting(false);
    }
  };
  return (
    <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <CheckCircle2 className="size-4 text-emerald-700" />
        <span className="text-sm font-semibold text-emerald-950">{tx(locale, "Deterministic binding passed post-validation", "确定性绑定已通过后验证")}</span>
        <Badge variant="outline" className="border-emerald-300 bg-white text-emerald-800">
          Tier {repaired?.trust_tier || "C"} {tx(locale, "candidate", "候选")}
        </Badge>
      </div>
      <div className="mt-3 grid items-stretch gap-2 sm:grid-cols-[1fr_auto_1fr]">
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <p className="text-xs font-semibold text-slate-500">{tx(locale, "Original fact", "原始事实")}</p>
          <p className="mt-2 font-mono text-sm text-slate-900">{displayValue(originalValue)}</p>
          <p className="mt-1 text-xs text-slate-500">
            {displayPeriod(originalQualifiers?.reference_period, locale)} · {originalQualifiers?.normalized_unit || tx(locale, "Unit unbound", "单位未绑定")}
          </p>
        </div>
        <div className="flex items-center justify-center text-emerald-700">
          <ArrowRight className="size-4 rotate-90 sm:rotate-0" />
        </div>
        <div className="rounded-md border border-emerald-200 bg-white p-3">
          <p className="text-xs font-semibold text-emerald-700">{tx(locale, "Repaired candidate", "修复后候选")}</p>
          <p className="mt-2 font-mono text-sm text-slate-900">
            {displayValue(repaired?.value ?? execution.selected_cell?.raw_value ?? originalValue)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {displayPeriod(repaired?.qualifiers?.reference_period, locale)} · {repaired?.qualifiers?.normalized_unit || tx(locale, "Unit unbound", "单位未绑定")}
          </p>
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-emerald-900">
        {execution.selected_cell?.row_header || tx(locale, "Metric row", "指标行")} · {execution.selected_cell?.column_header || tx(locale, "Year column", "年份列")}; {tx(locale, "the derived fact has not entered the trusted knowledge base.", "派生事实仍未进入可信知识库。")}
      </p>
      {review ? (
        <div className="mt-3 border-t border-emerald-200 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-900">{tx(locale, "Trusted promotion review", "可信晋级审核")}</p>
            <Badge
              variant="outline"
              className={review.state === "pending_review"
                ? "border-cyan-200 bg-cyan-50 text-cyan-800"
                : review.state === "approved_for_promotion_staging"
                  ? "border-emerald-300 bg-white text-emerald-800"
                  : "border-amber-300 bg-white text-amber-800"}
            >
              {review.state === "pending_review"
                ? tx(locale, "Pending review", "待审核")
                : review.state === "approved_for_promotion_staging"
                  ? tx(locale, "Approved for promotion staging", "已批准进入晋级暂存")
                  : review.state === "evidence_required"
                    ? tx(locale, "More evidence required", "需要补充证据")
                    : tx(locale, "Rejected", "已拒绝")}
            </Badge>
          </div>
          {review.state === "pending_review" ? (
            <div className="mt-3 space-y-2">
              <Textarea
                value={rationale}
                onChange={(event) => setRationale(event.target.value)}
                placeholder={tx(locale, "Explain the approval, rejection or request for more evidence", "填写批准、拒绝或补充证据的审核依据")}
                className="min-h-20 bg-white text-sm"
              />
              {submissionError ? <p className="text-xs text-rose-700">{submissionError}</p> : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={submitting}
                  onClick={() => void submitDecision("approve_for_promotion_staging")}
                  className="bg-[#0b6e75] hover:bg-[#095d63]"
                >
                  {tx(locale, "Approve for staging", "批准进入暂存")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={submitting}
                  onClick={() => void submitDecision("request_more_evidence")}
                >
                  {tx(locale, "Request more evidence", "要求补充证据")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={submitting}
                  className="border-rose-200 text-rose-700 hover:bg-rose-50"
                  onClick={() => void submitDecision("reject")}
                >
                  {tx(locale, "Reject candidate", "拒绝候选")}
                </Button>
              </div>
              <p className="text-xs text-slate-500">{tx(locale, "Approval only enters promotion staging; it does not write directly to the trusted knowledge base.", "批准仅进入晋级暂存，不会直接写入可信知识库。")}</p>
            </div>
          ) : review.decision_history?.length ? (
            <div className="mt-3 rounded-md border border-slate-200 bg-white p-3 text-xs text-slate-600">
              <p>{review.decision_history.at(-1)?.rationale}</p>
              <p className="mt-2 text-slate-400">
                {review.decision_history.at(-1)?.reviewer} · {review.decision_history.at(-1)?.at}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
      {staging ? (
        <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              {staging.state === "ready_for_tier_b_overlay_commit"
                ? <CheckCircle2 className="size-4 text-emerald-700" />
                : <ShieldAlert className="size-4 text-amber-700" />}
              {tx(locale, "Tier B promotion staging checks", "Tier B 晋级暂存检查")}
            </p>
            <Badge
              variant="outline"
              className={staging.state === "ready_for_tier_b_overlay_commit"
                ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                : staging.state === "already_trusted_equivalent"
                  ? "border-slate-300 bg-slate-50 text-slate-700"
                  : "border-amber-300 bg-amber-50 text-amber-800"}
            >
              {staging.state === "ready_for_tier_b_overlay_commit"
                ? tx(locale, "Checks passed; awaiting commit", "检查通过，等待提交")
                : staging.state === "already_trusted_equivalent"
                  ? tx(locale, "Equivalent trusted fact already exists", "可信库已有等价事实")
                  : tx(locale, "Promotion staging blocked", "晋级暂存已阻断")}
            </Badge>
          </div>
          {staging.blocking_reasons.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {staging.blocking_reasons.map((reason) => (
                <Badge key={reason} variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
                  {reason}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-emerald-800">
              {tx(locale, "Independent source, source hash, evidence slot, period, unit, scope and conflict checks all passed.", "独立来源、来源哈希、证据槽位、期间、单位、范围和冲突检查均已通过。")}
            </p>
          )}
          <p className="mt-3 text-xs text-slate-500">
            {tx(locale, `${staging.source_ids.length} source(s) registered; the base trusted store is never modified directly.`, `已登记来源 ${staging.source_ids.length} 个；基础可信库始终不会被直接修改。`)}
          </p>
          {staging.state === "ready_for_tier_b_overlay_commit" ? (
            <div className="mt-3 border-t border-slate-200 pt-3">
              <Textarea
                value={overlayRationale}
                onChange={(event) => setOverlayRationale(event.target.value)}
                placeholder={overlay ? tx(locale, "Explain why the Tier B overlay is being withdrawn", "填写撤回 Tier B 覆盖事实的依据") : tx(locale, "Explain why the Tier B overlay is being committed", "填写正式提交 Tier B 覆盖事实的依据")}
                className="min-h-16 bg-white text-sm"
              />
              {submissionError ? <p className="mt-2 text-xs text-rose-700">{submissionError}</p> : null}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {overlay ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={overlaySubmitting}
                    className="border-rose-200 text-rose-700 hover:bg-rose-50"
                    onClick={() => void submitOverlayAction("withdraw")}
                  >
                    {tx(locale, "Withdraw Tier B overlay", "撤回 Tier B 覆盖")}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    disabled={overlaySubmitting}
                    onClick={() => void submitOverlayAction("commit")}
                    className="bg-[#0b6e75] hover:bg-[#095d63]"
                  >
                    {tx(locale, "Commit Tier B overlay", "正式提交 Tier B 覆盖")}
                  </Button>
                )}
                <Badge variant="outline" className={overlay
                  ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                  : "border-slate-300 bg-slate-50 text-slate-700"}
                >
                  {overlay ? tx(locale, "Overlay active and withdrawable", "覆盖层已生效，可撤回") : tx(locale, "Awaiting formal commit", "等待正式提交")}
                </Badge>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function FactEvidenceSheet({
  open,
  onOpenChange,
  payload,
  loading,
  error,
  apiBase,
  onRefresh,
  locale,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload: JobFactPayload | null;
  loading: boolean;
  error: string | null;
  apiBase: string;
  onRefresh: () => Promise<void>;
  locale: Locale;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 bg-[#f6f8fa] p-0 sm:max-w-2xl">
        <SheetHeader className="border-b border-slate-200 bg-white px-6 py-5">
          <div className="flex items-center gap-2 text-xs font-semibold text-cyan-700">
            <FileSearch className="size-4" />{tx(locale, "Evidence and promotion audit", "证据与晋级审计")}
          </div>
          <SheetTitle className="pr-8 text-xl text-[#102330]">
            {payload?.source.original_filename || tx(locale, "Report fact details", "报告事实详情")}
          </SheetTitle>
          <SheetDescription>
            {payload
              ? tx(locale, `${payload.matched} atomic facts · source ${payload.source.sha256.slice(0, 12)}…`, `${payload.matched} 条原子事实 · 来源 ${payload.source.sha256.slice(0, 12)}…`)
              : tx(locale, "Reading the job's local analysis archive", "读取任务的本地分析档案")}
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-[calc(100vh-132px)]">
          {loading ? (
            <div className="space-y-4 p-6">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : error ? (
            <div className="m-6 rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="size-4" />{tx(locale, "Unable to read evidence details", "无法读取证据详情")}
              </div>
              <p className="mt-2 leading-6">{error}</p>
            </div>
          ) : payload?.records.length ? (
            <Accordion type="multiple" className="p-5">
              {payload.records.map((item, index) => {
                const evidence = item.fact.evidence[0];
                const projectionPassed = item.projection_audit?.status === "passed";
                const promotionEligible = item.promotion_gate?.decision === "eligible";
                return (
                  <AccordionItem
                    key={item.fact.record_id}
                    value={item.fact.record_id}
                    className="mb-3 rounded-xl border border-slate-200 bg-white px-4 shadow-sm"
                  >
                    <AccordionTrigger className="hover:no-underline">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-slate-400">#{index + 1}</span>
                          <Badge
                            variant="outline"
                            className={projectionPassed
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-amber-200 bg-amber-50 text-amber-700"}
                          >
                            {projectionPassed ? tx(locale, "Projection passed", "投影通过") : tx(locale, "Quarantined", "已隔离")}
                          </Badge>
                          <Badge variant="outline" className="border-slate-200 text-slate-600">
                            Tier {item.fact.trust_tier}
                          </Badge>
                        </div>
                        <p className="mt-2 truncate text-base font-semibold text-slate-800">
                          {item.fact.predicate.canonical_key} = {displayValue(item.fact.value)}
                          {item.fact.qualifiers?.normalized_unit
                            ? ` ${item.fact.qualifiers.normalized_unit}`
                            : ""}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {tx(locale, "Page", "第")} {evidence?.pdf_page ?? "—"}{locale === "zh" ? " 页" : ""} · {displayPeriod(item.fact.qualifiers?.reference_period, locale)}
                        </p>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 border-t border-slate-100 pt-4">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div className="rounded-lg bg-slate-50 p-3">
                          <p className="text-xs text-slate-400">{tx(locale, "Verbatim value", "原始值")}</p>
                          <p className="mt-1 font-mono text-sm text-slate-800">
                            {evidence?.verbatim_value || displayValue(item.fact.value)}
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-3">
                          <p className="text-xs text-slate-400">{tx(locale, "Spatial coordinates", "空间坐标")}</p>
                          <p className="mt-1 font-mono text-sm text-slate-800">
                            {evidence?.coordinates ? `[${evidence.coordinates.join(", ")}]` : tx(locale, "Not located", "未定位")}
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-3">
                          <p className="text-xs text-slate-400">{tx(locale, "Evidence block", "证据块")}</p>
                          <p className="mt-1 font-mono text-sm text-slate-800">
                            {evidence?.block_type || "—"}
                          </p>
                        </div>
                      </div>

                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{tx(locale, "Frozen source text", "冻结原文")}</p>
                        <blockquote className="mt-2 rounded-lg border-l-2 border-cyan-500 bg-cyan-50/60 p-3 text-sm leading-6 text-slate-700">
                          {evidence?.quote || tx(locale, "No source text available", "没有可显示的原文")}
                        </blockquote>
                      </div>

                      <div>
                        <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                          {projectionPassed
                            ? <CheckCircle2 className="size-4 text-emerald-600" />
                            : <AlertTriangle className="size-4 text-amber-600" />}
                          {tx(locale, "Slot projection", "槽位投影")}
                        </p>
                        {item.projection_audit?.blocking_reasons?.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {item.projection_audit.blocking_reasons.map((reason) => (
                              <Badge key={reason} variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
                                {reason}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <p className="mt-2 text-sm text-emerald-700">
                            {tx(locale, "Value, subject, period, unit and coordinates are deterministically bound.", "原值、主题、期间、单位和坐标均完成确定性绑定。")}
                          </p>
                        )}
                      </div>

                      <div className="rounded-lg border border-slate-200 p-3">
                        <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                          <ShieldAlert className="size-4 text-slate-500" />{tx(locale, "Trusted promotion gate", "可信晋级门")}
                        </p>
                        <p className="mt-2 text-sm text-slate-600">
                          {promotionEligible
                            ? tx(locale, "Promotion conditions are met, but this view never modifies the trusted knowledge base directly.", "已满足晋级条件，但本视图不会直接修改可信知识库。")
                            : tx(locale, "Not yet promoted; the following audit dimensions are incomplete.", "尚未晋级；需要补齐下列审计维度。")}
                        </p>
                        {item.promotion_gate?.blocking_reasons?.length ? (
                          <ul className="mt-2 space-y-1 text-xs text-slate-500">
                            {item.promotion_gate.blocking_reasons.map((reason) => (
                              <li key={reason}>• {reason}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>

                      {item.repair_plan ? (
                        <div className="rounded-lg border border-cyan-200 bg-cyan-50/50 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                              <Wrench className="size-4 text-cyan-700" />{tx(locale, "Controlled repair plan", "受控修复计划")}
                            </p>
                            <Badge variant="outline" className="border-cyan-200 bg-white text-cyan-800">
                              {tx(locale, "Read-only plan", "只读计划")}
                            </Badge>
                          </div>
                          <p className="mt-2 text-sm text-slate-600">
                            {tx(locale, "The system selected allowed repair strategies from the blocking reasons; promotion review remains conditional on post-validation.", "系统已根据阻断原因选择允许的修复策略；须通过后验证才可能进入晋级审查。")}
                          </p>
                          {item.repair_plan.routes.length ? (
                            <div className="mt-3 space-y-3">
                              {item.repair_plan.routes.map((route) => (
                                <div
                                  key={`${route.blocking_reason}-${route.strategy_id}`}
                                  className="rounded-md border border-cyan-100 bg-white p-3"
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
                                      {route.blocking_reason}
                                    </Badge>
                                    <span className="text-sm font-medium text-slate-800">{route.strategy_name}</span>
                                    <span className="font-mono text-xs text-slate-400">{route.strategy_id}</span>
                                  </div>
                                  <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
                                    {route.actions.map((action) => <li key={action}>• {action}</li>)}
                                  </ul>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-3 text-sm text-amber-800">{tx(locale, "No safely matching strategy; execution is blocked under the fail-closed policy.", "没有安全匹配的策略，已按失败关闭原则阻断。")}</p>
                          )}

                          {item.repair_plan.unresolved_blocking_reasons.length ? (
                            <div className="mt-3">
                              <p className="text-xs font-semibold text-amber-900">{tx(locale, "Manual strategy definition required", "仍需人工定义策略")}</p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {item.repair_plan.unresolved_blocking_reasons.map((reason) => (
                                  <Badge key={reason} variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
                                    {reason}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          ) : null}

                          {item.repair_dispatch ? (
                            <div className="mt-3 border-t border-cyan-200 pt-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-semibold text-slate-700">{tx(locale, "Execution preflight", "执行预检")}</span>
                                <Badge
                                  variant="outline"
                                  className={item.repair_dispatch.decision === "blocked"
                                    ? "border-amber-200 bg-amber-50 text-amber-800"
                                    : "border-emerald-200 bg-emerald-50 text-emerald-700"}
                                >
                                  {item.repair_dispatch.decision === "ready_for_supervised_execution"
                                    ? tx(locale, "Ready for supervised execution", "可进入受控执行")
                                    : item.repair_dispatch.decision === "ready_for_automatic_execution"
                                      ? tx(locale, "Ready for automatic execution", "可自动执行")
                                      : tx(locale, "Blocked", "已阻断")}
                                </Badge>
                              </div>
                              {item.repair_dispatch.blocking_reasons.length ? (
                                <ul className="mt-2 space-y-1 text-xs text-amber-800">
                                  {item.repair_dispatch.blocking_reasons.map((reason) => (
                                    <li key={reason}>• {reason}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="mt-2 text-xs text-slate-600">
                                  {tx(locale, "Source hash, parent fact, strategy and unexecuted state all passed preflight.", "来源哈希、父事实、策略和未执行状态均通过预检。")}
                                </p>
                              )}
                            </div>
                          ) : null}

                          {item.repair_executions?.map((execution, executionIndex) => (
                            <RepairExecutionCard
                              key={execution.selected_cell?.cell_handle || `${execution.validator_id}-${executionIndex}`}
                              execution={execution}
                              originalValue={item.fact.value}
                              originalQualifiers={item.fact.qualifiers}
                              apiBase={apiBase}
                              jobId={payload.job_id}
                              onReviewUpdated={onRefresh}
                              locale={locale}
                            />
                          ))}
                        </div>
                      ) : null}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          ) : (
            <div className="m-6 rounded-xl border border-slate-200 bg-white p-8 text-center">
              <p className="font-semibold text-slate-800">{tx(locale, "No atomic facts yet", "暂无原子事实")}</p>
              <p className="mt-2 text-sm text-slate-500">
                {tx(locale, "This job may still be running, or no projectable ESG values were found.", "该任务可能尚未完成本地分析，或没有发现可投影的 ESG 数值。")}
              </p>
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
