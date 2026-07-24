import { PuzzlePiece } from '@phosphor-icons/react'
import Badge from './Badge'
import type { SkillInvocation } from '../lib/types'

export default function SkillBadge({ skill }: { skill: SkillInvocation }) {
  return (
    <Badge tone="accent">
      <PuzzlePiece size={13} weight="regular" />
      <span className="font-medium">{skill.name}</span>
      {skill.script && (
        <span className="text-accent/80">
          · {skill.script}
          {skill.script_result != null && <> → {skill.script_result}</>}
        </span>
      )}
    </Badge>
  )
}
