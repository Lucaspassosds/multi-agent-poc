import type { Icon } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

export default function SectionHeading({
  icon: IconCmp,
  children,
  right,
  className = '',
}: {
  icon?: Icon
  children: ReactNode
  right?: ReactNode
  className?: string
}) {
  return (
    <div className={`mb-3 flex items-center justify-between ${className}`}>
      <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
        {IconCmp && <IconCmp size={16} weight="regular" className="text-accent" />}
        {children}
      </h2>
      {right != null && <div className="text-xs text-mutedForeground tabular-nums">{right}</div>}
    </div>
  )
}
