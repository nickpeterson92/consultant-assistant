import { useState, useEffect } from 'react'
import { ConversationPanel } from '@/components/ConversationPanel'
import { VisualizationPanel } from '@/components/VisualizationPanel'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { InterruptModal } from '@/components/InterruptModal'
import { ResizablePanels } from '@/components/ResizablePanels'
import { useSSE } from '@/hooks/useSSE'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useA2AClient } from '@/hooks/useA2AClient'
import { Toaster } from '@/components/ui/toaster'
import { ThreadProvider, useThread } from '@/contexts/ThreadContext'
import { ConversationProvider, useConversation } from '@/contexts/ConversationContext'
import { cn } from '@/lib/utils'

function AppContent() {
  const [isDarkMode, setIsDarkMode] = useState(true)
  const [isInterruptModalOpen, setIsInterruptModalOpen] = useState(false)
  const [currentPlan, setCurrentPlan] = useState<any[]>([])
  const [processedInterrupts, setProcessedInterrupts] = useState<Set<string>>(new Set())
  
  console.log('App component mounted')
  
  // Apply dark mode to document
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDarkMode])

  // SSE connection for real-time updates
  const { events, isConnected: sseConnected } = useSSE('/a2a/stream')
  
  // WebSocket for interrupts
  const { 
    isConnected: wsConnected, 
    sendInterrupt 
  } = useWebSocket(`ws://${window.location.host}/ws`)
  
  // A2A client for API calls
  const { sendMessage } = useA2AClient()
  const { addMessage } = useConversation()
  const { updateThreadStatus } = useThread()

  // Handle interrupt SSE events
  useEffect(() => {
    // Process all interrupt events that haven't been processed yet
    const interruptEvents = events.filter(e => e.type === 'interrupt')
    
    interruptEvents.forEach(event => {
      // Create unique ID for this interrupt event
      const eventId = `${event.timestamp}_${event.data?.task_id || 'unknown'}`
      
      // Skip if already processed
      if (processedInterrupts.has(eventId)) {
        return
      }
      
      const data = event.data
      
      // Simple approach - just display the interrupt reason/message
      if (data && data.interrupt_reason) {
        // Add the message to conversation
        addMessage({
          role: 'assistant',
          content: data.interrupt_reason,
          status: 'sent'
        })
        
        // Update thread status
        updateThreadStatus('interrupted')
        
        // Mark as processed
        setProcessedInterrupts(prev => new Set([...prev, eventId]))
      }
    })
  }, [events, addMessage, processedInterrupts, updateThreadStatus])

  // Handle ESC key for interrupts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && currentPlan.length > 0) {
        setIsInterruptModalOpen(true)
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentPlan])

  const handleInterrupt = async (modifiedPlan: string) => {
    await sendInterrupt('user_escape', modifiedPlan)
    setIsInterruptModalOpen(false)
  }

  return (
    <div className={cn(
      "h-screen bg-background transition-colors duration-300",
      "flex flex-col overflow-hidden"
    )}>
      {/* Header */}
      <Header 
        isDarkMode={isDarkMode} 
        onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        sseConnected={sseConnected}
        wsConnected={wsConnected}
      />
      
      {/* Main Content */}
      <main className="flex-1 min-h-0">
        <ResizablePanels
          leftPanel={<ConversationPanel onSendMessage={sendMessage} />}
          rightPanel={
            <VisualizationPanel 
              events={events}
              onPlanUpdate={setCurrentPlan}
            />
          }
          defaultLeftWidth={70}
          minLeftWidth={400}
          minRightWidth={300}
        />
      </main>
      
      {/* Footer */}
      <Footer />
      
      {/* Interrupt Modal */}
      <InterruptModal 
        isOpen={isInterruptModalOpen}
        onClose={() => setIsInterruptModalOpen(false)}
        currentPlan={currentPlan}
        onSubmit={handleInterrupt}
      />
      
      {/* Toast Notifications */}
      <Toaster />
    </div>
  )
}

function App() {
  return (
    <ThreadProvider>
      <ConversationProvider>
        <AppContent />
      </ConversationProvider>
    </ThreadProvider>
  )
}

export default App