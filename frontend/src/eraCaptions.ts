export type EraCaption = { from: number; to: number; text: string }

export const ERA_CAPTIONS: EraCaption[] = [
  {
    from: 1990,
    to: 1999,
    text: 'Sewage treatment upgrades removed 80 tonnes of phosphorus a year, causing levels of phosphorus to fall across monitored stations.',
  },
  {
    from: 2000,
    to: 2011,
    text: 'The Water Framework Directive sets legal targets for achieving all surface waters to achieve good ecologoical status by 2027.',
  },
  {
    from: 2012,
    to: 2014,
    text: 'Going for Growth programme is launched to prioritise expanding the agri-food sector.',
  },
  {
    from: 2015,
    to: 2019,
    text: 'EU milk quotas abolished, allowing dairy farmers to expand production and increase the size of the cattle herd.',
  },
  {
    from: 2020,
    to: 2022,
    text: 'Between 2012 and 2022, phosphorus in NI rivers rose 55%.',
  },
  {
    from: 2023,
    to: 2024,
    text: 'Algae blooms in Lough Neagh are visible from space.',
  },
]

export function getEraKey(year: number): string {
  const era = ERA_CAPTIONS.find(e => year >= e.from && year <= e.to)
  return era ? `${era.from}-${era.to}` : 'unknown'
}

export function getEraCaption(year: number): string | null {
  const era = ERA_CAPTIONS.find(e => year >= e.from && year <= e.to)
  return era ? era.text : null
}
