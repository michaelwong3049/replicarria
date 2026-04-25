'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

const SCAN_SOURCES = ['Reuters', 'BBC News', 'AP News']

type Screen = 'menu' | 'source' | 'scanning' | 'headlines' | 'upload' | 'configure' | 'history' | 'about'
type Memory = 'fresh' | 'living'

export default function Home() {
  const router = useRouter()
  const [screen, setScreen] = useState<Screen>('menu')
  const [scanIndex, setScanIndex] = useState(0)
  const [headlines, setHeadlines] = useState<{ source: string; title: string; description: string }[]>([])
  const [selectedHeadline, setSelectedHeadline] = useState<string | null>(null)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [memory, setMemory] = useState<Memory>('fresh')
  const [duration, setDuration] = useState(3)

  useEffect(() => {
    if (screen !== 'scanning') return
    if (scanIndex >= SCAN_SOURCES.length) {
      const t = setTimeout(() => setScreen('headlines'), 400)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => setScanIndex(i => i + 1), 800)
    return () => clearTimeout(t)
  }, [screen, scanIndex])

  async function startScan() {
    setScanIndex(0)
    setScreen('scanning')
    try {
      const res = await fetch('http://localhost:8000/news')
      const data = await res.json()
      setHeadlines(data)
    } catch {
      setHeadlines([
        { source: 'Reuters', title: 'Federal Reserve holds rates steady amid inflation concerns', description: 'The Fed kept interest rates unchanged as policymakers weigh persistent inflation against slowing growth.' },
        { source: 'BBC News', title: 'New minimum wage bill passes Senate committee vote', description: 'The bill would raise the federal minimum wage to $17 per hour over three years, affecting millions of workers.' },
        { source: 'AP News', title: 'US announces sweeping new tariffs on imported goods', description: 'The administration imposed 25% tariffs on steel and aluminum imports, citing national security concerns.' },
      ])
    }
  }

  return (
    <div className="relative min-h-screen flex flex-col items-center overflow-hidden">
      <img
        src="/assets/bg.gif"
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
        style={{ imageRendering: 'pixelated' }}
      />

      <div className="relative z-10 flex flex-col items-center w-full max-w-md px-6" style={{ paddingTop: '12vh' }}>
        <h1
          className="pixel-text text-center leading-tight mb-10"
          style={{ fontSize: '3.2rem', color: '#f5d76e', textShadow: '0 4px 0 #7c5200, 0 8px 0 #000' }}
        >
          REPLICARRIA
        </h1>

        {screen === 'menu' && (
          <div className="flex flex-col items-center gap-6">
            <MenuButton onClick={() => setScreen('source')}>NEW SIMULATION</MenuButton>
            <MenuButton onClick={() => setScreen('history')}>PAST SIMULATIONS</MenuButton>
            <a
              href="https://github.com/michaelwong3049/replicarria"
              target="_blank"
              rel="noopener noreferrer"
              className="pixel-menu-btn"
            >
              SOURCE CODE
            </a>
            <MenuButton onClick={() => setScreen('about')}>ABOUT</MenuButton>
          </div>
        )}

        {screen === 'source' && (
          <div className="flex flex-col items-center gap-6">
            <MenuButton onClick={startScan}>FETCH LATEST NEWS</MenuButton>
            <MenuButton onClick={() => setScreen('upload')}>UPLOAD POLICY PDF</MenuButton>
            <BackButton onClick={() => setScreen('menu')} />
          </div>
        )}

        {screen === 'history' && (
          <div className="flex flex-col items-center gap-4">
            <p className="pixel-text text-[12px]" style={{ color: '#4a4030' }}>NO PAST SIMULATIONS YET</p>
            <BackButton onClick={() => setScreen('menu')} />
          </div>
        )}

        {screen === 'about' && (
          <div className="flex flex-col items-center gap-6 text-center">
            <div className="flex flex-col gap-5 px-2 py-4 rounded" style={{ background: 'rgba(0,0,0,0.55)' }}>
              <p className="pixel-text text-[11px] leading-loose" style={{ color: '#e8d9a0', textShadow: '0 2px 0 #000' }}>
                A LIVING CITY SIMULATION WHERE AI AGENTS REACT TO REAL-WORLD NEWS AND POLICY EVENTS.
              </p>
              <p className="pixel-text text-[11px] leading-loose" style={{ color: '#e8d9a0', textShadow: '0 2px 0 #000' }}>
                WATCH CITIZENS DEBATE, ADAPT, AND RESHAPE THEIR CITY IN REAL TIME.
              </p>
              <p className="pixel-text text-[9px]" style={{ color: '#a89060', textShadow: '0 2px 0 #000' }}>
                BUILT AT A HACKATHON WITH LANGGRAPH + OLLAMA + PHASER 3
              </p>
            </div>
            <BackButton onClick={() => setScreen('menu')} />
          </div>
        )}

        {screen === 'scanning' && (
          <div className="flex flex-col items-center gap-4">
            <p className="pixel-text text-[13px] text-green-400 animate-pulse" style={{ textShadow: '0 0 6px #4ade80, 0 2px 0 #000' }}>
              scanning {SCAN_SOURCES[Math.min(scanIndex, SCAN_SOURCES.length - 1)]}...
            </p>
            <div className="flex gap-2">
              {SCAN_SOURCES.map((_, i) => (
                <div key={i} className="w-2 h-2" style={{ background: i < scanIndex ? '#4ade80' : '#1a1a1a' }} />
              ))}
            </div>
          </div>
        )}

        {screen === 'headlines' && (
          <div className="flex flex-col gap-3 w-full">
            <div className="flex flex-col gap-2 overflow-y-auto" style={{ maxHeight: '55vh' }}>
              {headlines.map((h, i) => (
                <button
                  key={i}
                  onClick={() => { setSelectedHeadline(`${h.title}. ${h.description}`); setScreen('configure') }}
                  className="pixel-card p-3 text-left w-full"
                >
                  <span className="pixel-text text-[11px] block mb-1" style={{ color: '#6a5a30' }}>
                    {h.source}
                  </span>
                  <span className="pixel-text text-[12px] leading-relaxed block" style={{ color: '#d4c080' }}>
                    {h.title}
                  </span>
                </button>
              ))}
            </div>
            <BackButton onClick={() => setScreen('source')} />
          </div>
        )}

        {screen === 'upload' && (
          <div className="flex flex-col items-center gap-5 mt-4 w-full">
            <label className="pixel-menu-btn cursor-pointer text-center block w-full">
              {uploadedFile ? uploadedFile.name : 'CHOOSE FILE'}
              <input type="file" accept=".pdf,.csv,.txt" className="hidden" onChange={e => {
                const f = e.target.files?.[0]
                if (f) { setUploadedFile(f); setSelectedHeadline(f.name); setScreen('configure') }
              }} />
            </label>
            <BackButton onClick={() => setScreen('source')} />
          </div>
        )}

        {screen === 'configure' && (
          <div className="flex flex-col gap-6 w-full mt-2">
            <div className="flex flex-col gap-3">
              <p className="pixel-text text-[12px] text-center" style={{ color: '#e8e8e8', textShadow: '0 2px 0 #000' }}>
                CITY MEMORY
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setMemory('fresh')}
                  className="pixel-menu-btn flex-1 text-[11px]"
                  style={memory === 'fresh' ? { color: '#93c5fd' } : {}}
                >
                  FRESH CITY
                </button>
                <button
                  onClick={() => setMemory('living')}
                  className="pixel-menu-btn flex-1 text-[11px]"
                  style={memory === 'living' ? { color: '#d8b4fe' } : {}}
                >
                  LIVING CITY
                </button>
              </div>
              <p className="pixel-text text-[9px] text-center" style={{ color: '#4a4030' }}>
                {memory === 'fresh' ? 'AGENTS START WITH NO MEMORIES' : 'AGENTS REMEMBER PAST SIMULATIONS'}
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <p className="pixel-text text-[12px] text-center" style={{ color: '#e8e8e8', textShadow: '0 2px 0 #000' }}>
                DURATION -{' '}
                <span style={{ color: '#f5d76e' }}>{duration} MONTH{duration > 1 ? 'S' : ''}</span>
              </p>
              <input
                type="range"
                min={1}
                max={12}
                value={duration}
                onChange={e => setDuration(Number(e.target.value))}
                className="w-full"
                style={{ accentColor: '#f5d76e' }}
              />
              <div className="flex justify-between">
                <span className="pixel-text text-[9px]" style={{ color: '#3a3020' }}>1 MO</span>
                <span className="pixel-text text-[9px]" style={{ color: '#3a3020' }}>12 MO</span>
              </div>
            </div>

            <MenuButton onClick={async () => {
              sessionStorage.setItem('sim_headline', selectedHeadline ?? '')
              sessionStorage.setItem('sim_months', String(duration))
              if (uploadedFile) {
                const form = new FormData()
                form.append('file', uploadedFile)
                form.append('months', String(duration))
                form.append('use_memory', String(memory === 'living'))
                await fetch('http://localhost:8000/simulate/upload', { method: 'POST', body: form }).catch(() => {})
              } else {
                await fetch('http://localhost:8000/simulate', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ policy_text: selectedHeadline ?? '', months: duration, use_memory: memory === 'living' }),
                }).catch(() => {})
              }
              router.push('/simulation')
            }}>START SIMULATION</MenuButton>
            <BackButton onClick={() => setScreen('headlines')} />
          </div>
        )}
      </div>
    </div>
  )
}

function MenuButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className="pixel-menu-btn w-full">
      {children}
    </button>
  )
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="pixel-back-btn">
      &lt; BACK
    </button>
  )
}
