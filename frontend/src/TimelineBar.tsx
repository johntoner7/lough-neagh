import { YEAR_MIN, YEAR_MAX } from './constants'
import { UI_TEXT } from './uiText'

interface Props {
  year: number
  onYearChange: (year: number) => void
}

export default function TimelineBar({ year, onYearChange }: Props) {
  const sliderPct = ((year - YEAR_MIN) / (YEAR_MAX - YEAR_MIN)) * 100
  const sliderBg = `linear-gradient(to right, var(--accent) ${sliderPct}%, var(--surface-hi) ${sliderPct}%)`

  return (
    <div className="timeline-bar">
      <div className="timeline-controls">
        <span className="timeline-year">{year}</span>
      </div>

      <div className="timeline-slider-wrap">
        <div className="timeline-annotations" aria-hidden="true">
          <div className="timeline-annotation timeline-annotation--2007">
            <span className="annotation-year-label">2007</span>
            <span className="timeline-annotation-tick" />
            <span className="timeline-annotation-pill">{UI_TEXT.sidebar.annotations.nap}</span>
          </div>
          <div className="timeline-annotation timeline-annotation--2023">
            <span className="annotation-year-label">2023</span>
            <span className="timeline-annotation-tick" />
            <span className="timeline-annotation-pill">{UI_TEXT.sidebar.annotations.loughNeagh}</span>
          </div>
        </div>

        <input
          type="range"
          min={YEAR_MIN}
          max={YEAR_MAX}
          value={year}
          style={{ background: sliderBg }}
          onChange={e => onYearChange(Number(e.target.value))}
        />

        <div className="timeline-range-labels">
          <span>{YEAR_MIN}</span>
          <span>{YEAR_MAX}</span>
        </div>
      </div>
    </div>
  )
}
