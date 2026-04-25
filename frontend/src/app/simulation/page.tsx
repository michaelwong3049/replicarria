'use client'

import dynamic from 'next/dynamic'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { connectSocket, disconnectSocket, bridge } from '@/lib/eventBridge'

const GameCanvas = dynamic(() => import('@/components/GameCanvas'), { ssr: false })

const SPEEDS = [1, 2, 4]

interface LogEntry {
  name: string
  role: string
  text: string
  mood: string
  photo_url?: string
}

interface Indicators {
  unemployment: number
  social_unrest: number
  gov_approval: number
  prices: number
  businesses_open: number
}

export default function SimulationPage() {
  const router = useRouter()
  const [speed, setSpeed] = useState(1)
  const [month, setMonth] = useState(1)
  const [totalMonths, setTotalMonths] = useState(3)
  const [headline, setHeadline] = useState('SIMULATION RUNNING')
  const [log, setLog] = useState<LogEntry[]>([])
  const [indicators, setIndicators] = useState<Indicators>({
    unemployment: 5.4,
    social_unrest: 12,
    gov_approval: 56,
    prices: 2.1,
    businesses_open: 95,
  })
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const stored = sessionStorage.getItem('sim_headline')
    if (stored) setHeadline(stored)
    const months = sessionStorage.getItem('sim_months')
    if (months) setTotalMonths(Number(months))
  }, [])

  useEffect(() => {
    connectSocket()

    bridge.on('agent_speak', (data: LogEntry) => {
      setLog(prev => [data, ...prev].slice(0, 30))
    })

    bridge.on('economic_update', (data: { round: number; unemployment: number; social_unrest: number; gov_approval: number; prices: number; businesses_open: number }) => {
      setMonth(data.round)
      setIndicators({
        unemployment: data.unemployment,
        social_unrest: data.social_unrest,
        gov_approval: data.gov_approval,
        prices: data.prices * 100,
        businesses_open: data.businesses_open,
      })
    })

    bridge.on('simulation_end', (data: { verdict: string; summary: string; key_moments: unknown[]; final_indices: unknown }) => {
      sessionStorage.setItem('sim_result', JSON.stringify(data))
      router.push('/report')
    })

    return () => {
      bridge.removeAllListeners()
      disconnectSocket()
    }
  }, [router])

  return (
    <div className="relative w-screen h-screen overflow-hidden">

      <GameCanvas />

      <div className="absolute top-0 left-0 w-48 flex flex-col gap-2 p-3" style={{ background: 'rgba(22, 14, 6, 0.78)', borderRight: '2px solid #6d5a2c', borderBottom: '2px solid #6d5a2c', boxShadow: 'inset -1px 0 0 #000' }}>
        <p className="pixel-text text-[9px]" style={{ color: '#f5d76e', textShadow: '0 2px 0 #7c5200, 0 3px 0 #000' }}>EVENT LOG</p>
        <div ref={logRef} className="log-scroll flex flex-col gap-3 overflow-y-auto" style={{ maxHeight: '280px' }}>
          {log.length === 0 ? (
            <>
              <EventEntry name="Maria Santos" role="Factory Worker" text="This policy is going to hurt people like us." mood="anxious" />
              <EventEntry name="James Okafor" role="Small Business" text="Finally, something that helps the economy." mood="hopeful" />
              <EventEntry name="Priya Nair" role="Healthcare Worker" text="We need more support, not less." mood="frustrated" />
            </>
          ) : (
            log.map((e, i) => <EventEntry key={i} {...e} />)
          )}
        </div>
      </div>

      <div className="absolute top-0 right-0 w-48 flex flex-col gap-4 p-3" style={{ background: 'rgba(22, 14, 6, 0.78)', borderLeft: '2px solid #6d5a2c', boxShadow: 'inset 1px 0 0 #000' }}>
        <p className="pixel-text text-[9px]" style={{ color: '#f5d76e', textShadow: '0 2px 0 #7c5200, 0 3px 0 #000' }}>INDICATORS</p>
        <div className="flex flex-col gap-4">
          <Indicator label="UNEMPLOYMENT" value={indicators.unemployment} unit="%" color="#e07050" />
          <Indicator label="SOCIAL UNREST" value={indicators.social_unrest} unit="" color="#d4943a" />
          <Indicator label="GOV APPROVAL" value={indicators.gov_approval} unit="%" color="#6aaa50" />
          <Indicator label="PRICE INDEX" value={indicators.prices} unit="%" color="#c8b030" />
          <Indicator label="BUSINESSES" value={indicators.businesses_open} unit="%" color="#5090c8" />
        </div>
      </div>

      <div className="absolute top-0 left-48 right-48 flex items-center justify-between px-4 py-2" style={{ background: 'rgba(22, 14, 6, 0.78)', borderBottom: '2px solid #6d5a2c', boxShadow: 'inset 0 -1px 0 #000' }}>
        <p className="pixel-text text-[8px]" style={{ color: '#d4ccb0', textShadow: '0 2px 0 #000' }}>MONTH {month} / {totalMonths}</p>
        <p className="pixel-text text-[9px] truncate mx-4" style={{ color: '#f5d76e', textShadow: '0 2px 0 #7c5200, 0 3px 0 #000' }}>{headline}</p>
        <div className="flex items-center gap-1 shrink-0">
          {SPEEDS.map(s => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className="pixel-text text-[7px] px-2 py-1"
              style={{
                background: speed === s ? 'rgba(109, 90, 44, 0.6)' : 'rgba(22, 14, 6, 0.4)',
                border: `1px solid ${speed === s ? '#f5d76e' : '#6d5a2c'}`,
                color: speed === s ? '#f5d76e' : '#a89060',
                cursor: 'pointer',
              }}
            >{s}x</button>
          ))}
        </div>
      </div>

    </div>
  )
}

function EventEntry({ name, role, text, mood, photo_url }: { name: string; role: string; text: string; mood: string; photo_url?: string }) {
  const moodColor: Record<string, string> = {
    anxious: '#d4943a',
    hopeful: '#6aaa50',
    frustrated: '#e07050',
    neutral: '#d4ccb0',
    angry: '#e03030',
    worried: '#d4943a',
  }
  const color = moodColor[mood] ?? '#d4ccb0'

  return (
    <div className="flex flex-col gap-1" style={{ borderLeft: `2px solid ${color}`, paddingLeft: '6px' }}>
      <div className="flex items-center gap-1">
        {photo_url && <img src={photo_url} alt="" className="w-4 h-4 rounded-sm" style={{ imageRendering: 'pixelated' }} />}
        <span className="pixel-text text-[8px]" style={{ color, textShadow: '0 1px 0 #000' }}>{name}</span>
      </div>
      <span className="pixel-text text-[7px]" style={{ color: '#6a5a30' }}>{role}</span>
      <span className="pixel-text text-[8px] leading-relaxed" style={{ color: '#d4ccb0', textShadow: '0 1px 0 #000' }}>{text}</span>
    </div>
  )
}

function Indicator({ label, value, unit, color }: { label: string; value: number; unit: string; color: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center">
        <span className="pixel-text text-[7px]" style={{ color: '#d4ccb0', textShadow: '0 1px 0 #000' }}>{label}</span>
        <span className="pixel-text text-[9px]" style={{ color, textShadow: '0 1px 0 #000' }}>{value.toFixed(1)}{unit}</span>
      </div>
      <div style={{ height: '4px', background: '#1a1008', border: '1px solid #3a2a10' }}>
        <div style={{ width: `${Math.min(value, 100)}%`, height: '100%', background: color }} />
      </div>
    </div>
  )
}
