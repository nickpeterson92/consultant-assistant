# Enterprise Assistant Web Frontend

A beautiful, modern web interface for the Enterprise Assistant multi-agent orchestration system.

## Features

- **Real-time Chat Interface**: Smooth animations and markdown support
- **Live Plan Execution Display**: Watch as the AI executes each step
- **Interactive Memory Graph**: Visualize entity relationships and connections
- **LLM Context Viewer**: See exactly what context is sent to the AI
- **Interrupt Support**: Press ESC to modify plans mid-execution
- **Dark/Light Mode**: Beautiful glass morphism effects
- **Responsive Design**: Works on desktop and mobile

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development
- **Tailwind CSS** for styling
- **shadcn/ui** for beautiful components
- **React Flow** for graph visualization
- **Framer Motion** for animations
- **Server-Sent Events** for real-time updates
- **WebSocket** for interrupt handling

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000)

## Architecture

- `/components` - React components
  - `ConversationPanel` - Chat interface
  - `VisualizationPanel` - Tabbed panel for Memory/Context/Plan
  - `MemoryGraph` - Interactive graph visualization
  - `PlanDisplay` - Real-time plan execution view
  - `LLMContextDisplay` - Context viewer with syntax highlighting
- `/hooks` - Custom React hooks
  - `useSSE` - Server-sent events handling
  - `useWebSocket` - WebSocket connection for interrupts
  - `useA2AClient` - API client for orchestrator
- `/contexts` - React contexts for state management

## API Endpoints

The frontend expects these endpoints from the orchestrator:
- `POST /a2a` - Send messages to orchestrator
- `GET /a2a/stream` - SSE stream for real-time events
- `WS /ws` - WebSocket for interrupt handling

## Environment Variables

None required - the Vite proxy handles API routing to `localhost:8000`.

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.