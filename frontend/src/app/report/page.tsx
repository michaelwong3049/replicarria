'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

interface SimResult {
  verdict: string
  summary: string
  key_moments: { round: number; agent: string; quote: string }[]
  final_indices: {
    unemployment: number
    social_unrest: number
    gov_approval: number
    prices: number
    businesses_open: number
  }
}

const INITIAL: SimResult['final_indices'] = {
  unemployment: 5.4,
  social_unrest: 12,
  gov_approval: 56,
  prices: 2.1,
  businesses_open: 95,
}

export default function ReportPage() {
  const router = useRouter()
  const [result, setResult] = useState<SimResult | null>(null)
  const [headline, setHeadline] = useState('POLICY SIMULATION')

  useEffect(() => {
    const raw = sessionStorage.getItem('sim_result')
    if (raw) setResult(JSON.parse(raw))
    const h = sessionStorage.getItem('sim_headline')
    if (h) setHeadline(h)
  }, [])

  const verdictColor =
    result?.verdict === 'positive' ? '#6aaa50'
    : result?.verdict === 'negative' ? '#e07050'
    : '#d4943a'

  const final = result?.final_indices ?? INITIAL

  return (
    <div className="relative min-h-screen flex flex-col items-center overflow-hidden">
      <img
        src="/assets/bg.gif"
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
        style={{ imageRendering: 'pixelated' }}
      />

      <div className="relative z-10 flex flex-col items-center w-full max-w-lg px-6 py-10 gap-6">
        <h1
          className="pixel-text text-center"
          style={{ fontSize: '2rem', color: '#f5d76e', textShadow: '0 4px 0 #7c5200, 0 6px 0 #000' }}
        >
          SIMULATION REPORT
        </h1>

        <p className="pixel-text text-[9px] text-center" style={{ color: '#a89060', textShadow: '0 1px 0 #000' }}>
          {headline.length > 80 ? headline.slice(0, 80) + '…' : headline}
        </p>

        <div
          className="pixel-panel w-full flex flex-col items-center gap-3 py-5 px-6"
          style={{ borderColor: verdictColor }}
        >
          <p className="pixel-text text-[9px]" style={{ color: '#a89060' }}>VERDICT</p>
          <p
            className="pixel-text text-[1.6rem]"
            style={{ color: verdictColor, textShadow: `0 0 20px ${verdictColor}, 0 3px 0 #000` }}
          >
            {(result?.verdict ?? 'PENDING').toUpperCase()}
          </p>
          {result?.summary && (
            <p style={{ color: '#e8e0cc', fontSize: '0.85rem', lineHeight: '1.6', textAlign: 'center', fontFamily: 'Georgia, serif', fontStyle: 'italic' }}>
              {result.summary}
            </p>
          )}
        </div>

        <div className="pixel-panel w-full flex flex-col gap-3 py-4 px-5">
          <p className="pixel-text text-[9px]" style={{ color: '#f5d76e' }}>FINAL INDICES</p>
          <IndexRow label="UNEMPLOYMENT" before={INITIAL.unemployment} after={final.unemployment} unit="%" lowerIsBetter />
          <IndexRow label="SOCIAL UNREST" before={INITIAL.social_unrest} after={final.social_unrest} unit="" lowerIsBetter />
          <IndexRow label="GOV APPROVAL" before={INITIAL.gov_approval} after={final.gov_approval} unit="%" />
          <IndexRow label="PRICE INDEX" before={INITIAL.prices} after={final.prices} unit="%" lowerIsBetter />
          <IndexRow label="BUSINESSES" before={INITIAL.businesses_open} after={final.businesses_open} unit="%" />
        </div>

        {result?.key_moments && result.key_moments.length > 0 && (
          <div className="pixel-panel w-full flex flex-col gap-3 py-4 px-5">
            <p className="pixel-text text-[9px]" style={{ color: '#f5d76e' }}>KEY MOMENTS</p>
            {result.key_moments.map((m, i) => (
              <div key={i} className="flex flex-col gap-1" style={{ borderLeft: '2px solid #6d5a2c', paddingLeft: '8px' }}>
                <span className="pixel-text text-[8px]" style={{ color: '#d4943a' }}>Month {m.round} — {m.agent}</span>
                <span className="pixel-text text-[8px] leading-relaxed" style={{ color: '#d4ccb0' }}>"{m.quote}"</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-4 w-full">
          <button
            className="pixel-menu-btn w-full"
            onClick={() => {
              sessionStorage.removeItem('sim_result')
              router.push('/')
            }}
          >
            RUN AGAIN
          </button>
          <button
            className="pixel-back-btn"
            onClick={() => router.push('/')}
          >
            &lt; MAIN MENU
          </button>
        </div>
      </div>
    </div>
  )
}

function IndexRow({
  label, before, after, unit, lowerIsBetter = false,
}: {
  label: string; before: number; after: number; unit: string; lowerIsBetter?: boolean
}) {
  const improved = lowerIsBetter ? after < before : after > before
  const same = Math.abs(after - before) < 0.05
  const color = same ? '#d4ccb0' : improved ? '#6aaa50' : '#e07050'
  const arrow = same ? '=' : improved ? '▲' : '▼'

  return (
    <div className="flex justify-between items-center">
      <span className="pixel-text text-[7px]" style={{ color: '#a89060' }}>{label}</span>
      <div className="flex items-center gap-2">
        <span className="pixel-text text-[7px]" style={{ color: '#6a5a30' }}>{before.toFixed(1)}{unit}</span>
        <span className="pixel-text text-[8px]" style={{ color }}>{arrow}</span>
        <span className="pixel-text text-[9px]" style={{ color }}>{after.toFixed(1)}{unit}</span>
      </div>
    </div>
  )
}
