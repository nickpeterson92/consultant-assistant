import React, { useState, useRef, useEffect } from 'react'
import { Send, Loader2, User, Bot, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useConversation } from '@/contexts/ConversationContext'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ConversationPanelProps {
  onSendMessage: (message: string) => Promise<void>
}

export function ConversationPanel({ onSendMessage }: ConversationPanelProps) {
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { messages, addMessage } = useConversation()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)

    console.log('Sending message:', userMessage)

    // Add user message
    addMessage({
      role: 'user',
      content: userMessage,
      status: 'sent'
    })

    try {
      await onSendMessage(userMessage)
    } catch (error) {
      console.error('Error sending message:', error)
      addMessage({
        role: 'system',
        content: 'Failed to send message. Please try again.',
        status: 'error'
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as any)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4 max-w-md">
              <Bot className="w-16 h-16 mx-auto text-muted-foreground/50" />
              <h3 className="text-lg font-semibold text-muted-foreground">
                Welcome to Enterprise Assistant
              </h3>
              <p className="text-sm text-muted-foreground">
                Ask me anything about your CRM, projects, or IT systems. 
                I'll coordinate with specialized agents to help you.
              </p>
            </div>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className={cn(
                "flex gap-3",
                message.role === 'user' && "justify-end"
              )}
            >
              {message.role !== 'user' && (
                <div className={cn(
                  "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                  message.role === 'assistant' ? "bg-primary/10" : "bg-destructive/10"
                )}>
                  {message.role === 'assistant' ? (
                    <Bot className="w-5 h-5 text-primary" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-destructive" />
                  )}
                </div>
              )}

              <div className={cn(
                "max-w-[80%] rounded-lg px-4 py-2",
                message.role === 'user' 
                  ? "bg-primary text-primary-foreground" 
                  : "glass"
              )}>
                <div className="text-sm">
                  {message.role === 'user' ? (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  ) : (
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      className="prose prose-sm dark:prose-invert max-w-none prose-table:border-collapse prose-td:border prose-td:border-border prose-td:px-3 prose-td:py-2 prose-th:border prose-th:border-border prose-th:px-3 prose-th:py-2 prose-th:bg-muted/50"
                      components={{
                        pre: ({ children }) => (
                          <pre className="overflow-x-auto p-4 rounded-lg bg-muted/30 border border-border my-4">
                            {children}
                          </pre>
                        ),
                        code: ({ inline, children }) => 
                          inline ? (
                            <code className="px-1.5 py-0.5 rounded bg-muted text-xs font-mono">
                              {children}
                            </code>
                          ) : (
                            <code className="font-mono text-xs">
                              {children}
                            </code>
                          ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-4 rounded-lg border border-border">
                            <table className="min-w-full divide-y divide-border">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-muted/50">
                            {children}
                          </thead>
                        ),
                        tbody: ({ children }) => (
                          <tbody className="divide-y divide-border">
                            {children}
                          </tbody>
                        ),
                        tr: ({ children }) => (
                          <tr className="hover:bg-muted/30 transition-colors">
                            {children}
                          </tr>
                        ),
                        td: ({ children }) => (
                          <td className="px-3 py-2 text-sm">
                            {children}
                          </td>
                        ),
                        th: ({ children }) => (
                          <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider">
                            {children}
                          </th>
                        ),
                        p: ({ children }) => (
                          <p className="mb-3 last:mb-0">
                            {children}
                          </p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside space-y-1 mb-3">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside space-y-1 mb-3">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="ml-2">
                            {children}
                          </li>
                        ),
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-4 border-primary/50 pl-4 py-2 italic my-4">
                            {children}
                          </blockquote>
                        ),
                        h1: ({ children }) => (
                          <h1 className="text-2xl font-bold mb-4 mt-6 first:mt-0">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-xl font-semibold mb-3 mt-5 first:mt-0">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-lg font-semibold mb-2 mt-4 first:mt-0">
                            {children}
                          </h3>
                        ),
                        hr: () => (
                          <hr className="my-4 border-border" />
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  )}
                </div>
                <div className={cn(
                  "text-xs mt-1",
                  message.role === 'user' 
                    ? "text-primary-foreground/70" 
                    : "text-muted-foreground"
                )}>
                  {message.timestamp.toLocaleTimeString()}
                </div>
              </div>

              {message.role === 'user' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                  <User className="w-5 h-5" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div className="glass rounded-lg px-4 py-2">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="border-t border-border/50 p-4">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything..."
            className="flex-1 min-h-[60px] max-h-[120px] px-4 py-2 bg-background/50 border border-border/50 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 scrollbar-thin"
            disabled={isLoading}
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isLoading}
            className="self-end"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}