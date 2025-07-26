import React from 'react'
import { CheckCircle2, Circle, Loader2, AlertCircle, PlayCircle, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'

interface PlanStep {
  task: string
  tool?: string
  status?: 'pending' | 'executing' | 'completed' | 'failed'
  result?: any
  error?: string
}

interface PlanDisplayProps {
  plan: PlanStep[]
  currentStep: number
  status: 'idle' | 'created' | 'executing' | 'completed' | 'modified'
}

export function PlanDisplay({ plan, currentStep, status }: PlanDisplayProps) {
  console.log('PlanDisplay render:', { plan, currentStep, status })
  
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

  if (plan.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-4">
          <Clock className="w-16 h-16 mx-auto text-muted-foreground/30" />
          <p className="text-muted-foreground">No plan created yet</p>
          <p className="text-sm text-muted-foreground/70">
            Send a message to start planning
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto scrollbar-thin space-y-2 pr-2">
      {/* Status Header */}
      <div className="mb-4 p-3 rounded-lg glass">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Execution Status</span>
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
        {status === 'executing' && (
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
      <AnimatePresence initial={false}>
        {plan.map((step, index) => {
          const stepStatus = getStepStatus(step, index)
          
          // Handle both string and object formats
          const taskText = typeof step === 'string' ? step : (step.task || step.description || step.step || 'Unknown task')
          const toolName = typeof step === 'object' ? (step.tool || step.tool_name) : undefined
          
          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className={cn(
                "relative flex gap-3 p-3 rounded-lg transition-all",
                stepStatus === 'executing' && "glass ring-2 ring-primary/50",
                stepStatus === 'completed' && "bg-green-500/5",
                stepStatus === 'failed' && "bg-destructive/5",
                stepStatus === 'current' && "glass",
                stepStatus === 'pending' && "opacity-60"
              )}
            >
              {/* Step Number and Icon */}
              <div className="flex-shrink-0 flex flex-col items-center">
                <div className="relative">
                  {getStepIcon(step, index)}
                  {stepStatus === 'executing' && (
                    <div className="absolute inset-0 w-5 h-5 bg-primary/20 blur-xl animate-pulse" />
                  )}
                </div>
                {index < plan.length - 1 && (
                  <div className={cn(
                    "w-0.5 h-16 mt-2",
                    index < currentStep ? "bg-green-500" : "bg-border"
                  )} />
                )}
              </div>

              {/* Step Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="text-sm font-medium">{taskText}</p>
                    {toolName && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Using: {toolName}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    Step {index + 1}
                  </span>
                </div>

                {/* Result or Error */}
                {step.result && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="mt-2 p-2 rounded bg-green-500/10 text-xs"
                  >
                    <p className="text-green-600 dark:text-green-400">
                      ✓ {typeof step.result === 'string' ? step.result : 'Completed successfully'}
                    </p>
                  </motion.div>
                )}

                {step.error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="mt-2 p-2 rounded bg-destructive/10 text-xs"
                  >
                    <p className="text-destructive">
                      ✗ {step.error}
                    </p>
                  </motion.div>
                )}
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}