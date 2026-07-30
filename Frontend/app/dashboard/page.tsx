'use client'
import { useEffect, useState, useMemo } from 'react'
import ReactFlow, { Background, Controls } from 'reactflow'
import 'reactflow/dist/style.css'
import {
  ComposedChart, Line, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
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
  latency_ms?: number
}

function statusColor(status: string | undefined) {
  const s = status?.toUpperCase()
  if (s === 'CIRCUIT_BROKEN') return '#FF4757'
  if (s === 'RUNNING') return '#F5A623'
  return '#2DD4BF'
}

function buildGraph(spans: Span[]) {
  const nodes = spans.map((s, i) => {
    const color = statusColor(s.status)
    return {
      id: s.span_id,
      data: {
        label: (
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, lineHeight: 1.5 }}>
            <div style={{ color: '#E8ECF3', fontWeight: 600 }}>{s.agent_id}</div>
            <div style={{ color: '#8B93A7', fontSize: 11 }}>{s.tool_name}</div>
            <div style={{ color, fontSize: 11, marginTop: 2 }}>
              {(s.prompt_tokens || 0) + (s.completion_tokens || 0)} tok
              {s.latency_ms ? ` · ${Math.round(s.latency_ms)}ms` : ''}
            </div>
          </div>
        ),
      },
      position: { x: (s.depth ?? 0) * 240, y: i * 95 },
      style: {
        background: '#12161F',
        border: `1.5px solid ${color}`,
        borderRadius: 10,
        padding: '10px 14px',
        boxShadow: s.status?.toUpperCase() === 'CIRCUIT_BROKEN' ? `0 0 16px ${color}55` : 'none',
        width: 210,
      },
    }
  })

  const edges = spans
    .filter((s) => s.parent_span_id)
    .map((s) => ({
      id: `${s.parent_span_id}-${s.span_id}`,
      source: s.parent_span_id as string,
      target: s.span_id,
      animated: s.status?.toUpperCase() === 'RUNNING',
      style: { stroke: '#3A4254', strokeWidth: 1.5 },
    }))

  return { nodes, edges }
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{
      background: '#12161F', border: '1px solid #232A38', borderRadius: 8,
      padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 12,
    }}>
      <div style={{ color: '#E8ECF3', fontWeight: 600, marginBottom: 4 }}>
        {d.agent_id} → {d.tool_name}
      </div>
      <div style={{ color: '#8B93A7' }}>latency: <span style={{ color: '#E8ECF3' }}>{Math.round(d.latency_ms)}ms</span></div>
      <div style={{ color: '#8B93A7' }}>tokens: <span style={{ color: '#E8ECF3' }}>{d.tokens}</span></div>
      <div style={{ color: statusColor(d.status), marginTop: 4 }}>{d.status?.toUpperCase()}</div>
    </div>
  )
}

export default function Dashboard() {
  const [spans, setSpans] = useState<Span[]>([])
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const [tab, setTab] = useState<'flow' | 'chart'>('flow')

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

  useEffect(() => {
    const channel = supabase
      .channel('spans-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'spans' },
        (payload) => {
          setBannerDismissed(false)
          setSpans((current) => {
            if (payload.eventType === 'INSERT') return [...current, payload.new as Span]
            if (payload.eventType === 'UPDATE')
              return current.map((s) =>
                s.span_id === (payload.new as Span).span_id ? (payload.new as Span) : s
              )
            return current
          })
        }
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  const { nodes, edges } = useMemo(() => buildGraph(spans), [spans])
  const alertTripped = spans.some((s) => s.status?.toUpperCase() === 'CIRCUIT_BROKEN')
  const totalTokens = spans.reduce((sum, s) => sum + (s.prompt_tokens || 0) + (s.completion_tokens || 0), 0)
  const activeCount = spans.filter((s) => s.status?.toUpperCase() === 'RUNNING').length

  const chartData = useMemo(() => {
    return [...spans]
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      .map((s) => ({
        latency_ms: s.latency_ms ?? 0,
        tokens: (s.prompt_tokens || 0) + (s.completion_tokens || 0),
        agent_id: s.agent_id,
        tool_name: s.tool_name,
        status: s.status,
      }))
  }, [spans])

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#0A0D12' }}>

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 24px', borderBottom: '1px solid #232A38',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', background: '#2DD4BF',
            boxShadow: '0 0 8px #2DD4BF', animation: 'pulse 2s infinite',
          }} />
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: 18, letterSpacing: 1, color: '#E8ECF3' }}>
            TRACKTON
          </span>
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#8B93A7' }}>
            FLIGHT RECORDER
          </span>
        </div>

        <div style={{ display: 'flex', gap: 24, fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
          <div><span style={{ color: '#8B93A7' }}>CALLS </span><span style={{ color: '#E8ECF3', fontWeight: 600 }}>{spans.length}</span></div>
          <div><span style={{ color: '#8B93A7' }}>ACTIVE </span><span style={{ color: '#F5A623', fontWeight: 600 }}>{activeCount}</span></div>
          <div><span style={{ color: '#8B93A7' }}>TOKENS </span><span style={{ color: '#E8ECF3', fontWeight: 600 }}>{totalTokens.toLocaleString()}</span></div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, padding: '10px 24px 0', borderBottom: '1px solid #232A38' }}>
        {(['flow', 'chart'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '8px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 12,
              color: tab === t ? '#E8ECF3' : '#8B93A7',
              borderBottom: tab === t ? '2px solid #2DD4BF' : '2px solid transparent',
              letterSpacing: 0.5,
            }}
          >
            {t === 'flow' ? 'TRACE GRAPH' : 'LATENCY × TOKENS'}
          </button>
        ))}
      </div>

      {/* Circuit breaker banner */}
      {alertTripped && !bannerDismissed && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: '#2A1216', borderBottom: '1px solid #FF4757',
          padding: '10px 24px', fontFamily: 'JetBrains Mono, monospace', fontSize: 13,
        }}>
          <span style={{ color: '#FF4757', fontWeight: 600 }}>
            🚨 CIRCUIT_BROKEN — execution halted on one or more spans
          </span>
          <button
            onClick={() => setBannerDismissed(true)}
            style={{ background: 'none', border: 'none', color: '#8B93A7', cursor: 'pointer', fontSize: 12 }}
          >
            dismiss
          </button>
        </div>
      )}

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {tab === 'flow' && (
          <>
            <div style={{ flex: 1, position: 'relative' }}>
              <ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.4 }}>
                <Background color="#1A2029" gap={20} />
                <Controls />
              </ReactFlow>
            </div>

            <div style={{
              width: 300, borderLeft: '1px solid #232A38', background: '#0D1117',
              padding: '16px 0', overflowY: 'auto',
            }}>
              <div style={{
                fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#8B93A7',
                padding: '0 16px 12px', letterSpacing: 1, borderBottom: '1px solid #232A38', marginBottom: 8,
              }}>
                LIVE TAPE
              </div>
              {[...spans]
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                .slice(0, 8)
                .map((s) => {
                  const color = statusColor(s.status)
                  const time = new Date(s.created_at).toLocaleTimeString()
                  return (
                    <div key={s.span_id} style={{
                      padding: '8px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
                      borderLeft: `2px solid ${color}`, marginBottom: 4,
                    }}>
                      <div style={{ color: '#8B93A7' }}>{time}</div>
                      <div style={{ color: '#E8ECF3' }}>{s.agent_id} → {s.tool_name}</div>
                      <div style={{ color }}>{s.status?.toUpperCase()}</div>
                    </div>
                  )
                })}
            </div>
          </>
        )}

        {tab === 'chart' && (
          <div style={{ flex: 1, padding: 24 }}>
            <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: '#8B93A7', marginBottom: 16 }}>
              Points connect in the order calls happened — this traces the run's actual path. Watch for the line looping back into the same high-token, low-latency zone — a signature of a runaway loop.
            </div>
            <ResponsiveContainer width="100%" height="85%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                <CartesianGrid stroke="#1A2029" />
                <XAxis
                  type="number" dataKey="latency_ms" name="Latency"
                  unit="ms" stroke="#8B93A7"
                  tick={{ fill: '#8B93A7', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                  label={{ value: 'LATENCY (ms)', position: 'insideBottom', offset: -10, fill: '#8B93A7', fontSize: 11 }}
                />
                <YAxis
                  type="number" dataKey="tokens" name="Tokens"
                  stroke="#8B93A7"
                  tick={{ fill: '#8B93A7', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                  label={{ value: 'TOKENS USED', angle: -90, position: 'insideLeft', fill: '#8B93A7', fontSize: 11 }}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: '#3A4254' }} />
                <Line
                  type="monotone" dataKey="tokens"
                  stroke="#3A4254" strokeWidth={1.5} dot={false} activeDot={false}
                  isAnimationActive={false}
                />
                <Scatter data={chartData} dataKey="tokens" isAnimationActive={false}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={statusColor(entry.status)} r={6} />
                  ))}
                </Scatter>
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}