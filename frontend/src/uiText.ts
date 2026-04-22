export const UI_TEXT = {
  app: {
    connecting: 'Connecting…',
    errorTitle: 'Unable to load',
    errorMessage: 'The data service is unavailable. Please try refreshing the page.',
    errorRetry: 'Refresh',
  },
  sidebar: {
    title: 'NI River Phosphorus',
    subtitle: 'River monitoring network · 1990–2024',
    collapseAriaLabel: 'Collapse sidebar',
    expandAriaLabel: 'Expand sidebar',
    baselineHeadline: 'In 1990, every river in this network exceeded the legal phosphorus limit. The algae blooms of 2023 had been building for decades.',
    baselineSubline: 'Press Play to see where progress was made, where it stalled, and what that means for the lough today.',
    aboveThresholdLabel: 'of rivers above legal threshold',
    narrationSewage: 'Improvement driven by sewage works upgrades from the 1980s.',
    narrationStalled: 'Progress stalled around 2008. Agricultural runoff is now the dominant source, and there is no equivalent regulatory intervention.',
    aboveThresholdSummary: (above: number, total: number, year: number) =>
      `${above} of ${total} monitored rivers exceed the legal phosphorus limit in ${year}`,
    noDataForYear: 'No data for this year',
    headlineHint: 'Click a circle on the map for detail.',
    sedimentCallout: 'Even if every river reached compliance today, AFBI scientists estimate it would take around 40 years for Lough Neagh to recover. The phosphorus accumulated over decades is still in the sediment.',
    sections: {
      year: 'Year',
      catchment: 'Catchment',
      concentration: 'Phosphorus level',
    },
    controls: {
      play: 'Play',
      pause: 'Pause',
      yearHint: 'Press Play to watch 35 years of change, and where it stopped.',
      allCatchments: 'All catchments',
    },
    farmLayer: {
      title: 'Cattle density (farm census)',
      show: 'Show layer',
      hide: 'Hide layer',
      legendNote: 'Syncs to timeline (2015–2024). Hover a ward for details. Areas with higher cattle density tend to have higher phosphorus levels.',
    },
    annotations: {
      nap: 'Nitrates Action Programme introduced. Progress had already stalled.',
      loughNeagh: 'Lough Neagh crisis. Algae visible from space.',
    },
    legend: {
      belowWfd: 'Below legal limit',
      midBand: 'Above limit — moderate',
      highBand: 'Above limit — high',
      wfdLimitPrefix: 'Legal clean-water limit:',
      wfdLimitValue: '0.035 mg/l',
      noData: 'No data this year',
    },
    methodology: {
      line1: 'Sewage treatment upgrades in the early 1980s drove most of the improvement visible in the 1990s. Progress stalled around 2008.',
      line2: 'Agriculture contributes 62% of the phosphorus entering Lough Neagh. No equivalent intervention exists for diffuse agricultural runoff.',
      line3:
        'The phosphorus that accumulated in Lough Neagh\'s sediment during this period continues to fuel algae blooms today, regardless of what the rivers are currently carrying.',
      source: 'Source: DAERA, 2026. Six key stations = main Lough Neagh tributaries.',
    },
  },
  header: {                                                                                                                                                                                    
    argumentLine1: 'Lough Neagh supplies 40% of Northern Ireland\'s drinking water. In 2023 it turned green with toxic algae visible from space.',                                             
    argumentLine2: 'Agriculture contributes 62% of the phosphorus driving it. These are the rivers carrying it, and most are still failing the legal limit for phosphorus.',                   
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
    sparseYearWarning: '⚠ Limited data this year — fewer than 8 samples',
    chartLabel: 'Phosphorus (mg/l) · 1990–2024',
    chartLegendAnnual: 'Yearly reading',
    chartLegendRolling: '5-year average',
    chartLegendWfd: 'Legal limit',
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
        'The Upper Bann has not recorded a single year below the legal phosphorus limit in 35 years of monitoring. In every year of the dataset, it has delivered phosphorus into Lough Neagh above the threshold for safe ecological status.',
      10328:
        'The Blackwater catchment spans the NI–Republic border. Persistent agricultural runoff has kept levels above the WFD limit for decades.',
      10361:
        'The Ballinderry approaches compliance in wetter years but consistently exceeds the legal threshold, linked to intensive livestock farming.',
      10380:
        'The Moyola came closer to compliance than any other tributary, recording its lowest levels between 2006 and 2009. Since 2013 that progress has reversed, a trend confirmed as statistically significant. The reversal coincides with a period of significant dairy expansion in NI — EU milk quotas were abolished in 2015 and the dairy herd grew substantially in subsequent years. Of all six rivers, the Moyola most clearly shows what happens when agricultural growth outpaces regulation.',
    } as Record<number, string>,
  },
  sparkline: {
    annualMeanLabel: 'Yearly reading',
    rollingMeanLabel: '5-year average',
    tooltipUnit: 'mg/l',
  },
} as const
