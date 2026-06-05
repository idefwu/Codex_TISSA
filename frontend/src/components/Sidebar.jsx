import { ChevronLeft, ChevronRight, Edit3, MessageSquarePlus, Moon, Settings, Sun, Trash2, X } from 'lucide-react'
import { useState } from 'react'

export function Sidebar({
  activeChatId,
  chats,
  collapsed,
  mobileOpen,
  onAddChat,
  onCloseMobile,
  onDeleteChat,
  onRenameChat,
  onSelectChat,
  onToggleCollapsed,
  onToggleTheme,
  theme,
}) {
  const [editingChatId, setEditingChatId] = useState(null)
  const [draftTitle, setDraftTitle] = useState('')
  const isCompact = collapsed && !mobileOpen

  const startRename = (chat) => {
    setEditingChatId(chat.id)
    setDraftTitle(chat.title)
  }

  const finishRename = () => {
    if (editingChatId) {
      onRenameChat(editingChatId, draftTitle)
    }

    setEditingChatId(null)
    setDraftTitle('')
  }

  const handleRenameKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      finishRename()
    }

    if (event.key === 'Escape') {
      setEditingChatId(null)
      setDraftTitle('')
    }
  }

  const confirmDelete = (chat) => {
    if (window.confirm(`刪除聊天室「${chat.title}」？`)) {
      onDeleteChat(chat.id)
    }
  }

  return (
    <aside className={`sidebar ${isCompact ? 'sidebar--collapsed' : ''} ${mobileOpen ? 'sidebar--mobile-open' : ''}`}>
      <div className="sidebar-header">
        {!isCompact ? (
          <>
            <div>
              <p className="panel-kicker">Workspace</p>
              <h1>DB Agent Chat</h1>
            </div>
            <button
              type="button"
              className="icon-button mobile-only"
              onClick={onCloseMobile}
              aria-label="關閉聊天室列表"
              title="關閉聊天室列表"
            >
              <X size={18} />
            </button>
          </>
        ) : null}
        <button
          type="button"
          className="icon-button desktop-only"
          onClick={onToggleCollapsed}
          aria-label={isCompact ? '展開聊天室列表' : '收合聊天室列表'}
          title={isCompact ? '展開聊天室列表' : '收合聊天室列表'}
        >
          {isCompact ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {isCompact ? null : (
        <>
          <button type="button" className="primary-action" onClick={onAddChat}>
            <MessageSquarePlus size={18} />
            新增聊天室
          </button>

          <nav className="chat-list" aria-label="聊天室列表">
            {chats.map((chat) => (
              <div className={`chat-item ${chat.id === activeChatId ? 'chat-item--active' : ''}`} key={chat.id}>
                {editingChatId === chat.id ? (
                  <input
                    className="chat-title-input"
                    value={draftTitle}
                    onBlur={finishRename}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    onKeyDown={handleRenameKeyDown}
                    autoFocus
                    aria-label="聊天室名稱"
                  />
                ) : (
                  <button type="button" className="chat-select" onClick={() => onSelectChat(chat.id)}>
                    {chat.title}
                    <span>{chat.messages.length} 則訊息</span>
                  </button>
                )}

                <div className="chat-actions">
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => startRename(chat)}
                    aria-label={`重新命名 ${chat.title}`}
                    title="重新命名"
                  >
                    <Edit3 size={15} />
                  </button>
                  <button
                    type="button"
                    className="icon-button danger-button"
                    onClick={() => confirmDelete(chat)}
                    aria-label={`刪除 ${chat.title}`}
                    title="刪除"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </nav>

          <div className="sidebar-footer">
            <button
              type="button"
              className="settings-button"
              onClick={onToggleTheme}
              aria-label="切換 Light / Dark Mode"
              title="切換 Light / Dark Mode"
            >
              <Settings size={18} />
              <span>設定</span>
              {theme === 'dark' ? <Moon size={17} /> : <Sun size={17} />}
            </button>
          </div>
        </>
      )}
    </aside>
  )
}
