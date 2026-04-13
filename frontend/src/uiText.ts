export const UI_TEXT = {
  app: {
    errorPrefix: '⚠',
    apiRunningHint: 'Make sure the API is running:',
    apiRunCommand: 'uvicorn api.main:app --port 8000',
    connecting: 'Connecting to API…',
  },
  sidebar: {
    title: 'NI River Phosphorus',
    subtitle: 'DAERA monitoring network · 1990–2024',
    collapseAriaLabel: 'Collapse sidebar',
    expandAriaLabel: 'Expand sidebar',
    baselineHeadline: '1990 mean phosphorus: 0.34 mg/l (nearly 10× the legal limit)',
    baselineSubline:
      'Every monitored station exceeded the WFD threshold. Press Play to see what changed — and what didn\'t.',
    aboveThresholdLabel: 'of rivers above legal threshold',
    aboveThresholdSummary: (above: number, total: number, year: number) =>
      `${above} of ${total} monitored stations exceed the WFD phosphorus limit (0.035 mg/l) in ${year}`,
    noDataForYear: 'No data for this year',
    headlineHint: 'Click a circle on the map for detail.',
    sections: {
      year: 'Year',
      stationView: 'Station view',
      catchment: 'Catchment',
      concentration: 'P(SOL) concentration',
    },
    controls: {
      play: 'Play',
      pause: 'Pause',
      yearHint: 'Press Play to watch 35 years of change — and where it stopped.',
      showKeyOnly: 'Show key stations only',
      showAll: 'Show all stations',
      allCatchments: 'All catchments',
    },
    annotations: {
      nap: 'Nitrates Action Programme introduced. Progress had already stalled.',
      loughNeagh: 'Lough Neagh crisis. Algae visible from space.',
    },
    legend: {
      belowWfd: '< 0.035 mg/l',
      midBand: '0.035–0.1 mg/l',
      highBand: '> 0.1 mg/l',
      wfdLimitPrefix: 'WFD good-status limit:',
      wfdLimitValue: '0.035 mg/l',
      noData: 'No data this year',
    },
    methodology: {
      line1: 'Sewage treatment upgrades in the early 1980s drove most of the improvement visible in the 1990s. Progress stalled around 2008.',
      line2: 'Agriculture contributes 62% of the phosphorus entering Lough Neagh. No equivalent intervention exists for diffuse agricultural runoff.',
      line3:
        'The phosphorus that accumulated in Lough Neagh\'s sediment during this period continues to fuel algae blooms today, independent of what the rivers currently carry.',
      source: 'Source: DAERA, 2026. Six key stations = main Lough Neagh tributaries.',
    },
  },
  header: {
    argumentLine1: 'Agriculture contributes 62% of the phosphorus entering Lough Neagh.',
    argumentLine2: 'These are the rivers carrying it.',
  },
  map: {
    calloutLine1: 'These six rivers',
    calloutLine2: 'feed Lough Neagh',
  },
  drawer: {
    closeAriaLabel: 'Close station details',
    closeSymbol: '×',
  },
  stationDetail: {
    backToAll: '← All stations',
    catchmentSuffix: ' catchment',
    unit: ' mg/l',
    badgeCompliant: '▼ Compliant',
    badgeAboveLimit: '▲ Above limit',
    sparseYearWarning: '⚠ Sparse year — fewer than 8 readings',
    chartLabel: 'P(SOL) mg/l · 1990–2024',
    chartLegendAnnual: 'Annual mean',
    chartLegendRolling: '5-yr mean',
    chartLegendWfd: 'WFD limit',
    chartLoading: 'Loading chart…',
    trend: {
      noData: '— No trend data',
      improving: '↓ Improving',
      worsening: '↑ Worsening',
      noClearTrend: '→ No clear trend',
      insufficientData: 'insufficient data',
    },
    interpretive: {
      10212:
        'The Main drains central Co. Antrim. Despite falling from historic highs, levels remain above the WFD limit with little recent improvement.',
      10233:
        'The Six Mile Water flows through a heavily farmed lowland catchment. Phosphorus consistently sits just above the legal threshold.',
      10271:
        'The Upper Bann carries the highest phosphorus load of the six tributaries, more than three times the WFD good-status limit in some years.',
      10328:
        'The Blackwater catchment spans the NI–Republic border. Persistent agricultural runoff has kept levels above the WFD limit for decades.',
      10361:
        'The Ballinderry approaches compliance in wetter years but consistently exceeds the legal threshold, linked to intensive livestock farming.',
      10380:
        'The Moyola improved through the 2000s and briefly approached compliance, the only tributary to do so. Since 2013, levels have been rising, a trend confirmed as statistically significant.',
    } as Record<number, string>,
  },
  sparkline: {
    annualMeanLabel: 'Annual mean',
    rollingMeanLabel: '5-yr mean',
    tooltipUnit: 'mg/l',
  },
} as const