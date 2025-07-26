import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

export interface ThreadState {
  threadId: string
  createdAt: Date
  lastActivity: Date
  status: 'active' | 'interrupted' | 'completed'
  metadata: {
    userId: string
    sessionId: string
    conversationId?: string
  }
}

interface ThreadContextValue {
  thread: ThreadState
  resetThread: () => void
  updateThreadStatus: (status: ThreadState['status']) => void
  updateLastActivity: () => void
}

const ThreadContext = createContext<ThreadContextValue | undefined>(undefined)

// Generate thread ID with collision prevention
function generateThreadId(): string {
  const timestamp = Date.now().toString(36)
  const random = Math.random().toString(36).substring(2, 9)
  const sessionPrefix = 'web'
  return `${sessionPrefix}-${timestamp}-${random}`
}

// Generate session ID (persists across thread resets)
function generateSessionId(): string {
  const stored = sessionStorage.getItem('session_id')
  if (stored) return stored
  
  const sessionId = `session-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 9)}`
  sessionStorage.setItem('session_id', sessionId)
  return sessionId
}

interface ThreadProviderProps {
  children: React.ReactNode
  userId?: string
}

export function ThreadProvider({ children, userId = 'web-user' }: ThreadProviderProps) {
  const [thread, setThread] = useState<ThreadState>(() => ({
    threadId: generateThreadId(),
    createdAt: new Date(),
    lastActivity: new Date(),
    status: 'active',
    metadata: {
      userId,
      sessionId: generateSessionId(),
    }
  }))

  const resetThread = useCallback(() => {
    setThread({
      threadId: generateThreadId(),
      createdAt: new Date(),
      lastActivity: new Date(),
      status: 'active',
      metadata: {
        userId,
        sessionId: thread.metadata.sessionId, // Keep session ID
      }
    })
  }, [userId, thread.metadata.sessionId])

  const updateThreadStatus = useCallback((status: ThreadState['status']) => {
    setThread(prev => ({
      ...prev,
      status,
      lastActivity: new Date()
    }))
  }, [])

  const updateLastActivity = useCallback(() => {
    setThread(prev => ({
      ...prev,
      lastActivity: new Date()
    }))
  }, [])

  // Log thread lifecycle events
  useEffect(() => {
    console.log('[ThreadContext] Thread created:', thread.threadId)
    
    return () => {
      console.log('[ThreadContext] Thread unmounting:', thread.threadId)
    }
  }, [thread.threadId])

  // Persist thread state to sessionStorage
  useEffect(() => {
    const threadData = {
      threadId: thread.threadId,
      createdAt: thread.createdAt.toISOString(),
      status: thread.status
    }
    sessionStorage.setItem(`thread_${thread.threadId}`, JSON.stringify(threadData))
  }, [thread])

  const value: ThreadContextValue = {
    thread,
    resetThread,
    updateThreadStatus,
    updateLastActivity
  }

  return (
    <ThreadContext.Provider value={value}>
      {children}
    </ThreadContext.Provider>
  )
}

export function useThread() {
  const context = useContext(ThreadContext)
  if (!context) {
    throw new Error('useThread must be used within a ThreadProvider')
  }
  return context
}

// Utility function to validate thread ID format
export function isValidThreadId(threadId: string): boolean {
  // Must match pattern: web-timestamp-random
  const pattern = /^web-[a-z0-9]{8,}-[a-z0-9]{7}$/
  return pattern.test(threadId)
}