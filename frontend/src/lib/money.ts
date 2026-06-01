type CategoryRow = Record<string, string | number | null>

/** The non-Month numeric columns of a categories pivot = the category names. */
export function categoryNames(rows: CategoryRow[]): string[] {
  if (rows.length === 0) return []
  return Object.keys(rows[0]).filter((k) => k.toLowerCase() !== "month")
}

/**
 * Breakdown of the most recent month into `{name, value}` pairs (drops the Month
 * column and any non-positive categories), sorted descending. For donut charts.
 */
export function lastCategoryBreakdown(
  rows: CategoryRow[],
): { name: string; value: number }[] {
  if (rows.length === 0) return []
  const last = rows[rows.length - 1]
  return categoryNames(rows)
    .map((name) => ({ name, value: Number(last[name]) || 0 }))
    .filter((c) => c.value > 0)
    .sort((a, b) => b.value - a.value)
}
