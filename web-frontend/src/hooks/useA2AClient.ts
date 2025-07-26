import { useState, useCallback, useRef } from 'react'
import { useToast } from '@/hooks/use-toast'
import { useConversation } from '@/contexts/ConversationContext'

export function useA2AClient() {
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()
  const { addMessage } = useConversation()
  
  // Use useRef to persist thread_id across renders
  // Only generate new thread_id on mount (when ref.current is null)
  const threadIdRef = useRef<string | null>(null)
  if (!threadIdRef.current) {
    threadIdRef.current = Math.random().toString(36).substring(2, 11)
  }
  const threadId = threadIdRef.current

  const sendMessage = useCallback(async (instruction: string) => {
    setIsLoading(true)

    try {
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
              thread_id: threadId,
              user_id: 'web-user'
            }
          },
          id: Math.random().toString(36).substring(2, 11)
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
          const interrupt_reason = data.result.metadata?.interrupt_reason || 'Agent requested clarification'
          const interrupt_type = data.result.metadata?.interrupt_type || 'unknown'
          
          addMessage({
            role: 'assistant',
            content: `🔄 **Execution Paused** (${interrupt_type})\n\n${interrupt_reason}`,
            status: 'sent'
          })
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
  }, [addMessage, toast])

  return {
    sendMessage,
    isLoading,
    threadId
  }
}