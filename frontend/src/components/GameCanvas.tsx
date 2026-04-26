'use client'

import { useEffect, useRef } from 'react'
import { bridge, sendToServer } from '@/lib/eventBridge'

const NPC_CONFIGS = [
  { personRow: 11 },
  { personRow: 12 },
  { personRow: 13 },
  { personRow: 14 },
  { personRow: 12 },
  { personRow: 13 },
  { personRow: 11 },
]

const TILESET_COLS = 24
const PERSON_COL = 19

const ROAD_TILES = new Set([
  264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274,
  288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298,
  312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322,
  336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346,
])

const MOOD_INT: Record<string, number> = {
  angry: 0xe03030, anxious: 0xd4943a, frustrated: 0xe07050,
  hopeful: 0x6aaa50, optimistic: 0x6aaa50, neutral: 0xa09878,
}
const MOOD_STR: Record<string, string> = {
  angry: '#e03030', anxious: '#d4943a', frustrated: '#e07050',
  hopeful: '#6aaa50', optimistic: '#6aaa50', neutral: '#a09878',
}

const HOP_RADIUS = 48
const NPC_SPEED_PX = 14
const CONVO_TRIGGER_PX = 14
const CONVO_COOLDOWN_MS = 25_000

function frameOf(row: number, col: number) {
  return row * TILESET_COLS + col
}

interface Opinion {
  npcIdx: number
  text: string
  name: string
  role: string
  mood: string
}

export default function GameCanvas() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    let game: InstanceType<typeof import('phaser')['Game']>
    let agentSpeakCleanup: (() => void) | null = null

    async function init() {
      const Phaser = await import('phaser')

      class CityScene extends Phaser.Scene {
        private npcs: Array<{
          sprite: Phaser.GameObjects.Sprite
          npcIndex: number
          destination: { x: number; y: number }
          currentTween: Phaser.Tweens.Tween | null
          bubble: Phaser.GameObjects.Container | null
          inConversation: boolean
          lastTalkedAt: number
        }> = []
        private roadWaypoints: Array<{ x: number; y: number }> = []
        private agentNpcMap = new Map<string, number>()
        private npcCursor = 0
        private opinionPool: Opinion[] = []
        private speedMult = 1
        private bubbleQueue: Array<{ npcIdx: number; text: string; name: string; mood: string }> = []
        private bubbleProcessing = false
        private npcAgentMap = new Map<number, string>()
        private conversationPending = false

        constructor() {
          super({ key: 'CityScene' })
        }

        preload() {
          this.load.tilemapTiledJSON('map', '/assets/city.json')
          this.load.image('tileset', '/assets/tilemap.png')
          this.load.spritesheet('chars', '/assets/tilemap_packed.png', {
            frameWidth: 8,
            frameHeight: 8,
          })
        }

        create() {
          const map = this.make.tilemap({ key: 'map' })
          const tiles = map.addTilesetImage('city-tileset', 'tileset', 8, 8, 0, 1)
          if (!tiles) return

          map.createLayer('Terrain', tiles, 0, 0)?.setDepth(0)
          map.createLayer('Vehicles', tiles, 0, 0)?.setDepth(1)
          map.createLayer('Objects', tiles, 0, 0)?.setDepth(1000)

          const terrainLayer = map.getLayer('Terrain')?.tilemapLayer
          if (terrainLayer) {
            for (let ty = 0; ty < map.height; ty++) {
              for (let tx = 0; tx < map.width; tx++) {
                const tile = terrainLayer.getTileAt(tx, ty)
                if (tile && ROAD_TILES.has(tile.index)) {
                  this.roadWaypoints.push({ x: tx * 8 + 4, y: ty * 8 + 4 })
                }
              }
            }
          }

          NPC_CONFIGS.forEach((cfg, i) => {
            if (this.anims.exists(`walk_${i}`)) return
            this.anims.create({
              key: `walk_${i}`,
              frames: [
                { key: 'chars', frame: frameOf(cfg.personRow, PERSON_COL) },
                { key: 'chars', frame: frameOf(cfg.personRow, PERSON_COL + 1) },
                { key: 'chars', frame: frameOf(cfg.personRow, PERSON_COL + 2) },
                { key: 'chars', frame: frameOf(cfg.personRow, PERSON_COL + 1) },
              ],
              frameRate: 4,
              repeat: -1,
            })
          })

          const cam = this.cameras.main
          cam.setBackgroundColor('#1a1a2e')
          const zoom = Math.max(
            this.scale.width / map.widthInPixels,
            this.scale.height / map.heightInPixels
          )
          cam.setZoom(zoom)
          cam.setBounds(0, 0, map.widthInPixels, map.heightInPixels)
          cam.centerOn(map.widthInPixels / 2, map.heightInPixels / 2)

          this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
            if (!pointer.isDown) return
            cam.scrollX -= pointer.velocity.x / 4
            cam.scrollY -= pointer.velocity.y / 4
          })

          const waypoints = this.roadWaypoints.length > 0
            ? this.roadWaypoints
            : [{ x: 44, y: 44 }, { x: 84, y: 44 }, { x: 44, y: 84 }, { x: 84, y: 84 }]

          this.spawnNPCs(waypoints)

          const onAgentSpeak = (data: { agent_id: string; name: string; role: string; text: string; mood: string }) => {
            if (!this.agentNpcMap.has(data.agent_id)) {
              this.agentNpcMap.set(data.agent_id, this.npcCursor % NPC_CONFIGS.length)
              this.npcCursor++
            }
            const idx = this.agentNpcMap.get(data.agent_id)!
            const snippet = data.text.length > 100 ? data.text.slice(0, 97) + '...' : data.text
            const entry: Opinion = { npcIdx: idx, text: snippet, name: data.name, role: data.role, mood: data.mood }
            const existing = this.opinionPool.findIndex(o => o.npcIdx === idx)
            if (existing >= 0) this.opinionPool[existing] = entry
            else this.opinionPool.push(entry)
            this.npcAgentMap.set(idx, data.agent_id)

            this.enqueueBubble(idx, snippet, data.name, data.mood)
          }

          const onSpeedChange = (s: number) => { this.speedMult = s }

          const onSimEnd = () => {
            this.time.removeAllEvents()
            this.tweens.killAll()
            this.bubbleQueue = []
            this.bubbleProcessing = false
            this.conversationPending = false
            this.npcs.forEach(npc => {
              npc.inConversation = false
              npc.currentTween?.stop()
              npc.currentTween = null
              if (npc.bubble) { npc.bubble.destroy(); npc.bubble = null }
            })
          }

          bridge.on('agent_speak', onAgentSpeak)
          bridge.on('speed_change', onSpeedChange)
          bridge.on('simulation_end', onSimEnd)
          agentSpeakCleanup = () => {
            bridge.off('agent_speak', onAgentSpeak)
            bridge.off('speed_change', onSpeedChange)
            bridge.off('simulation_end', onSimEnd)
          }
        }

        private enqueueBubble(npcIdx: number, text: string, name: string, mood: string) {
          const existing = this.bubbleQueue.findIndex(b => b.npcIdx === npcIdx)
          if (existing >= 0) this.bubbleQueue[existing] = { npcIdx, text, name, mood }
          else this.bubbleQueue.push({ npcIdx, text, name, mood })
          if (!this.bubbleProcessing) this.drainBubbleQueue()
        }

        private drainBubbleQueue() {
          if (this.bubbleQueue.length === 0) {
            this.bubbleProcessing = false
            return
          }
          this.bubbleProcessing = true
          const next = this.bubbleQueue.shift()!
          const npc = this.npcs[next.npcIdx]
          if (!npc || npc.inConversation) {
            this.time.delayedCall(600, () => this.drainBubbleQueue())
            return
          }
          this.buildBubble(next.npcIdx, next.text, next.name, next.mood, 5500, 500)
          this.time.delayedCall(4000, () => this.drainBubbleQueue())
        }

        private randomWaypoint(waypoints: Array<{ x: number; y: number }>) {
          return waypoints[Math.floor(Math.random() * waypoints.length)]
        }

        private nextHopToward(
          from: { x: number; y: number },
          dest: { x: number; y: number },
          waypoints: Array<{ x: number; y: number }>
        ) {
          const candidates = waypoints.filter(wp => {
            const dx = wp.x - from.x
            const dy = wp.y - from.y
            return Math.sqrt(dx * dx + dy * dy) <= HOP_RADIUS
          })
          if (candidates.length === 0) return this.randomWaypoint(waypoints)
          candidates.sort((a, b) =>
            Math.hypot(a.x - dest.x, a.y - dest.y) - Math.hypot(b.x - dest.x, b.y - dest.y)
          )
          const top = candidates.slice(0, Math.max(1, Math.floor(candidates.length * 0.3)))
          return top[Math.floor(Math.random() * top.length)]
        }

        private spawnNPCs(waypoints: Array<{ x: number; y: number }>) {
          NPC_CONFIGS.forEach((cfg, i) => {
            const start = this.randomWaypoint(waypoints)
            const sprite = this.add.sprite(start.x, start.y, 'chars', frameOf(cfg.personRow, PERSON_COL))
            sprite.setDepth(start.y + 10)
            this.npcs.push({
              sprite,
              npcIndex: i,
              destination: this.randomWaypoint(waypoints),
              currentTween: null,
              bubble: null,
              inConversation: false,
              lastTalkedAt: 0,
            })
            this.time.delayedCall(i * 600 + 300, () => this.step(i, waypoints))
          })
        }

        private step(npcIndex: number, waypoints: Array<{ x: number; y: number }>) {
          const npc = this.npcs[npcIndex]
          if (!npc || npc.inConversation) return

          const from = { x: npc.sprite.x, y: npc.sprite.y }
          if (Math.hypot(npc.destination.x - from.x, npc.destination.y - from.y) < HOP_RADIUS) {
            npc.destination = this.randomWaypoint(waypoints)
          }

          const target = this.nextHopToward(from, npc.destination, waypoints)
          npc.sprite.play(`walk_${npcIndex}`)
          npc.sprite.setFlipX(target.x < from.x)

          const dist = Math.hypot(target.x - from.x, target.y - from.y)
          npc.currentTween = this.tweens.add({
            targets: npc.sprite,
            x: target.x,
            y: target.y,
            duration: Math.max((dist / (NPC_SPEED_PX * this.speedMult)) * 1000, 200),
            ease: 'Linear',
            onUpdate: () => npc.sprite.setDepth(npc.sprite.y + 10),
            onComplete: () => {
              npc.sprite.stop()
              npc.sprite.setFrame(frameOf(NPC_CONFIGS[npcIndex].personRow, PERSON_COL))
              this.time.delayedCall(
                Phaser.Math.Between(300, 1200),
                () => this.step(npcIndex, waypoints)
              )
            },
          })
        }

        private startConversation(aIdx: number, bIdx: number, waypoints: Array<{ x: number; y: number }>) {
          const a = this.npcs[aIdx]
          const b = this.npcs[bIdx]
          if (!a || !b) return

          const aOp = this.opinionPool.find(o => o.npcIdx === aIdx)
          const bOp = this.opinionPool.find(o => o.npcIdx === bIdx)
          const agentIdA = this.npcAgentMap.get(aIdx)
          const agentIdB = this.npcAgentMap.get(bIdx)

          if (!aOp || !bOp || !agentIdA || !agentIdB || this.conversationPending) return

          this.conversationPending = true
          a.inConversation = true
          b.inConversation = true
          a.currentTween?.stop()
          b.currentTween?.stop()
          a.sprite.stop()
          b.sprite.stop()
          a.sprite.setFrame(frameOf(NPC_CONFIGS[aIdx].personRow, PERSON_COL))
          b.sprite.setFrame(frameOf(NPC_CONFIGS[bIdx].personRow, PERSON_COL))
          a.sprite.setFlipX(b.sprite.x < a.sprite.x)
          b.sprite.setFlipX(a.sprite.x < b.sprite.x)

          const endConvo = () => {
            const now = Date.now()
            this.conversationPending = false
            a.inConversation = false
            b.inConversation = false
            a.lastTalkedAt = now
            b.lastTalkedAt = now
            this.step(aIdx, waypoints)
            this.step(bIdx, waypoints)
          }

          const showExchange = (aLine: string, bLine: string, aReply?: string, bReply?: string) => {
            this.buildBubble(aIdx, aLine, aOp.name, aOp.mood, 3200, 300)
            this.time.delayedCall(3600, () => {
              this.buildBubble(bIdx, bLine, bOp.name, bOp.mood, 3200, 300)
            })
            if (aReply) {
              this.time.delayedCall(7200, () => {
                this.buildBubble(aIdx, aReply, aOp.name, aOp.mood, 3200, 300)
              })
            }
            if (bReply) {
              this.time.delayedCall(10800, () => {
                this.buildBubble(bIdx, bReply, bOp.name, bOp.mood, 3200, 300)
              })
            }
            this.time.delayedCall(aReply || bReply ? 14400 : 7200, endConvo)
          }

          let responded = false
          const onResponse = (data: { a_line: string; b_line: string; a_reply?: string; b_reply?: string }) => {
            if (responded) return
            responded = true
            if (data.a_line && data.b_line) showExchange(data.a_line, data.b_line, data.a_reply, data.b_reply)
            else showExchange(aOp.text, bOp.text)
          }
          bridge.once('converse_response', onResponse)

          // Fallback: if backend doesn't respond in 3s, show real opinions
          this.time.delayedCall(3000, () => {
            if (!responded) {
              responded = true
              bridge.off('converse_response', onResponse)
              showExchange(aOp.text, bOp.text)
            }
          })

          sendToServer('converse_request', { agent_id_a: agentIdA, agent_id_b: agentIdB })
        }

        private buildBubble(
          npcIndex: number, text: string, name: string | undefined, mood: string | undefined,
          displayMs: number, fadeMs: number,
        ) {
          const npc = this.npcs[npcIndex]
          if (!npc) return

          if (npc.bubble) { npc.bubble.destroy(); npc.bubble = null }

          const zoom = this.cameras.main.zoom
          const accentStr = mood ? (MOOD_STR[mood] ?? '#a09878') : '#a09878'
          const accentInt = mood ? (MOOD_INT[mood] ?? 0xa09878) : 0xa09878

          const DISPLAY_PX = 7
          const HEADER_PX = 6
          const WRAP_PX = 260
          const pad = 8

          let headerText: Phaser.GameObjects.Text | null = null
          if (name) {
            headerText = this.add.text(0, 0, name, {
              fontFamily: '"Press Start 2P"',
              fontSize: `${HEADER_PX}px`,
              color: accentStr,
            })
          }

          const snippet = text.length > 100 ? text.slice(0, 97) + '...' : text
          const bodyY = headerText ? headerText.height + 6 : 0
          const bodyText = this.add.text(0, bodyY, snippet, {
            fontFamily: '"Press Start 2P"',
            fontSize: `${DISPLAY_PX}px`,
            color: '#ffffff',
            wordWrap: { width: WRAP_PX },
          })

          const contentW = Math.max(headerText?.width ?? 0, bodyText.width)
          const contentH = bodyY + bodyText.height
          const totalW = contentW + pad * 2
          const totalH = contentH + pad * 2

          if (headerText) headerText.setPosition(pad - totalW / 2, -totalH + pad)
          bodyText.setPosition(pad - totalW / 2, -totalH + pad + bodyY)

          const bg = this.add.graphics()
          bg.fillStyle(0x0d0806, 0.96)
          bg.fillRect(-totalW / 2, -totalH, totalW, totalH)
          bg.lineStyle(2, accentInt, 1)
          bg.strokeRect(-totalW / 2, -totalH, totalW, totalH)

          const items: Phaser.GameObjects.GameObject[] = headerText
            ? [bg, headerText, bodyText]
            : [bg, bodyText]

          const bubble = this.add.container(npc.sprite.x, npc.sprite.y - 10, items)
          bubble.setScale(1 / zoom)
          bubble.setDepth(npc.sprite.y + 1000)
          npc.bubble = bubble

          this.tweens.add({
            targets: bubble,
            alpha: 0,
            delay: displayMs,
            duration: fadeMs,
            onComplete: () => {
              bubble.destroy()
              if (npc.bubble === bubble) npc.bubble = null
            },
          })
        }

        update() {
          const now = Date.now()

          this.npcs.forEach(npc => {
            if (npc.bubble) {
              npc.bubble.x = npc.sprite.x
              npc.bubble.y = npc.sprite.y - 10
              npc.bubble.setDepth(npc.sprite.y + 1000)
            }
          })

          for (let i = 0; i < this.npcs.length; i++) {
            const a = this.npcs[i]
            if (a.inConversation || now - a.lastTalkedAt < CONVO_COOLDOWN_MS) continue
            for (let j = i + 1; j < this.npcs.length; j++) {
              const b = this.npcs[j]
              if (b.inConversation || now - b.lastTalkedAt < CONVO_COOLDOWN_MS) continue
              const dist = Math.hypot(a.sprite.x - b.sprite.x, a.sprite.y - b.sprite.y)
              if (dist <= CONVO_TRIGGER_PX) {
                this.startConversation(i, j, this.roadWaypoints.length > 0 ? this.roadWaypoints : [{ x: 44, y: 44 }])
                return
              }
            }
          }
        }
      }

      game = new Phaser.Game({
        type: Phaser.AUTO,
        parent: containerRef.current!,
        backgroundColor: '#5b87c0',
        scene: CityScene,
        pixelArt: true,
        roundPixels: true,
        scale: {
          mode: Phaser.Scale.RESIZE,
          autoCenter: Phaser.Scale.CENTER_BOTH,
        },
      })
    }

    init()

    return () => {
      agentSpeakCleanup?.()
      game?.destroy(true)
    }
  }, [])

  return <div ref={containerRef} className="absolute inset-0" />
}
