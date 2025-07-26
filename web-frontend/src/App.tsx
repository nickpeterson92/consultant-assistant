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
import { cn } from '@/lib/utils'

function App() {
  const [isDarkMode, setIsDarkMode] = useState(true)
  const [isInterruptModalOpen, setIsInterruptModalOpen] = useState(false)
  const [currentPlan, setCurrentPlan] = useState<any[]>([])
  
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
          defaultLeftWidth={50}
          minLeftWidth={320}
          minRightWidth={320}
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

export default App