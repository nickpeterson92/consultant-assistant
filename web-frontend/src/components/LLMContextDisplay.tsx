import React, { useState } from 'react'
import { FileText, Clock, Hash, Copy, Check, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface LLMContextDisplayProps {
  context: any
}

export function LLMContextDisplay({ context }: LLMContextDisplayProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['full_prompt']))

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  if (!context) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <FileText className="w-16 h-16 mx-auto text-muted-foreground/30" />
          <p className="text-muted-foreground">No context data yet</p>
          <p className="text-sm text-muted-foreground/70">
            LLM context will appear during planning and execution
          </p>
        </div>
      </div>
    )
  }

  const { context_type, context_text, metadata = {}, full_prompt, timestamp } = context

  return (
    <div className="h-full overflow-y-auto scrollbar-thin space-y-4 pr-2">
      {/* Header */}
      <div className="glass rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center",
              context_type === 'execution' && "bg-green-500/20",
              context_type === 'planning' && "bg-blue-500/20",
              context_type === 'replanning' && "bg-yellow-500/20"
            )}>
              {context_type === 'execution' && <Hash className="w-4 h-4 text-green-500" />}
              {context_type === 'planning' && <FileText className="w-4 h-4 text-blue-500" />}
              {context_type === 'replanning' && <Clock className="w-4 h-4 text-yellow-500" />}
            </div>
            <div>
              <h3 className="font-medium capitalize">{context_type} Context</h3>
              <p className="text-xs text-muted-foreground">
                {new Date(timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        </div>

        {/* Metadata */}
        {Object.keys(metadata).length > 0 && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(metadata).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <span className="text-muted-foreground">{key}:</span>
                <span className="font-mono">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Context Text */}
      {context_text && (
        <div className="space-y-2">
          <button
            onClick={() => toggleSection('context_text')}
            className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors"
          >
            {expandedSections.has('context_text') ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            Context Summary
          </button>
          
          <AnimatePresence>
            {expandedSections.has('context_text') && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="glass rounded-lg p-4 relative"
              >
                <Button
                  size="icon"
                  variant="ghost"
                  className="absolute top-2 right-2 h-6 w-6"
                  onClick={() => copyToClipboard(context_text, 'context')}
                >
                  {copiedId === 'context' ? (
                    <Check className="w-3 h-3 text-green-500" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </Button>
                <div className="prose prose-sm dark:prose-invert max-w-none pr-8">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {context_text}
                  </ReactMarkdown>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Full Prompt */}
      {full_prompt && (
        <div className="space-y-2">
          <button
            onClick={() => toggleSection('full_prompt')}
            className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors"
          >
            {expandedSections.has('full_prompt') ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            Full Prompt
          </button>
          
          <AnimatePresence>
            {expandedSections.has('full_prompt') && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="glass rounded-lg p-4 relative"
              >
                <Button
                  size="icon"
                  variant="ghost"
                  className="absolute top-2 right-2 h-6 w-6"
                  onClick={() => copyToClipboard(full_prompt, 'prompt')}
                >
                  {copiedId === 'prompt' ? (
                    <Check className="w-3 h-3 text-green-500" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </Button>
                <SyntaxHighlighter
                  language="markdown"
                  style={oneDark}
                  customStyle={{
                    background: 'transparent',
                    padding: 0,
                    margin: 0,
                    fontSize: '0.75rem',
                  }}
                  className="!bg-transparent"
                >
                  {full_prompt}
                </SyntaxHighlighter>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}