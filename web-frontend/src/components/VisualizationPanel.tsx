import { useState, useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { MemoryGraph } from '@/components/MemoryGraph'
import { LLMContextDisplay } from '@/components/LLMContextDisplay'
import { PlanDisplay } from '@/components/PlanDisplay'
import { ToolEventsDisplay } from '@/components/ToolEventsDisplay'
import { Brain, FileText, ListChecks, Wrench } from 'lucide-react'

interface VisualizationPanelProps {
  events: any[]
  onPlanUpdate: (plan: any[]) => void
}

export function VisualizationPanel({ events, onPlanUpdate }: VisualizationPanelProps) {
  const [activeTab, setActiveTab] = useState('plan')
  const [memoryData, setMemoryData] = useState<any>(null)
  const [llmContext, setLLMContext] = useState<any>(null)
  const [planData, setPlanData] = useState<any>({
    plan: [],
    currentStep: -1,
    status: 'idle'
  })
  const [toolEvents, setToolEvents] = useState<any[]>([])
  const [processedEventCount, setProcessedEventCount] = useState(0)

  // Process SSE events
  useEffect(() => {
    // Only process new events that haven't been processed yet
    const newEvents = events.slice(processedEventCount)
    if (newEvents.length === 0) return
    
    console.log(`Processing ${newEvents.length} new events (previously processed: ${processedEventCount})`)
    
    newEvents.forEach(event => {
      console.log('Processing event:', event.type, event.data)
      
      switch (event.type) {
        // Memory events from backend
        case 'memory_graph_snapshot':
          console.log('Memory graph snapshot received:', event.data)
          setMemoryData(event.data.graph_data)
          break
        case 'memory_node_added':
          console.log('Memory node added:', event.data)
          // For now, just store the latest node data
          // In a real app, we'd update the graph incrementally
          if (event.data.node_data) {
            setMemoryData((prev: any) => ({
              nodes: { ...prev?.nodes, [event.data.node_id]: event.data.node_data },
              edges: prev?.edges || []
            }))
          }
          break
        case 'memory_edge_added':
          console.log('Memory edge added:', event.data)
          if (event.data.edge_data) {
            setMemoryData((prev: any) => ({
              nodes: prev?.nodes || {},
              edges: [...(prev?.edges || []), event.data.edge_data]
            }))
          }
          break
        
        // LLM context events
        case 'llm_context':
          console.log('LLM context received:', event.data)
          setLLMContext(event.data)
          break
        
        // Plan events from backend
        case 'plan_created':
          console.log('Plan created:', event.data)
          const plan = event.data.plan_steps || []
          // Convert plan steps to objects with status from the start
          const planWithStatus = plan.map((step: any) => {
            const stepText = typeof step === 'string' ? step : (step.task || step.description || step)
            return {
              task: stepText,
              status: 'pending',
              result: undefined
            }
          })
          setPlanData({
            plan: planWithStatus,
            currentStep: -1,
            status: 'created'
          })
          onPlanUpdate(plan) // Send original plan format to parent
          break
        case 'task_started':
          console.log('Task started:', event.data)
          setPlanData((prev: any) => ({
            ...prev,
            currentStep: (event.data.step_number || 1) - 1, // Convert 1-based to 0-based
            status: 'executing'
          }))
          break
        case 'task_completed':
          console.log('Task completed:', event.data)
          // Don't manually update plan here - wait for plan_updated event
          // This prevents inconsistencies between string and object formats
          break
        case 'plan_modified':
          console.log('Plan modified:', event.data)
          const newPlan = event.data.plan_steps || []
          // Convert modified plan steps to objects with status
          const modifiedPlanWithStatus = newPlan.map((step: any) => {
            const stepText = typeof step === 'string' ? step : (step.task || step.description || step)
            return {
              task: stepText,
              status: 'pending',
              result: undefined
            }
          })
          setPlanData({
            plan: modifiedPlanWithStatus,
            currentStep: 0,
            status: 'modified'
          })
          onPlanUpdate(newPlan) // Send original plan format to parent
          break
        case 'plan_updated':
          console.log('Plan updated:', event.data)
          // Reconstruct plan with proper status tracking
          const planSteps = event.data.plan_steps || []
          const completedSteps = event.data.completed_steps || []
          const failedSteps = event.data.failed_steps || []
          const completedCount = event.data.completed_count || 0
          const failedCount = event.data.failed_count || 0
          const totalSteps = event.data.total_steps || planSteps.length
          
          // Convert plan steps to objects with status
          const updatedPlanWithStatus = planSteps.map((step: any, index: number) => {
            const stepText = typeof step === 'string' ? step : (step.task || step.description || step)
            
            // Determine status based on completed/failed arrays
            let status = 'pending'
            let result = undefined
            
            if (completedSteps.includes(stepText)) {
              status = 'completed'
              result = 'Completed successfully'
            } else if (failedSteps.includes(stepText)) {
              status = 'failed'
              result = 'Failed'
            } else if (index < completedCount + failedCount) {
              status = 'completed'
              result = 'Completed successfully' 
            }
            
            return {
              task: stepText,
              status: status,
              result: result
            }
          })
          
          // Determine current step and overall status
          const currentStepIndex = completedCount + failedCount
          let overallStatus = 'executing'
          
          if (currentStepIndex >= totalSteps) {
            // All steps completed
            overallStatus = failedCount > 0 ? 'completed' : 'completed'
          } else {
            // If we're in the middle of execution (even at step 0), we're executing
            // The only time status should be 'created' is when no execution has started yet
            // which would be handled by plan_created event, not plan_updated
            overallStatus = 'executing'
          }
          
          setPlanData({
            plan: updatedPlanWithStatus,
            currentStep: Math.min(currentStepIndex, totalSteps - 1),
            status: overallStatus
          })
          break
        
        // Tool events
        case 'agent_call_started':
        case 'agent_call_completed':
        case 'agent_call_failed':
        case 'tool_selected':
        case 'direct_response':
        case 'web_search_started':
        case 'web_search_completed':
        case 'human_input_requested':
        case 'human_input_received':
          setToolEvents(prev => [...prev, {
            id: `${event.type}_${Date.now()}_${Math.random()}`,
            timestamp: new Date(),
            type: event.type,
            agent_name: event.data?.agent_name || 'unknown',
            task_id: event.data?.task_id || '',
            instruction: event.data?.instruction || '',
            additional_data: event.data?.additional_data || {}
          }].slice(-200)) // Keep last 200 events
          break
      }
    })
    
    // Update the count of processed events
    setProcessedEventCount(events.length)
  }, [events, onPlanUpdate, processedEventCount])

  return (
    <div className="h-full flex flex-col">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="grid w-full grid-cols-4 m-4">
          <TabsTrigger value="plan" className="flex items-center gap-2">
            <ListChecks className="w-4 h-4" />
            <span>Plan</span>
            {planData.status === 'executing' && (
              <span className="ml-1 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            )}
          </TabsTrigger>
          <TabsTrigger value="tools" className="flex items-center gap-2">
            <Wrench className="w-4 h-4" />
            <span>Tools</span>
            {toolEvents.length > 0 && (
              <span className="ml-1 text-xs bg-primary/20 px-1.5 py-0.5 rounded-full">
                {toolEvents.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="memory" className="flex items-center gap-2">
            <Brain className="w-4 h-4" />
            <span>Memory</span>
          </TabsTrigger>
          <TabsTrigger value="context" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            <span>Context</span>
          </TabsTrigger>
        </TabsList>

        <div className="flex-1 relative">
          <TabsContent value="plan" className="absolute inset-0 p-4" data-state={activeTab === 'plan' ? 'active' : 'inactive'}>
            <PlanDisplay 
              plan={planData.plan}
              currentStep={planData.currentStep}
              status={planData.status}
            />
          </TabsContent>

          <TabsContent value="tools" className="absolute inset-0 p-4" data-state={activeTab === 'tools' ? 'active' : 'inactive'}>
            <ToolEventsDisplay events={toolEvents} />
          </TabsContent>

          <TabsContent value="memory" className="absolute inset-0 p-4" data-state={activeTab === 'memory' ? 'active' : 'inactive'}>
            <MemoryGraph data={memoryData} />
          </TabsContent>

          <TabsContent value="context" className="absolute inset-0 p-4" data-state={activeTab === 'context' ? 'active' : 'inactive'}>
            <LLMContextDisplay context={llmContext} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}