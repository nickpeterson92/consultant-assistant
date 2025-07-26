import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  CheckCircle2, Circle, Loader2, AlertCircle, PlayCircle, Clock,
  Wrench, CheckCircle, XCircle, Search, MessageCircle, 
  Lightbulb, ChevronDown, ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface PlanStep {
  task: string
  tool?: string
  status?: 'pending' | 'executing' | 'completed' | 'failed'
  result?: any
  error?: string
}

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

interface PlanAndToolsDisplayProps {
  plan: PlanStep[]
  currentStep: number
  status: 'idle' | 'created' | 'executing' | 'completed' | 'modified'
  toolEvents: ToolEvent[]
  maxEvents?: number
}

export function PlanAndToolsDisplay({ 
  plan, 
  currentStep, 
  status, 
  toolEvents,
  maxEvents = 100 
}: PlanAndToolsDisplayProps) {
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set())
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [toolEvents, autoScroll])

  const getStepIcon = (step: PlanStep, index: number) => {
    if (step.status === 'completed') {
      return <CheckCircle2 className="w-5 h-5 text-green-500" />
    } else if (step.status === 'failed') {
      return <AlertCircle className="w-5 h-5 text-destructive" />
    } else if (index === currentStep && status === 'executing') {
      return <Loader2 className="w-5 h-5 text-primary animate-spin" />
    } else if (index < currentStep) {
      return <CheckCircle2 className="w-5 h-5 text-green-500" />
    } else if (index === currentStep) {
      return <PlayCircle className="w-5 h-5 text-primary" />
    } else {
      return <Circle className="w-5 h-5 text-muted-foreground" />
    }
  }

  const getStepStatus = (step: PlanStep, index: number) => {
    if (step.status === 'completed') return 'completed'
    if (step.status === 'failed') return 'failed'
    if (index === currentStep && status === 'executing') return 'executing'
    if (index < currentStep) return 'completed'
    if (index === currentStep) return 'current'
    return 'pending'
  }

  const getEventIcon = (type: string) => {
    const icons: Record<string, JSX.Element> = {
      'agent_call_started': <Wrench className="w-3 h-3" />,
      'agent_call_completed': <CheckCircle className="w-3 h-3 text-green-500" />,
      'agent_call_failed': <XCircle className="w-3 h-3 text-red-500" />,
      'tool_selected': <Wrench className="w-3 h-3 text-blue-500" />,
      'direct_response': <Lightbulb className="w-3 h-3 text-yellow-500" />,
      'web_search_started': <Search className="w-3 h-3 text-purple-500" />,
      'web_search_completed': <Search className="w-3 h-3 text-green-500" />,
      'human_input_requested': <MessageCircle className="w-3 h-3 text-orange-500" />,
      'human_input_received': <MessageCircle className="w-3 h-3 text-green-500" />
    }
    return icons[type] || <Wrench className="w-3 h-3" />
  }

  const formatAgentName = (name: string) => {
    const parts = name.split('_')
    if (parts.length >= 3 && parts[0] === parts[1]) {
      return `${parts[0]} → ${parts.slice(2).join('_')}`
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
    <div className="h-full flex flex-col gap-4">
      {/* Plan Section - 40% */}
      <div className="flex-shrink-0 h-[40%] overflow-hidden">
        <div className="h-full overflow-y-auto scrollbar-thin space-y-2 pr-2">
          {/* Status Header */}
          <div className="mb-4 p-3 rounded-lg glass sticky top-0 z-10 backdrop-blur">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Execution Plan</span>
              <span className={cn(
                "text-xs px-2 py-1 rounded-full",
                status === 'executing' && "bg-primary/20 text-primary",
                status === 'completed' && "bg-green-500/20 text-green-500",
                status === 'modified' && "bg-yellow-500/20 text-yellow-500",
                status === 'created' && "bg-blue-500/20 text-blue-500"
              )}>
                {status === 'executing' && 'Executing...'}
                {status === 'completed' && 'Completed'}
                {status === 'modified' && 'Modified'}
                {status === 'created' && 'Ready'}
              </span>
            </div>
            {status === 'executing' && plan.length > 0 && (
              <div className="mt-2">
                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                  <span>Progress</span>
                  <span>{currentStep + 1} / {plan.length}</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <motion.div
                    className="bg-primary h-2 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${((currentStep + 1) / plan.length) * 100}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Plan Steps */}
          {plan.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-2">
                <Clock className="w-12 h-12 mx-auto text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No plan created yet</p>
              </div>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {plan.map((step, index) => {
                const stepStatus = getStepStatus(step, index)
                const taskText = typeof step === 'string' ? step : (step.task || 'Unknown task')
                
                return (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className={cn(
                      "relative flex gap-2 p-2 rounded-lg transition-all text-sm",
                      stepStatus === 'executing' && "glass ring-1 ring-primary/50",
                      stepStatus === 'completed' && "bg-green-500/5",
                      stepStatus === 'failed' && "bg-destructive/5",
                      stepStatus === 'current' && "glass",
                      stepStatus === 'pending' && "opacity-60"
                    )}
                  >
                    <div className="flex-shrink-0">
                      {getStepIcon(step, index)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">{taskText}</p>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      Step {index + 1}
                    </span>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          )}
        </div>
      </div>

      {/* Divider */}
      <div className="h-px bg-border" />

      {/* Tool Events Section - 60% */}
      <div className="flex-1 min-h-0 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium">Tool Execution Log</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAutoScroll(!autoScroll)}
            className={cn("h-7 text-xs", autoScroll && "text-primary")}
          >
            Auto-scroll {autoScroll ? 'ON' : 'OFF'}
          </Button>
        </div>

        {/* Events list */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto scrollbar-thin space-y-1"
          onScroll={(e) => {
            const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
            setAutoScroll(scrollTop + clientHeight >= scrollHeight - 10)
          }}
        >
          {toolEvents.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground text-xs">No tool events yet</p>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {toolEvents.slice(-maxEvents).map((event) => {
                const isExpanded = expandedEvents.has(event.id)
                
                return (
                  <motion.div
                    key={event.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className="glass p-2 rounded text-xs"
                  >
                    <div 
                      className="flex items-start gap-2 cursor-pointer"
                      onClick={() => toggleEventExpansion(event.id)}
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        {getEventIcon(event.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </span>
                          <span className="text-xs font-medium">
                            {formatAgentName(event.agent_name)}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground truncate">
                          {event.instruction}
                        </p>
                      </div>
                      <div className="flex-shrink-0">
                        {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      </div>
                    </div>

                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-2 pl-5 space-y-1"
                      >
                        {event.additional_data.result_preview && (
                          <p className="text-[10px] text-green-600 dark:text-green-400">
                            Result: {event.additional_data.result_preview}
                          </p>
                        )}
                        {event.additional_data.error && (
                          <p className="text-[10px] text-red-600 dark:text-red-400">
                            Error: {event.additional_data.error}
                          </p>
                        )}
                      </motion.div>
                    )}
                  </motion.div>
                )
              })}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  )
}