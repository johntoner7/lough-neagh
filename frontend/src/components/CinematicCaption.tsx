import { getEraCaption, getEraKey } from '../eraCaptions'

interface Props {
  year: number
}

export default function CinematicCaption({ year }: Props) {
  const caption = getEraCaption(year)
  const eraKey = getEraKey(year)
  if (!caption) {return null}
  return (
    <div className="cinematic-caption">
      <span key={eraKey}>{caption}</span>
    </div>
  )
}
