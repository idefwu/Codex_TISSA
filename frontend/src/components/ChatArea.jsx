import { Bot, CheckCircle2, Database, Image, RefreshCw, Send, User, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

const routeOptions = [
  { value: 'general_chat', label: 'General' },
  { value: 'db_query', label: 'DB Query' },
  { value: 'db_write', label: 'DB Write' },
  { value: 'rag', label: 'RAG' },
  { value: 'image_skill', label: 'Image' },
]

const routeLabelMap = Object.fromEntries(routeOptions.map((route) => [route.value, route.label]))

const dbWriteToolLabels = {
  create_expense_report: '新增費用資料',
  create_invoice: '新增發票資料',
}

const dbWriteFieldLabels = {
  employee_name: '員工姓名',
  employee_code: '員工編號',
  vendor_name: '廠商',
  expense_date: '費用日期',
  category: '類別',
  amount: '金額',
  currency: '幣別',
  description: '說明',
  status: '狀態',
  invoice_number: '發票號碼',
  invoice_date: '發票日期',
  buyer_tax_id: '買方統編',
  seller_tax_id: '賣方統編',
  total_amount: '總金額',
  raw_text: '原始文字',
  source_image_path: '圖片路徑',
}

function formatCellValue(value) {
  if (value === null || value === undefined) {
    return '-'
  }

  if (typeof value === 'object') {
    return JSON.stringify(value)
  }

  return String(value)
}

function TypingIndicator() {
  return (
    <span className="typing-indicator" aria-label="系統思考中">
      <span />
      <span />
      <span />
    </span>
  )
}

function SqlAgentDetails({ metadata }) {
  const route = metadata?.route?.route
  const sqlAgent = metadata?.sql_agent

  if (!route && !sqlAgent) {
    return null
  }

  const columns = sqlAgent?.columns ?? []
  const rows = sqlAgent?.rows ?? []
  const routeLabel = routeLabelMap[route] ?? route ?? 'General'

  return (
    <div className="sql-agent-panel">
      {route ? (
        <div className="sql-agent-route">
          <Database size={14} />
          <span>本次使用 route：{routeLabel}</span>
        </div>
      ) : null}

      {sqlAgent?.error ? (
        <div className="sql-agent-error">{sqlAgent.error}</div>
      ) : null}

      {sqlAgent?.sql ? (
        <details className="sql-agent-details">
          <summary>產生的 SQL</summary>
          <pre>
            <code>{sqlAgent.sql}</code>
          </pre>
        </details>
      ) : null}

      {columns.length > 0 ? (
        <details className="sql-agent-details">
          <summary>查詢結果表格（{sqlAgent?.row_count ?? rows.length} 筆）</summary>
          <div className="sql-result-table-wrap">
            <table className="sql-result-table">
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.length > 0 ? (
                  rows.map((row, rowIndex) => (
                    <tr key={`sql-row-${rowIndex}`}>
                      {columns.map((column) => (
                        <td key={`${rowIndex}-${column}`}>{formatCellValue(row[column])}</td>
                      ))}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={columns.length}>沒有符合條件的資料</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </div>
  )
}

function DbWriteDetails({ isBusy, message, metadata, onCancelDbWrite, onConfirmDbWrite }) {
  const dbWrite = metadata?.db_write

  if (!dbWrite) {
    return null
  }

  const status = dbWrite.status
  const fields = dbWrite.fields ?? {}
  const resolved = dbWrite.resolved ?? {}
  const result = dbWrite.result ?? null
  const warnings = dbWrite.warnings ?? []
  const isPending = status === 'pending_confirmation'
  const isNeedsMoreInfo = status === 'needs_more_info'
  const isConfirmed = status === 'confirmed'
  const isCancelled = status === 'cancelled'

  return (
    <div className={`db-write-card db-write-card--${status ?? 'unknown'}`}>
      <div className="db-write-card-header">
        <div>
          <p className="panel-kicker">DB Write</p>
          <h4>{isPending ? '待確認寫入' : dbWriteToolLabels[dbWrite.tool] ?? 'DB Write'}</h4>
        </div>
        {isConfirmed ? <CheckCircle2 size={18} /> : null}
        {isCancelled ? <XCircle size={18} /> : null}
      </div>

      {isNeedsMoreInfo ? (
        <div className="db-write-state">
          需要補充：{(dbWrite.missing_fields ?? []).join('、') || '欄位資訊'}
        </div>
      ) : null}

      {Object.keys(fields).length > 0 ? (
        <div className="db-write-field-grid">
          {Object.entries(fields).map(([key, value]) => (
            <div key={key} className="db-write-field">
              <span>{dbWriteFieldLabels[key] ?? key}</span>
              <strong>{formatCellValue(value)}</strong>
            </div>
          ))}
        </div>
      ) : null}

      {resolved.employee_name || resolved.employee_code || resolved.vendor_name ? (
        <div className="db-write-resolved">
          {resolved.employee_name ? <span>員工：{resolved.employee_name}（{resolved.employee_code}）</span> : null}
          {resolved.vendor_name ? <span>廠商：{resolved.vendor_name}</span> : null}
        </div>
      ) : null}

      {warnings.length > 0 ? (
        <div className="db-write-warning">
          {warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      {result ? (
        <div className="db-write-result">
          <CheckCircle2 size={16} />
          <span>{result.summary ?? `新增資料 ID：${result.entity_id}`}</span>
        </div>
      ) : null}

      {isPending ? (
        <div className="db-write-actions">
          <button
            type="button"
            className="db-write-confirm-button"
            disabled={isBusy}
            onClick={() => onConfirmDbWrite(message.id)}
          >
            確認寫入
          </button>
          <button
            type="button"
            className="db-write-cancel-button"
            disabled={isBusy}
            onClick={() => onCancelDbWrite(message.id)}
          >
            取消
          </button>
        </div>
      ) : null}
    </div>
  )
}

function MessageBubble({ isBusy, message, onCancelDbWrite, onConfirmDbWrite }) {
  const isUser = message.role === 'user'
  const metadata = message.metadata_json ?? {}

  return (
    <article className={`message-row ${isUser ? 'message-row--user' : 'message-row--assistant'}`}>
      <div className="message-avatar" aria-hidden="true">
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className={`message-bubble ${message.isThinking ? 'message-bubble--thinking' : ''}`}>
        {message.isThinking ? (
          <TypingIndicator />
        ) : isUser ? (
          message.content
        ) : (
          <>
            <SqlAgentDetails metadata={metadata} />
            <DbWriteDetails
              isBusy={isBusy}
              message={message}
              metadata={metadata}
              onCancelDbWrite={onCancelDbWrite}
              onConfirmDbWrite={onConfirmDbWrite}
            />
            <ReactMarkdown
              components={{
                a: ({ children, ...props }) => (
                  <a {...props} target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </>
        )}
      </div>
    </article>
  )
}

function RouterDecisionPanel({ routeDecision, onConfirmRoute, onSelectRoute }) {
  if (!routeDecision) {
    return null
  }

  const router = routeDecision.router
  const selectedRoute = routeDecision.selectedRoute ?? router?.route
  const needsConfirmation = routeDecision.status === 'needs_confirmation'
  const isBusy = routeDecision.status === 'routing' || routeDecision.status === 'executing'

  return (
    <section className={`router-panel router-panel--${routeDecision.status}`} aria-label="Router 判斷結果">
      <div className="router-panel-header">
        <div>
          <p className="panel-kicker">Context Router</p>
          <h3>{isBusy && !router ? 'Router 判斷中...' : `建議路由：${router?.route ?? 'general_chat'}`}</h3>
        </div>
        {router ? <span>{Math.round(Number(router.confidence ?? 0) * 100)}%</span> : null}
      </div>

      {router ? (
        <p className="router-reason">
          {router.reason}
          {routeDecision.fallback ? '（fallback）' : ''}
        </p>
      ) : null}

      <div className="route-button-group" aria-label="選擇 route">
        {routeOptions.map((route) => (
          <button
            key={route.value}
            type="button"
            className={`route-button ${selectedRoute === route.value ? 'route-button--selected' : ''} ${
              router?.route === route.value ? 'route-button--suggested' : ''
            }`}
            disabled={!needsConfirmation}
            onClick={() => onSelectRoute(route.value)}
          >
            {route.label}
          </button>
        ))}
      </div>

      {router?.suggested_followup_question ? (
        <p className="router-followup">{router.suggested_followup_question}</p>
      ) : null}

      {needsConfirmation ? (
        <button type="button" className="confirm-route-button" onClick={onConfirmRoute}>
          確認執行
        </button>
      ) : null}
    </section>
  )
}

export function ChatArea({
  chat,
  dbStatus,
  error,
  isLoading,
  isSending,
  memoryRounds,
  routeDecision,
  onCancelDbWrite,
  onConfirmDbWrite,
  onConfirmRoute,
  onRefreshDbStatus,
  onSelectRoute,
  onSendMessage,
}) {
  const [draft, setDraft] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat?.messages])

  const submitMessage = () => {
    const trimmedDraft = draft.trim()

    if (!trimmedDraft || !chat || isSending) {
      return
    }

    onSendMessage(trimmedDraft)
    setDraft('')
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    submitMessage()
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submitMessage()
    }
  }

  return (
    <main className="chat-area">
      <section className="chat-header">
        <div>
          <p className="panel-kicker">Current Chat</p>
          <h2>{chat?.title ?? '聊天室'}</h2>
          <span className="memory-badge">目前記憶：{memoryRounds} 輪</span>
        </div>
        <div className={`db-status db-status--${dbStatus.state}`} title={dbStatus.detail}>
          <Database size={16} />
          <span>{dbStatus.label}</span>
          <button
            type="button"
            className="icon-button db-refresh-button"
            onClick={onRefreshDbStatus}
            aria-label="重新檢查 DB 狀態"
            title="重新檢查 DB 狀態"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </section>

      <section className="messages-pane" aria-label="聊天訊息">
        {isLoading ? <div className="chat-state">載入聊天訊息...</div> : null}
        {error ? <div className="chat-state chat-state--error">{error}</div> : null}
        <RouterDecisionPanel
          routeDecision={routeDecision}
          onConfirmRoute={onConfirmRoute}
          onSelectRoute={onSelectRoute}
        />
        {!isLoading && !chat ? <div className="empty-chat-state">請先新增或選擇一個聊天室。</div> : null}
        {!isLoading && chat?.messages.length === 0 ? (
          <div className="empty-chat-state">這個聊天室還沒有訊息。</div>
        ) : null}
        {chat?.messages.map((message) => (
          <MessageBubble
            key={message.id}
            isBusy={isSending}
            message={message}
            onCancelDbWrite={onCancelDbWrite}
            onConfirmDbWrite={onConfirmDbWrite}
          />
        ))}
        <div ref={messagesEndRef} />
      </section>

      <form className="composer" onSubmit={handleSubmit}>
        <div className="composer-toolbar">
          <button
            type="button"
            className="image-button"
            disabled
            aria-label="圖片功能尚未啟用"
            title="圖片功能尚未啟用"
          >
            <Image size={17} />
            圖片功能尚未啟用
          </button>
        </div>
        <div className="composer-input-row">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="輸入訊息..."
            rows={2}
            aria-label="聊天輸入框"
            title="Enter 送出，Shift+Enter 換行"
            disabled={!chat || isSending}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!chat || isSending || !draft.trim()}
            aria-label="送出訊息"
            title="送出訊息"
          >
            <Send size={18} />
          </button>
        </div>
      </form>
    </main>
  )
}
