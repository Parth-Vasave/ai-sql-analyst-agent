import { ChevronRight, Circle, CircleAlert, CircleCheck, CircleMinus } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

import { formatDuration, type PlanNode } from "../planTree";

interface Props {
  nodes: PlanNode[];
  /** Output of the root node (the answer), rendered under it. */
  rootOutput?: ReactNode;
  /** Expandable content per node key. */
  details?: Record<string, ReactNode>;
  running?: boolean;
  elapsedMs?: number;
  caption: string;
}

const MAX_DEPTH = 8; // deeper steps stay at this indent; --indent is narrower on small screens

function StatusIcon({ status }: { status: PlanNode["status"] }) {
  if (status === "failed") return <CircleAlert aria-label="failed" className="size-4 shrink-0 text-bad" strokeWidth={2} />;
  if (status === "skipped") return <CircleMinus aria-label="skipped" className="size-4 shrink-0 text-ink-3" strokeWidth={2} />;
  if (status === "success") return <CircleCheck aria-label="done" className="size-4 shrink-0 text-good" strokeWidth={2} />;
  // not run yet: a quiet marker keeps the icon column, so the tree lines never touch the text
  return <Circle aria-hidden className="size-4 shrink-0 text-rule-strong" strokeWidth={2} />;
}

function TimeBar({ share, animate, status }: { share: number; animate: boolean; status: PlanNode["status"] }) {
  const [shown, setShown] = useState(animate ? 0 : share);
  useEffect(() => {
    if (!animate) {
      setShown(share);
      return;
    }
    const frame = requestAnimationFrame(() => setShown(share));
    return () => cancelAnimationFrame(frame);
  }, [share, animate]);
  const color = status === "failed" ? "bg-bad" : share > 0.5 ? "bg-ramp-550" : share > 0.1 ? "bg-ramp-400" : "bg-ramp-250";
  return (
    <div aria-hidden className="h-1.5 w-full overflow-hidden rounded-full bg-well">
      <div
        className={`h-full rounded-full ${color} transition-[width] duration-[250ms] ease-out`}
        style={{ width: `${Math.max(shown * 100, shown > 0 ? 1.5 : 0)}%` }}
      />
    </div>
  );
}

/** The root's own time breakdown: one segment per step, in the order they ran. */
function SegmentBar({ steps }: { steps: PlanNode[] }) {
  const segments = [...steps].reverse().filter((s) => (s.durationMs ?? 0) > 0);
  return (
    <div aria-hidden className="flex h-1.5 w-full gap-[2px] overflow-hidden rounded-full bg-well">
      {segments.map((s) => (
        <div
          key={s.key}
          title={`${s.name}: ${formatDuration(s.durationMs)}`}
          className={`h-full min-w-[2px] ${s.status === "failed" ? "bg-bad" : s.share > 0.5 ? "bg-ramp-550" : s.share > 0.1 ? "bg-ramp-400" : "bg-ramp-250"}`}
          style={{ flexGrow: s.share, flexBasis: 0 }}
        />
      ))}
    </div>
  );
}

function NodeRow({
  node,
  depth,
  detail,
  pending,
  running,
  last,
  segments,
  children,
}: {
  node: PlanNode;
  depth: number;
  detail: ReactNode | undefined;
  pending: boolean;
  running: boolean;
  last: boolean;
  segments?: PlanNode[];
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const regionId = useId();
  const expandable = detail !== undefined && detail !== null;
  const level = Math.min(depth, MAX_DEPTH);

  // inline, so a wrapped name keeps its chevron right after the last word
  const title = (
    <>
      <span className={`font-semibold ${node.status === "failed" ? "text-bad" : ""}`}>{node.name}</span>
      {node.attempt !== null && <span className="ml-2 text-xs text-ink-3">attempt {node.attempt}</span>}
    </>
  );

  return (
    <li className="relative">
      {!last && (
        // the spine from this node's icon down to its child's elbow, through any output block
        <span
          aria-hidden
          className="absolute top-[1.85rem] bottom-0 border-l border-rule-strong"
          style={{ left: `calc(var(--indent) * ${level} + 0.45rem)` }}
        />
      )}
      <div className="relative" style={{ paddingLeft: `calc(var(--indent) * ${level})` }}>
        {depth > 0 && (
          // elbow connector from the parent's column into this row, as in EXPLAIN output
          <span
            aria-hidden
            className="absolute top-0 h-[1.35rem] rounded-bl-[3px] border-b border-l border-rule-strong"
            style={{ left: `calc(var(--indent) * ${level - 1} + 0.45rem)`, width: "calc(var(--indent) - 0.7rem)" }}
          />
        )}
        <div className="grid grid-cols-[1fr_auto] items-start gap-x-4 gap-y-1 py-2 sm:grid-cols-[minmax(0,1fr)_5rem_9rem]">
          <div className="flex min-w-0 items-start gap-2">
            <span className="mt-[0.2rem]">
              <StatusIcon status={node.status} />
            </span>
            <div className="min-w-0">
              {expandable ? (
                <button
                  type="button"
                  aria-expanded={open}
                  aria-controls={regionId}
                  onClick={() => setOpen((o) => !o)}
                  className="group text-left hover:text-accent"
                >
                  {title}
                  <ChevronRight
                    aria-hidden
                    className={`ml-1 inline size-3.5 align-[-0.1em] text-ink-3 transition-transform duration-150 group-hover:text-accent ${open ? "rotate-90" : ""}`}
                  />
                </button>
              ) : (
                title
              )}
              <p className={`mt-0.5 text-sm ${node.status === "failed" ? "text-bad" : "text-ink-2"}`}>
                {node.summary}
              </p>
            </div>
          </div>
          <div className="tabular pt-0.5 text-right text-sm text-ink-2">
            {running ? (
              <span aria-hidden className="inline-block h-3 w-10 animate-pulse rounded-sm bg-well" />
            ) : (
              formatDuration(node.durationMs)
            )}
          </div>
          <div className="col-span-2 pt-2 sm:col-span-1">
            {running ? (
              <div aria-hidden className="h-1.5 w-full animate-pulse rounded-full bg-well" />
            ) : pending ? null : segments ? (
              <SegmentBar steps={segments} />
            ) : (
              <TimeBar share={node.share} animate status={node.status} />
            )}
          </div>
        </div>
        {node.error && node.status === "failed" && node.step !== "answer" && (
          <p className="mb-2 ml-6 rounded-sm bg-bad-soft px-2.5 py-1.5 font-mono text-xs text-bad">{node.error}</p>
        )}
        {expandable && open && (
          <div id={regionId} className="mb-3 ml-6 space-y-2">
            {detail}
          </div>
        )}
        {children}
      </div>
    </li>
  );
}

export function PlanTree({ nodes, rootOutput, details = {}, running = false, elapsedMs = 0, caption }: Props) {
  const [root, ...steps] = nodes;
  if (!root) return null;
  const pending = root.status === "pending";
  const rootNode = running ? { ...root, summary: `Running for ${formatDuration(elapsedMs)}` } : root;

  return (
    <section aria-label={caption} aria-busy={running} className="rounded-md border border-rule bg-surface">
      <div className="flex items-baseline justify-between gap-4 border-b border-rule px-4 py-2 sm:px-5 sm:py-2.5">
        <h2 className="text-sm font-semibold">{caption}</h2>
        <div className="hidden text-xs text-ink-3 sm:grid sm:grid-cols-[5rem_9rem] sm:gap-x-4">
          <span className="text-right">Time</span>
          <span>Share of total</span>
        </div>
      </div>
      <ol className="px-4 pb-3 [--indent:1rem] sm:px-5 sm:[--indent:1.25rem]">
        <NodeRow
          node={rootNode}
          depth={0}
          detail={details[root.key]}
          pending={pending}
          running={running}
          last={steps.length === 0}
          segments={steps}
        >
          {rootOutput && <div className="mb-4 ml-6 space-y-4">{rootOutput}</div>}
        </NodeRow>
        {steps.map((node, i) => (
          <NodeRow
            key={node.key}
            node={node}
            depth={i + 1}
            detail={details[node.key]}
            pending={pending || running}
            running={running}
            last={i === steps.length - 1}
          />
        ))}
      </ol>
    </section>
  );
}
