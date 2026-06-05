import { Bot, Database, Image, RefreshCw, Send, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

const routeOptions = [
  { value: 'general_chat', label: 'General' },
  { value: 'db_query', label: 'DB Query' },
  { value: 'db_write', label: 'DB Write' },
  { value: 'rag', label: 'RAG' },
  { value: 'image_skill', label: 'Image' },
]

function TypingIndicator() {
  return (
    <span className="typing-indicator" aria-label="系統思考中">
      <span />
      <span />
      <span />
    </span>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'

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
          <MessageBubble key={message.id} message={message} />
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
