import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
} from 'chart.js'
import type { ChartOptions, TooltipItem } from 'chart.js'
import annotationPlugin from 'chartjs-plugin-annotation'
import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'

import { WFD_THRESHOLD } from '../constants'
import { UI_TEXT } from '../uiText'

import type { TimeSeriesPoint } from '../types'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler, annotationPlugin,
)

interface Props {
  series: TimeSeriesPoint[]
  currentYear: number
  yMax?: number
  yTickStep?: number
}

export default function SparklineChart({ series, currentYear, yMax, yTickStep }: Props) {
  const labels = useMemo(() => series.map(p => String(p.year)), [series])

  const data = useMemo(() => ({
    labels,
    datasets: [
      {
        label: UI_TEXT.sparkline.annualMeanLabel,
        data: series.map(p => p.annual_mean_p_sol),
        borderColor: '#c0551a',
        backgroundColor: 'rgba(192,85,26,0.06)',
        borderWidth: 1.5,
        tension: 0.2,
        fill: true,
        pointRadius: series.map(p => (p.sparse_year ? 3 : 2)),
        pointBackgroundColor: series.map(p => (p.sparse_year ? 'transparent' : '#c0551a')),
        pointBorderColor: '#c0551a',
        pointBorderWidth: 1.5,
        spanGaps: false,
      },
      {
        label: UI_TEXT.sparkline.rollingMeanLabel,
        data: series.map(p => p.rolling_mean_5yr),
        borderColor: 'rgba(136,134,128,0.7)',
        borderWidth: 1.5,
        borderDash: [4, 3],
        pointRadius: 0,
        tension: 0.3,
        fill: false,
        spanGaps: true,
      },
    ],
  }), [series, labels])

  const options = useMemo((): ChartOptions<'line'> => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
        callbacks: {
          label: (ctx: TooltipItem<'line'>) => {
            const v = ctx.parsed.y
            return `${ctx.dataset.label}: ${v !== null ? v.toFixed(3) : '—'} ${UI_TEXT.sparkline.tooltipUnit}`
          },
        },
      },
      annotation: {
        annotations: {
          threshold: {
            type: 'line' as const,
            yMin: WFD_THRESHOLD,
            yMax: WFD_THRESHOLD,
            borderColor: '#fd8d3c',
            borderWidth: 1,
            borderDash: [4, 4],
          },
          ...(labels.includes(String(currentYear)) && {
            currentYear: {
              type: 'line' as const,
              xMin: String(currentYear),
              xMax: String(currentYear),
              borderColor: 'rgba(45,45,45,0.3)',
              borderWidth: 1,
              borderDash: [2, 2],
            },
          }),
        },
      } as object,
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          font: { size: 9 },
          color: '#888680',
          maxTicksLimit: 7,
          maxRotation: 0,
        },
      },
      y: {
        grid: { color: 'rgba(0,0,0,0.05)' },
        ticks: {
          font: { size: 9 },
          color: '#888680',
          ...(yTickStep ? { stepSize: yTickStep } : {}),
          callback: (v: number | string) => Number(v).toFixed(2),
        },
        min: 0,
        ...(yMax ? { max: yMax } : {}),
      },
    },
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
  }), [currentYear, labels, yMax, yTickStep])

  return (
    <div style={{ height: 130, width: '100%' }}>
      <Line data={data} options={options} />
    </div>
  )
}
