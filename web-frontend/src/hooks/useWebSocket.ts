import { useEffect, useState, useRef, useCallback } from 'react'
import { useToast } from '@/hooks/use-toast'
import { useThread } from '@/contexts/ThreadContext'

export function useWebSocket(url: string) {
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const { toast } = useToast()
  const { thread } = useThread()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      // Include thread_id in URL
      const urlWithThread = `${url}?thread_id=${thread.threadId}`
      const ws = new WebSocket(urlWithThread)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        console.log('WebSocket connected for thread:', thread.threadId)
        
        // Send thread context on connection
        ws.send(JSON.stringify({
          type: 'thread_context',
          payload: {
            thread_id: thread.threadId,
            user_id: thread.metadata.userId,
            session_id: thread.metadata.sessionId
          }
        }))
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // Filter messages by thread_id if present
          if (data.thread_id && data.thread_id !== thread.threadId) {
            console.log(`WebSocket message ignored (wrong thread). Expected: ${thread.threadId}, Got: ${data.thread_id}`)
            return
          }
          
          if (data.type === 'interrupt_ack') {
            if (data.payload?.success) {
              toast({
                title: "Interrupt Acknowledged",
                description: "Plan modification in progress",
              })
            }
          }
        } catch (error) {
          console.error('Failed to parse WebSocket data:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setIsConnected(false)
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null

        // Reconnect after 5 seconds
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, 5000)
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      setIsConnected(false)
    }
  }, [url, toast, thread.threadId, thread.metadata])

  const sendInterrupt = useCallback(async (reason: string = 'user_escape', modifiedPlan?: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      toast({
        title: "Not Connected",
        description: "WebSocket is not connected",
        variant: "destructive"
      })
      return false
    }

    const message = {
      type: "interrupt",
      payload: {
        thread_id: thread.threadId,
        user_id: thread.metadata.userId,
        session_id: thread.metadata.sessionId,
        reason,
        modified_plan: modifiedPlan
      },
      id: Math.random().toString(36).substr(2, 9)
    }

    try {
      wsRef.current.send(JSON.stringify(message))
      return true
    } catch (error) {
      console.error('Failed to send interrupt:', error)
      toast({
        title: "Failed to Interrupt",
        description: "Could not send interrupt command",
        variant: "destructive"
      })
      return false
    }
  }, [toast, thread.threadId, thread.metadata])

  useEffect(() => {
    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  return {
    isConnected,
    sendInterrupt,
    reconnect: connect,
    threadId: thread.threadId
  }
}