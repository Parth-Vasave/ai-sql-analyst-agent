import type { QueryPlan } from '../api/types'

export function PlanBlock({ plan }: { plan: QueryPlan }) {
  const parts: string[] = [plan.intent]
  if (plan.metrics.length) parts.push(plan.metrics.join(', '))
  if (plan.filters.length) parts.push(`where ${plan.filters.join('; ')}`)
  if (plan.group_by.length) parts.push(`grouped by ${plan.group_by.join(', ')}`)
  if (plan.order_by) parts.push(`ordered by ${plan.order_by}`)
  if (plan.limit) parts.push(`limit ${plan.limit}`)

  return (
    <div className="font-mono text-[14px] leading-relaxed">
      <span className="text-accent">[plan]</span> <span>{parts.join(' · ')}</span>
      {plan.assumptions.length > 0 && (
        <ul className="mt-0.5 ml-[3.5rem] list-none text-ink-dim">
          {plan.assumptions.map((assumption, index) => (
            <li key={index}>— {assumption}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
