import { UI_TEXT } from './uiText'

interface Props {
  year: number
  onYearChange: (year: number) => void
}

export default function TimelineBar({ year, onYearChange }: Props) {
  const sliderPct = ((year - 1990) / (2024 - 1990)) * 100
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
          min={1990}
          max={2024}
          value={year}
          style={{ background: sliderBg }}
          onChange={e => onYearChange(Number(e.target.value))}
        />

        <div className="timeline-range-labels">
          <span>1990</span>
          <span>2024</span>
        </div>
      </div>
    </div>
  )
}
