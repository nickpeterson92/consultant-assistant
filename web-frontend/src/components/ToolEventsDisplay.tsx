import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Wrench, CheckCircle, XCircle, Search, MessageCircle, 
  Lightbulb, ChevronDown, ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface ToolEvent {
  id: string
  timestamp: Date
  type: 'agent_call_started' | 'agent_call_completed' | 'agent_call_failed' | 
        'tool_selected' | 'direct_response' | 'web_search_started' | 
        'web_search_completed' | 'human_input_requested' | 'human_input_received'
  agent_name: string
  task_id: string
  instruction: string
  additional_data: {
    tool_type?: string
    tool_args?: Record<string, any>
    result_preview?: string
    error?: string
    response_type?: string
    original_query?: string
    result_count?: number
    response_preview?: string
  }
}

interface ToolEventsDisplayProps {
  events: ToolEvent[]
  maxEvents?: number
}

export function ToolEventsDisplay({ events, maxEvents = 100 }: ToolEventsDisplayProps) {
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set())
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events, autoScroll])

  const getEventIcon = (type: string) => {
    const icons: Record<string, JSX.Element> = {
      'agent_call_started': <Wrench className="w-4 h-4 text-muted-foreground" />,
      'agent_call_completed': <CheckCircle className="w-4 h-4 text-primary" />,
      'agent_call_failed': <XCircle className="w-4 h-4 text-destructive" />,
      'tool_selected': <Wrench className="w-4 h-4 text-primary/70" />,
      'direct_response': <Lightbulb className="w-4 h-4 text-primary" />,
      'web_search_started': <Search className="w-4 h-4 text-muted-foreground" />,
      'web_search_completed': <Search className="w-4 h-4 text-primary" />,
      'human_input_requested': <MessageCircle className="w-4 h-4 text-primary/70" />,
      'human_input_received': <MessageCircle className="w-4 h-4 text-primary" />
    }
    return icons[type] || <Wrench className="w-4 h-4 text-muted-foreground" />
  }

  const formatAgentName = (name: string) => {
    // Clean up agent names like "salesforce_salesforce_get" -> "salesforce → get"
    // or "salesforce_SalesforceGet" -> "salesforce → Get"
    
    // Handle camelCase tool names like "salesforce_SalesforceGet"
    if (name.includes('_')) {
      const parts = name.split('_')
      
      // Check if it's a tool name like "salesforce_SalesforceGet"
      if (parts.length === 2 && parts[1].startsWith(parts[0].charAt(0).toUpperCase() + parts[0].slice(1))) {
        // Extract the tool action from the camelCase name
        const toolName = parts[1].replace(parts[0].charAt(0).toUpperCase() + parts[0].slice(1), '')
        return `${parts[0]} → ${toolName}`
      }
      
      // Handle underscore-separated names like "salesforce_salesforce_get"
      if (parts.length >= 3 && parts[0] === parts[1]) {
        return `${parts[0]} → ${parts.slice(2).join('_')}`
      }
    }
    
    // If it's just the agent name without specific tool
    if (name === 'salesforce_agent' || name === 'jira_agent' || name === 'servicenow_agent') {
      return name.replace('_agent', '')
    }
    
    // Handle orchestrator direct responses
    if (name === 'orchestrator') {
      return 'orchestrator'
    }
    
    return name
  }

  const toggleEventExpansion = (eventId: string) => {
    setExpandedEvents(prev => {
      const newSet = new Set(prev)
      if (newSet.has(eventId)) {
        newSet.delete(eventId)
      } else {
        newSet.add(eventId)
      }
      return newSet
    })
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <h3 className="text-lg font-medium">Tool Execution Log</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setAutoScroll(!autoScroll)}
          className={cn(
            "transition-colors",
            autoScroll && "text-primary hover:text-primary/80"
          )}
        >
          Auto-scroll {autoScroll ? 'ON' : 'OFF'}
        </Button>
      </div>

      {/* Events list */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-2 min-h-0 scrollbar-thin"
        style={{ 
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgba(155, 155, 155, 0.5) transparent',
          maxHeight: 'calc(100% - 5rem)' // Ensure it doesn't overflow the parent
        }}
        onScroll={(e) => {
          const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
          setAutoScroll(scrollTop + clientHeight >= scrollHeight - 10)
        }}
      >
        <AnimatePresence initial={false}>
          {events.slice(-maxEvents).map((event) => {
            const isExpanded = expandedEvents.has(event.id)
            
            return (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="bg-card/50 border border-border/50 p-3 rounded-lg hover:border-primary/30 transition-colors"
              >
                <div 
                  className="flex items-start gap-3 cursor-pointer"
                  onClick={() => toggleEventExpansion(event.id)}
                >
                  {/* Icon */}
                  <div className="flex-shrink-0 mt-0.5">
                    {getEventIcon(event.type)}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                      <span className="text-sm font-medium">
                        {formatAgentName(event.agent_name)}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground truncate">
                      {event.type === 'direct_response' 
                        ? (event.additional_data?.response_preview || 'Direct response')
                        : event.instruction
                      }
                    </p>
                  </div>

                  {/* Expand/Collapse */}
                  <div className="flex-shrink-0">
                    {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3 pl-10 space-y-2"
                  >
                    {event.additional_data.tool_args && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Arguments:</p>
                        <pre className="text-xs bg-black/20 p-2 rounded overflow-x-auto">
                          {JSON.stringify(event.additional_data.tool_args, null, 2)}
                        </pre>
                      </div>
                    )}
                    
                    {event.additional_data.result_preview && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Result:</p>
                        <p className="text-xs text-primary">
                          {event.additional_data.result_preview}
                        </p>
                      </div>
                    )}
                    
                    {event.additional_data.error && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Error:</p>
                        <p className="text-xs text-destructive">
                          {event.additional_data.error}
                        </p>
                      </div>
                    )}
                  </motion.div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>

        {events.length === 0 && (
          <div className="flex items-center justify-center h-32">
            <p className="text-muted-foreground text-sm">
              No tool events yet
            </p>
          </div>
        )}
      </div>
    </div>
  )
}