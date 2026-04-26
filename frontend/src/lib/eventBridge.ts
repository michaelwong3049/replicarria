import { io, Socket } from 'socket.io-client'
import { EventEmitter } from 'events'

export const bridge = new EventEmitter()
bridge.setMaxListeners(20)

let socket: Socket | null = null

export function connectSocket() {
  if (socket?.connected) return
  socket = io('http://localhost:8000', { transports: ['websocket'] })
  socket.onAny((type, data) => bridge.emit(type, data))
}

export function disconnectSocket() {
  socket?.disconnect()
  socket = null
}

export function sendToServer(event: string, data: unknown) {
  socket?.emit(event, data)
}
