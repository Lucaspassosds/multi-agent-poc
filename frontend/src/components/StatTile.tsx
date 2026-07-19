export default function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-primary p-4">
      <p className="text-xs text-mutedForeground mb-1">{label}</p>
      <p className="text-2xl font-semibold text-foreground">{value}</p>
    </div>
  )
}
