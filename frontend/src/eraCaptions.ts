export type EraCaption = { from: number; to: number; text: string }

export const ERA_CAPTIONS: EraCaption[] = [
  {
    from: 1990,
    to: 1999,
    text: 'Sewage treatment upgrades removed 80 tonnes of phosphorus a year. Every monitored station was still failing.',
  },
  {
    from: 2000,
    to: 2011,
    text: 'The Water Framework Directive sets legal targets. The Moyola briefly achieves compliance — the only tributary ever to do so.',
  },
  {
    from: 2012,
    to: 2014,
    text: 'Going for Growth launches. NI expands meat and dairy production to feed 10 million people.',
  },
  {
    from: 2015,
    to: 2019,
    text: 'EU milk quotas abolished. The Moyola begins reversing. River phosphorus rises.',
  },
  {
    from: 2020,
    to: 2022,
    text: 'Between 2012 and 2022, phosphorus in NI rivers rose 55%. WFD gains reversed.',
  },
  {
    from: 2023,
    to: 2024,
    text: 'Algae blooms visible from space. The sediment will take 20 years to recover.',
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
