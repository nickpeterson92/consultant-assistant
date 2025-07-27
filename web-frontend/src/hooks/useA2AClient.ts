import { useState, useCallback } from 'react'
import { useToast } from '@/hooks/use-toast'
import { useConversation } from '@/contexts/ConversationContext'
import { useThread } from '@/contexts/ThreadContext'

export function useA2AClient() {
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()
  const { addMessage } = useConversation()
  const { thread, updateLastActivity, updateThreadStatus } = useThread()
  
  // Generate unique request ID
  const generateRequestId = () => {
    return `req-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 9)}`
  }

  const sendMessage = useCallback(async (instruction: string) => {
    setIsLoading(true)
    updateLastActivity()

    try {
      const requestId = generateRequestId()
      const response = await fetch('/a2a', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'process_task',
          params: {
            task_id: Math.random().toString(36).substring(2, 11),
            instruction,
            context: {
              thread_id: thread.threadId,
              user_id: thread.metadata.userId,
              session_id: thread.metadata.sessionId,
              request_id: requestId,
              timestamp: new Date().toISOString()
            }
          },
          id: requestId
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      if (data.error) {
        throw new Error(data.error.message || 'Unknown error')
      }

      // Add assistant response
      if (data.result) {
        // Check for interrupted status first
        if (data.result.status === 'interrupted') {
          updateThreadStatus('interrupted')
          // Don't add message here - let SSE handler do it to avoid duplication
          // The interrupt message will be handled by the SSE event listener
        }
        // Check for artifacts (normal responses)
        else if (data.result.artifacts && data.result.artifacts.length > 0) {
          const artifact = data.result.artifacts[0]
          addMessage({
            role: 'assistant',
            content: artifact.content || 'Response received',
            status: 'sent'
          })
        } else if (data.result.response) {
          addMessage({
            role: 'assistant',
            content: data.result.response,
            status: 'sent'
          })
        } else if (data.result.metadata?.interrupt_value) {
          addMessage({
            role: 'assistant',
            content: data.result.metadata.interrupt_value,
            status: 'sent'
          })
        }
      }

      return data.result
    } catch (error) {
      console.error('A2A request failed:', error)
      toast({
        title: "Request Failed",
        description: error instanceof Error ? error.message : "Failed to process request",
        variant: "destructive"
      })
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [addMessage, toast, thread, updateLastActivity, updateThreadStatus])

  return {
    sendMessage,
    isLoading,
    threadId: thread.threadId
  }
}