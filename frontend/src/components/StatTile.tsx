import Card from './Card'

export default function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <p className="mb-1 text-xs text-mutedForeground">{label}</p>
      <p className="text-2xl font-semibold text-foreground">{value}</p>
    </Card>
  )
}
