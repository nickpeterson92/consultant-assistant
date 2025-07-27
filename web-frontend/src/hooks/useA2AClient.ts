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
          const metadata = data.result.metadata || {}
          const interrupt_reason = metadata.interrupt_reason || 'Agent requested clarification'
          const interrupt_type = metadata.interrupt_type || 'unknown'
          
          // Check if we have a structured interrupt payload (like from human_input tool)
          if (metadata.interrupt_payload || metadata.options) {
            const question = metadata.question || metadata.interrupt_reason || interrupt_reason
            const options = metadata.options || metadata.interrupt_payload?.options
            const context = metadata.context || metadata.interrupt_payload?.context || {}
            
            let content = `🔄 **${interrupt_type === 'selection' ? 'Please Select an Option' : 'Input Required'}**\n\n${question}`
            
            // Add options if this is a selection type
            if (options && options.length > 0) {
              content += '\n\n**Options:**'
              options.forEach((option: string, index: number) => {
                content += `\n${index + 1}. ${option}`
              })
              content += '\n\nPlease respond with your selection.'
            }
            
            // Add context if available
            if (context.recent_messages || context.completed_steps) {
              content += '\n\n---'
              if (context.completed_steps && context.completed_steps.length > 0) {
                content += '\n**Recent Steps:**'
                context.completed_steps.forEach((step: string) => {
                  content += `\n• ${step}`
                })
              }
            }
            
            addMessage({
              role: 'assistant',
              content,
              status: 'sent'
            })
          } else {
            // Fallback to simple interrupt message
            addMessage({
              role: 'assistant',
              content: `🔄 **Execution Paused** (${interrupt_type})\n\n${interrupt_reason}`,
              status: 'sent'
            })
          }
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