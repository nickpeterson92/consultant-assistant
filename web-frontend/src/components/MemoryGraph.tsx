import React, { useCallback, useEffect, useState } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Position,
  MarkerType,
} from 'react-flow-renderer'
import { Brain, User, Search, FileText, Target, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MemoryGraphProps {
  data: any
}

const nodeTypes = {
  domain_entity: ({ data }: any) => (
    <div className={cn(
      "px-4 py-2 rounded-lg border-2 transition-all",
      "bg-blue-500/10 border-blue-500/50 hover:border-blue-500",
      "min-w-[120px] text-center"
    )}>
      <User className="w-4 h-4 mx-auto mb-1 text-blue-500" />
      <div className="text-xs font-medium">{data.label}</div>
      {data.type && (
        <div className="text-xs text-muted-foreground mt-1">{data.type}</div>
      )}
    </div>
  ),
  action: ({ data }: any) => (
    <div className={cn(
      "px-4 py-2 rounded-lg border-2 transition-all",
      "bg-green-500/10 border-green-500/50 hover:border-green-500",
      "min-w-[120px] text-center"
    )}>
      <Zap className="w-4 h-4 mx-auto mb-1 text-green-500" />
      <div className="text-xs font-medium">{data.label}</div>
    </div>
  ),
  search: ({ data }: any) => (
    <div className={cn(
      "px-4 py-2 rounded-lg border-2 transition-all",
      "bg-purple-500/10 border-purple-500/50 hover:border-purple-500",
      "min-w-[120px] text-center"
    )}>
      <Search className="w-4 h-4 mx-auto mb-1 text-purple-500" />
      <div className="text-xs font-medium">{data.label}</div>
    </div>
  ),
  plan: ({ data }: any) => (
    <div className={cn(
      "px-4 py-2 rounded-lg border-2 transition-all",
      "bg-orange-500/10 border-orange-500/50 hover:border-orange-500",
      "min-w-[120px] text-center"
    )}>
      <Target className="w-4 h-4 mx-auto mb-1 text-orange-500" />
      <div className="text-xs font-medium">{data.label}</div>
    </div>
  ),
  default: ({ data }: any) => (
    <div className={cn(
      "px-4 py-2 rounded-lg border-2 transition-all",
      "bg-secondary border-border hover:border-primary/50",
      "min-w-[120px] text-center"
    )}>
      <FileText className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
      <div className="text-xs font-medium">{data.label}</div>
    </div>
  ),
}

export function MemoryGraph({ data }: MemoryGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  console.log('MemoryGraph data:', data)

  useEffect(() => {
    if (!data) return

    // Convert memory data to ReactFlow format
    const flowNodes: Node[] = []
    const flowEdges: Edge[] = []
    const positions = new Map<string, { x: number; y: number }>()

    // Simple layout algorithm - arrange in concentric circles
    const nodeArray = Object.entries(data.nodes || {})
    const centerX = 400
    const centerY = 300
    const radiusStep = 150

    nodeArray.forEach(([id, node]: [string, any], index) => {
      const level = Math.floor(index / 8) // 8 nodes per level
      const angle = (index % 8) * (Math.PI * 2 / 8)
      const radius = radiusStep * (level + 1)
      
      const x = centerX + Math.cos(angle) * radius
      const y = centerY + Math.sin(angle) * radius
      
      positions.set(id, { x, y })

      flowNodes.push({
        id,
        type: node.context_type || node.node_type || 'default',
        position: { x, y },
        data: {
          label: node.summary || node.title || node.content_preview || 'Unknown',
          ...node
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      })
    })

    // Create edges
    data.edges?.forEach((edge: any) => {
      flowEdges.push({
        id: `${edge.from_id}-${edge.to_id}`,
        source: edge.from_id,
        target: edge.to_id,
        label: edge.type || edge.relationship_type,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#64748b', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      })
    })

    setNodes(flowNodes)
    setEdges(flowEdges)
  }, [data, setNodes, setEdges])

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id)
  }, [])

  if (!data) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Brain className="w-16 h-16 mx-auto text-muted-foreground/30" />
          <p className="text-muted-foreground">No memory data yet</p>
          <p className="text-sm text-muted-foreground/70">
            Memory graph will appear as you interact
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        className="bg-background"
      >
        <Background color="#333" gap={16} />
        <Controls className="bg-background border border-border" />
        <MiniMap 
          className="bg-background border border-border"
          nodeColor={(node) => {
            switch (node.type) {
              case 'domain_entity': return '#3b82f6'
              case 'action': return '#10b981'
              case 'search': return '#8b5cf6'
              case 'plan': return '#f97316'
              default: return '#64748b'
            }
          }}
        />
        
        {selectedNode && (() => {
          const node = nodes.find(n => n.id === selectedNode)
          const nodeData = node?.data
          return (
            <div className="absolute top-4 right-4 bg-background/95 backdrop-blur-md border border-border rounded-lg p-4 max-w-md z-10 shadow-lg">
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-lg">Node Details</h3>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  ×
                </button>
              </div>
              
              <div className="space-y-3">
                {/* Basic Info */}
                <div className="space-y-1.5 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-[60px]">Type:</span>
                    <span className="font-medium capitalize">{node?.type?.replace('_', ' ')}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-[60px]">Summary:</span>
                    <span className="flex-1">{nodeData?.summary || nodeData?.label}</span>
                  </div>
                  {nodeData?.tags && nodeData.tags.length > 0 && (
                    <div className="flex items-start gap-2">
                      <span className="text-muted-foreground min-w-[60px]">Tags:</span>
                      <div className="flex flex-wrap gap-1">
                        {nodeData.tags.map((tag: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-full">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Content Details for Entities */}
                {nodeData?.content && (
                  <div className="border-t border-border pt-3 space-y-2">
                    <h4 className="font-medium text-sm">Entity Data</h4>
                    <div className="bg-muted/30 p-3 rounded-md max-h-64 overflow-y-auto">
                      <pre className="text-xs whitespace-pre-wrap font-mono">
                        {JSON.stringify(nodeData.content, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {/* Metadata */}
                {nodeData?.created_at && (
                  <div className="border-t border-border pt-2 text-xs text-muted-foreground">
                    <div>Created: {new Date(nodeData.created_at).toLocaleString()}</div>
                    {nodeData?.relevance !== undefined && (
                      <div>Relevance: {(nodeData.relevance * 100).toFixed(0)}%</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })()}
      </ReactFlow>
    </div>
  )
}