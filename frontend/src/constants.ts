export const YEAR_MIN = 1990
export const YEAR_MAX = 2024
export const LAKE_STATUS_YEAR = 2024

export const FARM_YEAR_MIN = 2015
export const FARM_YEAR_MAX = 2024

export const WFD_THRESHOLD = 0.035

export const KEY_STATION_CODES_ORDERED = [10212, 10233, 10271, 10328, 10361, 10380]

export const lowRiverPhosphorusColor = '#38bdf8' // Sky Blue (Clean/Good)
export const midRiverPhosphorusColor = '#f97316' // Solid Orange (Above limit)
export const highRiverPhosphorusColor = '#b91c1c' // Deep Crimson Red (Serious/High)

export const lowCattleDensityColor = '#f8fafc' // Near-white (Low)
export const midCattleDensityColor = '#bbf7d0' // Minty Green (Medium - light and airy)
export const highCattleDensityColor = '#166534' // Deep Green (High - big jump in darkness)
export const veryHighCattleDensityColor = '#052e16' // Black-Green (Very High - extremely dense)

// NI Water modelled spills are a single Nov-2025 snapshot with no year axis.
// Shown only at the timeline's present-day end, mirroring LAKE_STATUS_YEAR.
export const STORM_OVERFLOW_SNAPSHOT_YEAR = YEAR_MAX

// Violet: the only unused, colour-blind-distinguishable family left on this map.
// Blue→orange→red is river phosphorus, white→green is cattle density, and the
// green/yellow/orange/red ramp is lake status — a sewage layer in any of those
// would read as another phosphorus measurement.
export const overflowUnsatisfactoryColor = '#7c3aed' // Violet (spills modelled)
export const overflowSatisfactoryColor = '#a78bfa' // Light violet
export const overflowUnmodelledColor = '#9ca3af' // Grey — no estimate exists
