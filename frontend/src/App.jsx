import { useCallback, useEffect, useMemo, useState } from 'react'
import { MessageSquareText, SlidersHorizontal } from 'lucide-react'
import { ChatArea } from './components/ChatArea'
import { ControlPanel } from './components/ControlPanel'
import { Sidebar } from './components/Sidebar'
import './App.css'

const createTempId = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`

const wait = (ms) => new Promise((resolve) => {
  window.setTimeout(resolve, ms)
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

const apiRequest = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    const error = new Error(data.error || data.message || `HTTP ${response.status}`)
    error.status = response.status
    error.data = data
    throw error
  }

  return data
}

const fetchDbHealth = async () => apiRequest('/api/db/health')
const fetchLlmHealth = async () => apiRequest('/api/llm/health')
const fetchDbSummary = async () => {
  const data = await apiRequest('/api/db/summary')
  return data.summary
}
const fetchChatRooms = async () => {
  const data = await apiRequest('/api/chat/rooms')
  return data.rooms ?? []
}
const createChatRoom = async (title) => {
  const data = await apiRequest('/api/chat/rooms', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
  return data.room
}
const updateChatRoom = async (roomId, title) => {
  const data = await apiRequest(`/api/chat/rooms/${roomId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
  return data.room
}
const deleteChatRoom = async (roomId) => apiRequest(`/api/chat/rooms/${roomId}`, { method: 'DELETE' })
const fetchChatMessages = async (roomId) => {
  const data = await apiRequest(`/api/chat/rooms/${roomId}/messages`)
  return data
}
const sendChatMessage = async (roomId, payload) => {
  const data = await apiRequest(`/api/chat/rooms/${roomId}/messages`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return data
}

function App() {
  const [rooms, setRooms] = useState([])
  const [activeRoomId, setActiveRoomId] = useState(null)
  const [messages, setMessages] = useState([])
  const [roomsState, setRoomsState] = useState({ status: 'loading', error: '' })
  const [messagesState, setMessagesState] = useState({ status: 'idle', error: '' })
  const [isSending, setIsSending] = useState(false)
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
  const [llmHealth, setLlmHealth] = useState({
    state: 'checking',
    data: null,
    error: '',
  })
  const [theme, setTheme] = useState('light')
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isControlCollapsed, setIsControlCollapsed] = useState(false)
  const [mobileDrawer, setMobileDrawer] = useState(null)

  const activeRoom = useMemo(
    () => rooms.find((room) => room.id === activeRoomId) ?? null,
    [activeRoomId, rooms],
  )
  const activeChat = useMemo(
    () => (activeRoom ? { ...activeRoom, messages } : null),
    [activeRoom, messages],
  )

  const refreshDbStatus = useCallback(() => {
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
  }, [])

  const refreshDbSummary = useCallback(() => {
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
  }, [])

  const refreshLlmHealth = useCallback(() => {
    setLlmHealth({
      state: 'checking',
      data: null,
      error: '',
    })

    fetchLlmHealth()
      .then((data) => {
        setLlmHealth({
          state: 'ready',
          data: data.llm,
          error: '',
        })
      })
      .catch((error) => {
        setLlmHealth({
          state: 'error',
          data: error.data?.llm ?? null,
          error: error instanceof Error ? error.message : 'Unable to check LLM health',
        })
      })
  }, [])

  useEffect(() => {
    refreshDbStatus()
    refreshDbSummary()
    refreshLlmHealth()
  }, [refreshDbStatus, refreshDbSummary, refreshLlmHealth])

  useEffect(() => {
    let isCurrent = true

    setRoomsState({ status: 'loading', error: '' })
    fetchChatRooms()
      .then((loadedRooms) => {
        if (!isCurrent) {
          return
        }

        setRooms(loadedRooms)
        setActiveRoomId((currentActiveRoomId) => currentActiveRoomId ?? loadedRooms[0]?.id ?? null)
        setRoomsState({ status: 'ready', error: '' })
      })
      .catch((error) => {
        if (isCurrent) {
          setRoomsState({
            status: 'error',
            error:
              error.status === 404
                ? '找不到聊天室 API，請確認 Flask 後端已重啟。'
                : error instanceof Error
                  ? error.message
                  : 'Unable to load chat rooms',
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  useEffect(() => {
    if (!activeRoomId) {
      setMessages([])
      setMessagesState({ status: 'idle', error: '' })
      return
    }

    let isCurrent = true

    setMessagesState({ status: 'loading', error: '' })
    fetchChatMessages(activeRoomId)
      .then((data) => {
        if (!isCurrent) {
          return
        }

        setMessages(data.messages ?? [])
        setRooms((currentRooms) =>
          currentRooms.map((room) => (room.id === data.room?.id ? data.room : room)),
        )
        setMessagesState({ status: 'ready', error: '' })
      })
      .catch((error) => {
        if (isCurrent) {
          if (error.status === 404) {
            setRooms((currentRooms) => currentRooms.filter((room) => room.id !== activeRoomId))
            setActiveRoomId(null)
            setMessages([])
            setMessagesState({ status: 'idle', error: '' })
            return
          }

          setMessages([])
          setMessagesState({
            status: 'error',
            error: error instanceof Error ? error.message : 'Unable to load chat messages',
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [activeRoomId])

  const addChat = async () => {
    const title = `新聊天室 ${rooms.length + 1}`
    setRoomsState({ status: 'saving', error: '' })

    try {
      const room = await createChatRoom(title)
      setRooms((currentRooms) => [room, ...currentRooms])
      setActiveRoomId(room.id)
      setMessages([])
      setMobileDrawer(null)
      setRoomsState({ status: 'ready', error: '' })
    } catch (error) {
      setRoomsState({
        status: 'error',
        error: error instanceof Error ? error.message : 'Unable to create chat room',
      })
    }
  }

  const selectChat = (roomId) => {
    setActiveRoomId(roomId)
    setMobileDrawer(null)
  }

  const renameChat = async (roomId, title) => {
    const trimmedTitle = title.trim()

    if (!trimmedTitle) {
      return
    }

    const previousRooms = rooms
    setRooms((currentRooms) =>
      currentRooms.map((room) => (room.id === roomId ? { ...room, title: trimmedTitle } : room)),
    )
    setRoomsState({ status: 'saving', error: '' })

    try {
      const room = await updateChatRoom(roomId, trimmedTitle)
      setRooms((currentRooms) => currentRooms.map((item) => (item.id === room.id ? room : item)))
      setRoomsState({ status: 'ready', error: '' })
    } catch (error) {
      setRooms(previousRooms)
      setRoomsState({
        status: 'error',
        error: error instanceof Error ? error.message : 'Unable to rename chat room',
      })
    }
  }

  const deleteChat = async (roomId) => {
    const previousRooms = rooms
    const nextRooms = rooms.filter((room) => room.id !== roomId)

    setRooms(nextRooms)
    if (activeRoomId === roomId) {
      setActiveRoomId(nextRooms[0]?.id ?? null)
    }
    setRoomsState({ status: 'saving', error: '' })

    try {
      await deleteChatRoom(roomId)
      setRoomsState({ status: 'ready', error: '' })
    } catch (error) {
      setRooms(previousRooms)
      if (activeRoomId === roomId) {
        setActiveRoomId(roomId)
      }
      setRoomsState({
        status: 'error',
        error: error instanceof Error ? error.message : 'Unable to delete chat room',
      })
    }
  }

  const sendMessage = async (content) => {
    const trimmedContent = content.trim()

    if (!trimmedContent || !activeRoomId || isSending) {
      return
    }

    const pendingUserMessage = {
      id: createTempId('user'),
      role: 'user',
      content: trimmedContent,
      created_at: new Date().toISOString(),
    }
    const thinkingMessage = {
      id: createTempId('assistant'),
      role: 'assistant',
      content: '',
      isThinking: true,
      created_at: new Date().toISOString(),
    }

    setMessages((currentMessages) => [...currentMessages, pendingUserMessage, thinkingMessage])
    setMessagesState({ status: 'ready', error: '' })
    setIsSending(true)

    try {
      const [data] = await Promise.all([
        sendChatMessage(activeRoomId, {
          message: trimmedContent,
          model: controls.model,
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
        wait(2000),
      ])
      const savedMessages = data.messages ?? []

      setMessages((currentMessages) => [
        ...currentMessages.filter(
          (message) => message.id !== pendingUserMessage.id && message.id !== thinkingMessage.id,
        ),
        ...savedMessages,
      ])
      if (data.room) {
        setRooms((currentRooms) =>
          currentRooms
            .map((room) => (room.id === data.room.id ? data.room : room))
            .sort((left, right) => new Date(right.updated_at) - new Date(left.updated_at)),
        )
      }
    } catch (error) {
      const savedMessages = error.data?.messages ?? []
      const errorMessage = `LLM 目前無法回覆：${error instanceof Error ? error.message : 'unknown error'}`

      setMessages((currentMessages) =>
        savedMessages.length > 0
          ? [
              ...currentMessages.filter(
                (message) => message.id !== pendingUserMessage.id && message.id !== thinkingMessage.id,
              ),
              ...savedMessages,
              {
                ...thinkingMessage,
                content: errorMessage,
                isThinking: false,
              },
            ]
          : currentMessages.map((message) =>
              message.id === thinkingMessage.id
                ? {
                    ...message,
                    content: errorMessage,
                    isThinking: false,
                  }
                : message,
            ),
      )
      if (error.data?.room) {
        setRooms((currentRooms) =>
          currentRooms.map((room) => (room.id === error.data.room.id ? error.data.room : room)),
        )
      }
      setMessagesState({
        status: 'error',
        error: error instanceof Error ? error.message : 'Unable to send chat message',
      })
    } finally {
      setIsSending(false)
    }
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
        chats={rooms}
        activeChatId={activeRoomId}
        collapsed={isSidebarCollapsed}
        mobileOpen={mobileDrawer === 'chats'}
        roomsState={roomsState}
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
        isLoading={messagesState.status === 'loading'}
        isSending={isSending}
        error={messagesState.error || roomsState.error}
        onRefreshDbStatus={refreshDbStatus}
        onSendMessage={sendMessage}
      />

      <ControlPanel
        collapsed={isControlCollapsed}
        controls={controls}
        dbSummary={dbSummary}
        llmHealth={llmHealth}
        mobileOpen={mobileDrawer === 'controls'}
        onCloseMobile={() => setMobileDrawer(null)}
        onRefreshDbSummary={refreshDbSummary}
        onRefreshLlmHealth={refreshLlmHealth}
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
