import { useEffect, useMemo, useRef, useState } from 'react'
import { MessageSquareText, SlidersHorizontal } from 'lucide-react'
import { ChatArea } from './components/ChatArea'
import { ControlPanel } from './components/ControlPanel'
import { Sidebar } from './components/Sidebar'
import './App.css'

const createId = () => {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID()
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const createAssistantMessage = (content, options = {}) => ({
  id: createId(),
  role: 'assistant',
  content,
  isThinking: false,
  ...options,
})

const createUserMessage = (content) => ({
  id: createId(),
  role: 'user',
  content,
})

const createChat = (title) => ({
  id: createId(),
  title,
  messages: [
    createAssistantMessage('你好，我是 DB Agent Chat 的前端原型。這一階段會先透過後端 mock API 回覆。'),
  ],
})

const initialControls = {
  model: 'gpt-4o',
  temperature: 0.4,
  systemPrompt: '你是協助查詢員工與財務資料的 AI Agent。',
  memoryRounds: 5,
  contextRouter: true,
  dbQuery: true,
  rag: false,
  imageSkill: false,
  auditLog: true,
}

const fetchDbHealth = async () => {
  const response = await fetch('/api/db/health')
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.error || data.message || `HTTP ${response.status}`)
  }

  return data
}

const fetchDbSummary = async () => {
  const response = await fetch('/api/db/summary')
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.error || data.message || `HTTP ${response.status}`)
  }

  return data.summary
}

function App() {
  const [workspace, setWorkspace] = useState(() => {
    const firstChat = createChat('課程助理')
    return {
      activeChatId: firstChat.id,
      chats: [firstChat],
    }
  })
  const [controls, setControls] = useState(initialControls)
  const [dbStatus, setDbStatus] = useState({
    state: 'checking',
    label: 'DB checking',
    detail: '',
  })
  const [dbSummary, setDbSummary] = useState({
    state: 'loading',
    data: null,
    error: '',
  })
  const [theme, setTheme] = useState('light')
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isControlCollapsed, setIsControlCollapsed] = useState(false)
  const [mobileDrawer, setMobileDrawer] = useState(null)
  const pendingTimersRef = useRef(new Set())

  const activeChat = useMemo(
    () => workspace.chats.find((chat) => chat.id === workspace.activeChatId) ?? workspace.chats[0],
    [workspace],
  )

  const refreshDbStatus = () => {
    setDbStatus({
      state: 'checking',
      label: 'DB checking',
      detail: '',
    })

    fetchDbHealth()
      .then((data) => {
        setDbStatus({
          state: 'connected',
          label: 'DB connected',
          detail: data.database?.version ? `MySQL ${data.database.version}` : 'Connected',
        })
      })
      .catch((error) => {
        setDbStatus({
          state: 'error',
          label: 'DB error',
          detail: error instanceof Error ? error.message : 'Database unavailable',
        })
      })
  }

  const refreshDbSummary = () => {
    setDbSummary({
      state: 'loading',
      data: null,
      error: '',
    })

    fetchDbSummary()
      .then((summary) => {
        setDbSummary({
          state: 'ready',
          data: summary,
          error: '',
        })
      })
      .catch((error) => {
        setDbSummary({
          state: 'error',
          data: null,
          error: error instanceof Error ? error.message : 'Unable to load DB summary',
        })
      })
  }

  useEffect(() => {
    let isCurrent = true

    fetchDbHealth()
      .then((data) => {
        if (isCurrent) {
          setDbStatus({
            state: 'connected',
            label: 'DB connected',
            detail: data.database?.version ? `MySQL ${data.database.version}` : 'Connected',
          })
        }
      })
      .catch((error) => {
        if (isCurrent) {
          setDbStatus({
            state: 'error',
            label: 'DB error',
            detail: error instanceof Error ? error.message : 'Database unavailable',
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  useEffect(() => {
    let isCurrent = true

    fetchDbSummary()
      .then((summary) => {
        if (isCurrent) {
          setDbSummary({
            state: 'ready',
            data: summary,
            error: '',
          })
        }
      })
      .catch((error) => {
        if (isCurrent) {
          setDbSummary({
            state: 'error',
            data: null,
            error: error instanceof Error ? error.message : 'Unable to load DB summary',
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  useEffect(() => {
    const pendingTimers = pendingTimersRef.current

    return () => {
      pendingTimers.forEach((timerId) => window.clearTimeout(timerId))
    }
  }, [])

  const addChat = () => {
    setWorkspace((current) => {
      const newChat = createChat(`新聊天室 ${current.chats.length + 1}`)
      return {
        activeChatId: newChat.id,
        chats: [newChat, ...current.chats],
      }
    })
    setMobileDrawer(null)
  }

  const selectChat = (chatId) => {
    setWorkspace((current) => ({
      ...current,
      activeChatId: chatId,
    }))
    setMobileDrawer(null)
  }

  const renameChat = (chatId, title) => {
    const trimmedTitle = title.trim()

    if (!trimmedTitle) {
      return
    }

    setWorkspace((current) => ({
      ...current,
      chats: current.chats.map((chat) => (chat.id === chatId ? { ...chat, title: trimmedTitle } : chat)),
    }))
  }

  const deleteChat = (chatId) => {
    setWorkspace((current) => {
      const nextChats = current.chats.filter((chat) => chat.id !== chatId)

      if (nextChats.length === 0) {
        const replacementChat = createChat('新聊天室 1')
        return {
          activeChatId: replacementChat.id,
          chats: [replacementChat],
        }
      }

      return {
        activeChatId: current.activeChatId === chatId ? nextChats[0].id : current.activeChatId,
        chats: nextChats,
      }
    })
  }

  const replaceThinkingMessage = (chatId, messageId, content) => {
    setWorkspace((current) => ({
      ...current,
      chats: current.chats.map((chat) =>
        chat.id === chatId
          ? {
              ...chat,
              messages: chat.messages.map((message) =>
                message.id === messageId
                  ? {
                      ...message,
                      content,
                      isThinking: false,
                    }
                  : message,
              ),
            }
          : chat,
      ),
    }))
  }

  const sendMessage = (content) => {
    const trimmedContent = content.trim()

    if (!trimmedContent || !activeChat?.id) {
      return
    }

    const chatId = activeChat.id
    const selectedModel = controls.model
    const userMessage = createUserMessage(trimmedContent)
    const thinkingMessage = createAssistantMessage('', { isThinking: true })

    setWorkspace((current) => ({
      ...current,
      chats: current.chats.map((chat) =>
        chat.id === chatId
          ? { ...chat, messages: [...chat.messages, userMessage, thinkingMessage] }
          : chat,
      ),
    }))

    const timerId = window.setTimeout(async () => {
      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: trimmedContent,
            model: selectedModel,
            temperature: controls.temperature,
            systemPrompt: controls.systemPrompt,
            memoryRounds: controls.memoryRounds,
            tools: {
              contextRouter: controls.contextRouter,
              dbQuery: controls.dbQuery,
              rag: controls.rag,
              imageSkill: controls.imageSkill,
              auditLog: controls.auditLog,
            },
          }),
        })
        const data = await response.json().catch(() => ({}))

        if (!response.ok) {
          throw new Error(data.message || `HTTP ${response.status}`)
        }

        replaceThinkingMessage(
          chatId,
          thinkingMessage.id,
          data.reply || `我收到你的訊息了：${trimmedContent}。下一階段會串接後端與 LLM。`,
        )
      } catch (error) {
        replaceThinkingMessage(
          chatId,
          thinkingMessage.id,
          `後端目前無法回覆：${error instanceof Error ? error.message : 'unknown error'}`,
        )
      } finally {
        pendingTimersRef.current.delete(timerId)
      }
    }, 2000)

    pendingTimersRef.current.add(timerId)
  }

  const updateControl = (name, value) => {
    setControls((current) => ({
      ...current,
      [name]: value,
    }))
  }

  const toggleTheme = () => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }

  return (
    <div className="app-shell" data-theme={theme}>
      <header className="mobile-topbar">
        <button
          type="button"
          className="icon-button"
          onClick={() => setMobileDrawer('chats')}
          aria-label="開啟聊天室列表"
          title="開啟聊天室列表"
        >
          <MessageSquareText size={18} />
        </button>
        <strong>DB Agent Chat</strong>
        <button
          type="button"
          className="icon-button"
          onClick={() => setMobileDrawer('controls')}
          aria-label="開啟控制面板"
          title="開啟控制面板"
        >
          <SlidersHorizontal size={18} />
        </button>
      </header>

      <Sidebar
        chats={workspace.chats}
        activeChatId={workspace.activeChatId}
        collapsed={isSidebarCollapsed}
        mobileOpen={mobileDrawer === 'chats'}
        theme={theme}
        onAddChat={addChat}
        onCloseMobile={() => setMobileDrawer(null)}
        onDeleteChat={deleteChat}
        onRenameChat={renameChat}
        onSelectChat={selectChat}
        onToggleCollapsed={() => setIsSidebarCollapsed((current) => !current)}
        onToggleTheme={toggleTheme}
      />

      <ChatArea
        chat={activeChat}
        dbStatus={dbStatus}
        onRefreshDbStatus={refreshDbStatus}
        onSendMessage={sendMessage}
      />

      <ControlPanel
        collapsed={isControlCollapsed}
        controls={controls}
        dbSummary={dbSummary}
        mobileOpen={mobileDrawer === 'controls'}
        onCloseMobile={() => setMobileDrawer(null)}
        onRefreshDbSummary={refreshDbSummary}
        onToggleCollapsed={() => setIsControlCollapsed((current) => !current)}
        onUpdateControl={updateControl}
      />

      <button
        type="button"
        className={`drawer-backdrop ${mobileDrawer ? 'drawer-backdrop--visible' : ''}`}
        onClick={() => setMobileDrawer(null)}
        aria-label="關閉抽屜"
      />
    </div>
  )
}

export default App
