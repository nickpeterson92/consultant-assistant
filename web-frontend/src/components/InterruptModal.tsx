import React, { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Send } from 'lucide-react'
import { cn } from '@/lib/utils'

interface InterruptModalProps {
  isOpen: boolean
  onClose: () => void
  currentPlan: any[]
  onSubmit: (modifiedPlan: string) => Promise<void>
}

export function InterruptModal({ isOpen, onClose, currentPlan, onSubmit }: InterruptModalProps) {
  const [modifiedPlan, setModifiedPlan] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!modifiedPlan.trim()) return
    
    setIsSubmitting(true)
    try {
      await onSubmit(modifiedPlan)
      setModifiedPlan('')
      onClose()
    } catch (error) {
      console.error('Failed to submit interrupt:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-yellow-500" />
            </div>
            <div>
              <DialogTitle>Plan Execution Interrupted</DialogTitle>
              <DialogDescription>
                You've interrupted the current execution. You can modify the plan below.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 my-4">
          {/* Current Plan Display */}
          <div>
            <h4 className="text-sm font-medium mb-2">Current Plan:</h4>
            <div className="glass rounded-lg p-3 max-h-[200px] overflow-y-auto scrollbar-thin">
              {currentPlan.length > 0 ? (
                <ol className="space-y-1 text-sm">
                  {currentPlan.map((step, index) => (
                    <li key={index} className="flex gap-2">
                      <span className="text-muted-foreground">{index + 1}.</span>
                      <span>{typeof step === 'string' ? step : step.task}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-muted-foreground text-sm">No plan available</p>
              )}
            </div>
          </div>

          {/* Modification Input */}
          <div>
            <label htmlFor="modified-plan" className="text-sm font-medium mb-2 block">
              How would you like to modify the plan?
            </label>
            <textarea
              id="modified-plan"
              value={modifiedPlan}
              onChange={(e) => setModifiedPlan(e.target.value)}
              placeholder="Describe your changes... (e.g., 'Skip step 2 and add a step to verify the results')"
              className={cn(
                "w-full min-h-[100px] px-3 py-2 rounded-lg",
                "bg-background/50 border border-border/50",
                "focus:outline-none focus:ring-2 focus:ring-primary/50",
                "scrollbar-thin resize-none"
              )}
              autoFocus
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!modifiedPlan.trim() || isSubmitting}
          >
            <Send className="w-4 h-4 mr-2" />
            Submit Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}