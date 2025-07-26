import React from 'react'
import { Moon, Sun, Wifi, WifiOff, Cpu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { motion } from 'framer-motion'

interface HeaderProps {
  isDarkMode: boolean
  onToggleDarkMode: () => void
  sseConnected: boolean
  wsConnected: boolean
}

export function Header({ isDarkMode, onToggleDarkMode, sseConnected, wsConnected }: HeaderProps) {
  return (
    <header className="border-b border-border/50 backdrop-blur-md bg-background/80 sticky top-0 z-50">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo and Title */}
        <div className="flex items-center gap-4">
          <motion.div
            initial={{ rotate: 0 }}
            animate={{ rotate: 360 }}
            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
            className="relative"
          >
            <Cpu className="w-8 h-8 text-primary" />
            <div className="absolute inset-0 w-8 h-8 bg-primary/20 blur-xl animate-pulse-glow" />
          </motion.div>
          
          <div>
            <h1 className="text-xl font-bold gradient-text">
              Enterprise Assistant
            </h1>
            <p className="text-xs text-muted-foreground">
              Plan-and-Execute Multi-Agent Orchestration
            </p>
          </div>
        </div>
        
        {/* Status and Controls */}
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <div className={cn(
                "w-2 h-2 rounded-full",
                sseConnected ? "bg-green-500" : "bg-red-500"
              )} />
              <span className="text-xs text-muted-foreground">SSE</span>
            </div>
            
            <div className="flex items-center gap-1">
              <div className={cn(
                "w-2 h-2 rounded-full",
                wsConnected ? "bg-green-500" : "bg-red-500"
              )} />
              <span className="text-xs text-muted-foreground">WS</span>
            </div>
          </div>
          
          {/* Dark Mode Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleDarkMode}
            className="rounded-full"
          >
            {isDarkMode ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </Button>
        </div>
      </div>
    </header>
  )
}