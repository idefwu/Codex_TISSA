import { Bot, Image, Send, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

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
        {message.isThinking ? <TypingIndicator /> : message.content}
      </div>
    </article>
  )
}

export function ChatArea({ chat, onSendMessage }) {
  const [draft, setDraft] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat?.messages])

  const submitMessage = () => {
    const trimmedDraft = draft.trim()

    if (!trimmedDraft) {
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
        </div>
      </section>

      <section className="messages-pane" aria-label="聊天訊息">
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
          />
          <button type="submit" className="send-button" disabled={!draft.trim()} aria-label="送出訊息" title="送出訊息">
            <Send size={18} />
          </button>
        </div>
      </form>
    </main>
  )
}
