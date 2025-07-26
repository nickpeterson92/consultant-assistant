import { useEffect, useState, useRef, useCallback } from 'react'
import { useToast } from '@/hooks/use-toast'
import { useThread } from '@/contexts/ThreadContext'

export function useSSE(url: string) {
  const [events, setEvents] = useState<any[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const { toast } = useToast()
  const { thread } = useThread()

  const connect = useCallback(() => {
    if (eventSourceRef.current?.readyState === EventSource.OPEN) {
      return
    }

    try {
      // Include thread_id in URL for server-side filtering
      const urlWithThread = `${url}?thread_id=${thread.threadId}`
      const eventSource = new EventSource(urlWithThread)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setIsConnected(true)
        toast({
          title: "Connected",
          description: "Real-time updates established",
        })
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          console.log('SSE Event received:', data)
          
          // Handle heartbeat
          if (data.event === 'heartbeat') {
            return
          }

          // Filter events by thread_id if present
          if (data.thread_id && data.thread_id !== thread.threadId) {
            console.log(`SSE Event ignored (wrong thread). Expected: ${thread.threadId}, Got: ${data.thread_id}`)
            return
          }

          // Also check context.thread_id for nested thread info
          if (data.context?.thread_id && data.context.thread_id !== thread.threadId) {
            console.log(`SSE Event ignored (wrong context thread). Expected: ${thread.threadId}, Got: ${data.context.thread_id}`)
            return
          }

          // Add event to list
          // Handle both formats: {event: "type", data: {...}} and {type: "type", data: {...}}
          const eventType = data.event || data.type
          const eventData = data.data || data
          
          setEvents(prev => [...prev, {
            type: eventType,
            data: eventData,
            timestamp: new Date().toISOString()
          }])
        } catch (error) {
          console.error('Failed to parse SSE data:', error, event.data)
        }
      }

      eventSource.onerror = (error) => {
        console.error('SSE error:', error)
        setIsConnected(false)
        eventSource.close()

        // Reconnect after 5 seconds
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, 5000)
      }
    } catch (error) {
      console.error('Failed to create EventSource:', error)
      setIsConnected(false)
    }
  }, [url, toast, thread.threadId])

  useEffect(() => {
    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  return {
    events,
    isConnected,
    reconnect: connect
  }
}