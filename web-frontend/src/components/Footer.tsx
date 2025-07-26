import React from 'react'
import { Github, Globe, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Footer() {
  return (
    <footer className="border-t border-border/50 backdrop-blur-md bg-background/80">
      <div className="container mx-auto px-4 h-12 flex items-center">
        <div className="flex items-center justify-between text-sm text-muted-foreground w-full">
          <div className="flex items-center gap-4">
            <span>© 2025 Enterprise Assistant</span>
            <a 
              href="https://github.com/anthropics/claude-code"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-foreground transition-colors"
            >
              <Github className="w-4 h-4" />
              <span>Source</span>
            </a>
          </div>
          
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>Press ESC to interrupt execution</span>
          </div>
        </div>
      </div>
    </footer>
  )
}