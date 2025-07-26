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
          setPlanData({
            plan: plan,
            currentStep: -1,
            status: 'created'
          })
          onPlanUpdate(plan)
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
          const stepIndex = (event.data.step_number || 1) - 1
          setPlanData((prev: any) => {
            const isLastStep = stepIndex === prev.plan.length - 1
            return {
              ...prev,
              plan: prev.plan.map((step: any, idx: number) => 
                idx === stepIndex
                  ? { ...step, status: event.data.success ? 'completed' : 'failed', result: event.data.result }
                  : step
              ),
              status: isLastStep ? 'completed' : prev.status
            }
          })
          break
        case 'plan_modified':
          console.log('Plan modified:', event.data)
          const newPlan = event.data.plan_steps || []
          setPlanData({
            plan: newPlan,
            currentStep: 0,
            status: 'modified'
          })
          onPlanUpdate(newPlan)
          break
        case 'plan_updated':
          console.log('Plan updated:', event.data)
          setPlanData((prev: any) => ({
            plan: event.data.plan_steps || prev.plan,
            currentStep: (event.data.current_step || 1) - 1,
            status: prev.status
          }))
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

        <div className="flex-1 overflow-hidden p-4">
          <TabsContent value="plan" className="h-full">
            <PlanDisplay 
              plan={planData.plan}
              currentStep={planData.currentStep}
              status={planData.status}
            />
          </TabsContent>

          <TabsContent value="tools" className="h-full overflow-hidden">
            <div className="h-full">
              <ToolEventsDisplay events={toolEvents} />
            </div>
          </TabsContent>

          <TabsContent value="memory" className="h-full">
            <MemoryGraph data={memoryData} />
          </TabsContent>

          <TabsContent value="context" className="h-full">
            <LLMContextDisplay context={llmContext} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}