'use client'
import { useEffect, useState, useMemo } from 'react'
import ReactFlow, { Background, Controls } from 'reactflow'
import 'reactflow/dist/style.css'
import { supabase } from '../../lib/supabaseClient'

type Span = {
  span_id: string
  parent_span_id: string | null
  agent_id: string
  tool_name: string
  depth: number
  status: string
  prompt_tokens: number
  completion_tokens: number
  created_at: string
}

function buildGraph(spans: Span[]) {
  const nodes = spans.map((s, i) => ({
    id: s.span_id,
    data: {
      label: `${s.agent_id} → ${s.tool_name} (${(s.prompt_tokens || 0) + (s.completion_tokens || 0)} tok)`,
    },
    position: { x: (s.depth ?? 0) * 220, y: i * 90 },
    style: {
      background: s.status === 'circuit_broken' ? '#ff4d4d' : '#eef',
      border: '1px solid #556',
      borderRadius: 6,
      padding: 8,
      fontSize: 12,
    },
  }))

  const edges = spans
    .filter((s) => s.parent_span_id)
    .map((s) => ({
      id: `${s.parent_span_id}-${s.span_id}`,
      source: s.parent_span_id as string,
      target: s.span_id,
      animated: s.status === 'running',
    }))

  return { nodes, edges }
}

export default function Dashboard() {
  const [spans, setSpans] = useState<Span[]>([])

  // Load existing spans
  useEffect(() => {
    async function loadSpans() {
      const { data, error } = await supabase
        .from('spans')
        .select('*')
        .order('created_at', { ascending: true })

      if (error) console.error('Error loading spans:', error)
      else setSpans(data as Span[])
    }
    loadSpans()
  }, [])

  // Live updates
  useEffect(() => {
    const channel = supabase
      .channel('spans-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'spans' },
        (payload) => {
          setSpans((current) => {
            if (payload.eventType === 'INSERT') {
              return [...current, payload.new as Span]
            }
            if (payload.eventType === 'UPDATE') {
              return current.map((s) =>
                s.span_id === (payload.new as Span).span_id ? (payload.new as Span) : s
              )
            }
            return current
          })
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  const { nodes, edges } = useMemo(() => buildGraph(spans), [spans])
  const alertTripped = spans.some((s) => s.status === 'circuit_broken')
  const totalTokens = spans.reduce(
    (sum, s) => sum + (s.prompt_tokens || 0) + (s.completion_tokens || 0),
    0
  )

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <div style={{ padding: 12, fontFamily: 'monospace' }}>
        <strong>Total calls:</strong> {spans.length} &nbsp;|&nbsp;
        <strong>Total tokens:</strong> {totalTokens}
      </div>

      <ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.5 }}>
        <Background />
        <Controls />
      </ReactFlow>

      {alertTripped && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(255,0,0,0.15)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 999, pointerEvents: 'none',
        }}>
          <div style={{
            background: '#fff', border: '3px solid red', borderRadius: 10,
            padding: '24px 40px', fontSize: 24, fontWeight: 700, color: 'red',
            pointerEvents: 'auto',
          }}>
            🚨 CIRCUIT_BROKEN — execution halted
          </div>
        </div>
      )}
    </div>
  )
}