<template>
  <div class="knowledge-workspace">
    <div class="workspace-user-section">
      <UserProfileBadge :avatar="userAvatar" :label="userLabel" @logout="$emit('logout')" />
    </div>
    <div class="knowledge-shell">
      <header class="knowledge-header">
        <div>
          <span class="workspace-kicker">知识库工作台</span>
          <h2 class="workspace-title">统一管理知识检索与问答体验</h2>
          <p class="workspace-copy">
            当前保留知识库检索能力，方便继续做资料问答演示；文件上传入口暂时关闭，
            以保证向量数据库的安全和检索质量。
          </p>
        </div>
        <div class="workspace-badge">知识检索可用</div>
      </header>

      <div class="workspace-tabs" role="tablist" aria-label="知识库工作台标签">
        <button
          type="button"
          class="workspace-tab workspace-tab-disabled"
          @click="handleManageTabClick"
        >
          知识库管理
        </button>
        <button
          type="button"
          class="workspace-tab"
          :class="{ active: activeTab === 'chat' }"
          @click="activeTab = 'chat'"
        >
          知识库检索
        </button>
      </div>

      <section class="workspace-panel chat-panel">
        <div class="hero-strip compact">
          <div>
            <span class="panel-kicker">功能说明</span>
            <h3 class="panel-title">文件上传功能已临时关闭</h3>
            <p class="panel-copy">
              为了保证向量数据库的安全和检索质量，暂时关闭文件上传功能。
              你仍然可以继续使用知识库检索能力，对现有知识内容进行提问与回答。
            </p>
          </div>
          <button type="button" class="hero-notice-btn" @click="handleManageTabClick">
            查看关闭说明
          </button>
        </div>

        <div class="chat-surface">
          <div class="chat-notice">
            <span class="chat-notice-badge">提示</span>
            <span>{{ closedNotice }}</span>
          </div>

          <div ref="messagesRef" class="chat-messages">
            <div v-if="messages.length === 0" class="chat-empty">
              <div class="empty-badge">知识库检索</div>
              <h4>围绕知识库中已有知识内容回答您提出的问题</h4>
<!--              <p>例如输入产品维修步骤、售后政策说明或操作规范，系统会尝试基于知识库给出回答。</p>-->
            </div>

            <div
              v-for="(msg, index) in messages"
              :key="index"
              class="chat-item"
              :class="msg.role"
            >
              <div class="chat-avatar">{{ msg.role === 'user' ? '问' : '答' }}</div>
              <div class="chat-bubble">
                <div v-if="msg.loading" class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
                <div v-else class="chat-markdown" v-html="formatContent(msg.content)"></div>
              </div>
            </div>
          </div>

          <div class="chat-input-area">
            <el-input
              v-model="input"
              type="textarea"
              resize="none"
              :rows="3"
              placeholder="请输入想检索的知识问题..."
              @keydown.enter.prevent="handleSend"
            />
            <el-button
              type="primary"
              class="chat-send-btn"
              :loading="loading"
              :disabled="!input.trim()"
              @click="handleSend"
            >
              立即检索
            </el-button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { queryKnowledge } from '../api/knowledge'
import UserProfileBadge from './UserProfileBadge.vue'

defineProps({
  userAvatar: {
    type: String,
    required: true
  },
  userLabel: {
    type: String,
    required: true
  }
})

defineEmits(['logout'])

marked.setOptions({
  breaks: true,
  gfm: true
})

const closedNotice = '为了保证向量数据库的安全和检索质量，暂时关闭文件上传功能。'

const activeTab = ref('chat')
const input = ref('')
const loading = ref(false)
const messages = ref([])
const messagesRef = ref(null)

const handleManageTabClick = () => {
  activeTab.value = 'chat'
  ElMessage.warning(closedNotice)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const formatContent = (text) => {
  try {
    return marked.parse(text || '')
  } catch (error) {
    return text || ''
  }
}

const handleSend = async () => {
  if (!input.value.trim() || loading.value) return

  const question = input.value.trim()
  input.value = ''

  messages.value.push({
    role: 'user',
    content: question
  })
  scrollToBottom()

  loading.value = true
  messages.value.push({
    role: 'assistant',
    content: '',
    loading: true
  })
  scrollToBottom()

  try {
    const response = await queryKnowledge({ question })
    const lastMessage = messages.value[messages.value.length - 1]
    lastMessage.loading = false
    lastMessage.content = response.answer || '暂未检索到明确结果，请尝试补充更多关键词。'
  } catch (error) {
    const lastMessage = messages.value[messages.value.length - 1]
    lastMessage.loading = false
    lastMessage.content = error.message || '知识检索请求失败，请稍后重试。'
  } finally {
    loading.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
.knowledge-workspace {
  height: 100%;
  min-height: 0;
  padding: clamp(20px, 3vw, 28px) clamp(18px, 3vw, 32px) clamp(24px, 3vw, 32px);
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

.workspace-user-section {
  position: absolute;
  top: clamp(20px, 3vw, 28px);
  right: clamp(18px, 3vw, 32px);
  z-index: 3;
}

.knowledge-shell {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  gap: 18px;
  max-width: 1480px;
  margin: 0 auto;
  padding-top: clamp(74px, 9vw, 82px);
}

.knowledge-header,
.chat-surface {
  border: 1px solid rgba(150, 112, 58, 0.12);
  border-radius: 30px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(247, 243, 235, 0.9));
  box-shadow: var(--ui-shadow-md);
  backdrop-filter: blur(16px);
}

.knowledge-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 28px;
}

.workspace-kicker,
.panel-kicker {
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--wh-red-500);
}

.workspace-title,
.panel-title {
  margin: 12px 0 10px;
  color: var(--wh-navy-900);
  font-family: "Georgia", "Times New Roman", serif;
  letter-spacing: -0.03em;
}

.workspace-title {
  font-size: clamp(1.9rem, 2.6vw, 2.6rem);
}

.workspace-copy,
.panel-copy {
  margin: 0;
  color: var(--ui-text-muted);
  line-height: 1.7;
}

.workspace-badge {
  flex-shrink: 0;
  padding: 10px 16px;
  border: 1px solid rgba(17, 37, 63, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--wh-navy-900);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.workspace-tabs {
  display: inline-flex;
  gap: 10px;
  padding: 6px;
  width: fit-content;
  border: 1px solid rgba(17, 37, 63, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  box-shadow: var(--ui-shadow-sm);
}

.workspace-tab {
  min-width: 148px;
  padding: 11px 18px;
  border-radius: 999px;
  background: transparent;
  color: var(--ui-text-muted);
  font-weight: 600;
  transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.workspace-tab.active {
  background: linear-gradient(135deg, var(--wh-navy-900), var(--wh-navy-800));
  color: #fff;
  box-shadow: 0 12px 24px rgba(17, 37, 63, 0.16);
}

.workspace-tab-disabled {
  opacity: 0.72;
  border: 1px dashed rgba(17, 37, 63, 0.16);
}

.workspace-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 24px 28px;
  border: 1px solid rgba(150, 112, 58, 0.12);
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(247, 243, 235, 0.9));
  box-shadow: var(--ui-shadow-md);
}

.hero-strip.compact {
  padding-bottom: 18px;
}

.hero-notice-btn {
  min-width: 144px;
  padding: 12px 18px;
  border: 1px solid rgba(166, 31, 45, 0.16);
  border-radius: 999px;
  background: rgba(166, 31, 45, 0.08);
  color: var(--wh-red-700);
  font-weight: 700;
}

.chat-surface {
  display: flex;
  flex-direction: column;
  min-height: clamp(480px, 62vh, 620px);
  overflow: hidden;
}

.chat-notice {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 26px 0;
  color: var(--ui-text-muted);
  font-size: 14px;
}

.chat-notice-badge {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(166, 31, 45, 0.08);
  color: var(--wh-red-700);
  font-size: 12px;
  font-weight: 700;
}

.chat-messages {
  flex: 1;
  min-height: 0;
  padding: 26px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.chat-empty {
  margin: auto;
  max-width: 560px;
  text-align: center;
}

.empty-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(17, 37, 63, 0.05);
  color: var(--wh-red-500);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.chat-empty h4 {
  margin: 18px 0 10px;
  color: var(--wh-navy-900);
  font-family: "Georgia", "Times New Roman", serif;
  font-size: 2rem;
}

.chat-empty p {
  margin: 0;
  color: var(--ui-text-muted);
  line-height: 1.75;
}

.chat-item {
  display: flex;
  gap: 14px;
}

.chat-item.user {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--wh-navy-900), var(--wh-navy-800));
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.chat-bubble {
  max-width: min(78%, 760px);
  padding: 18px 20px;
  border: 1px solid rgba(17, 37, 63, 0.08);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: var(--ui-shadow-sm);
}

.chat-item.user .chat-bubble {
  background: linear-gradient(180deg, var(--wh-navy-800), var(--wh-navy-900));
  color: #fff;
}

.chat-markdown :deep(*) {
  margin-top: 0;
}

.chat-markdown :deep(pre) {
  overflow-x: auto;
}

.chat-input-area {
  padding: 20px 26px 26px;
  border-top: 1px solid rgba(17, 37, 63, 0.08);
  background: rgba(255, 255, 255, 0.58);
}

.chat-input-area :deep(.el-textarea__inner) {
  border-radius: 22px;
  box-shadow: none;
  padding: 18px 20px;
  line-height: 1.7;
}

.chat-send-btn {
  margin-top: 14px;
  min-width: 140px;
  border-radius: 999px;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(17, 37, 63, 0.42);
  animation: pulse 1s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes pulse {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }

  50% {
    transform: translateY(-2px);
    opacity: 1;
  }
}

@media (max-width: 1100px) {
  .hero-strip {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 1024px) {
  .workspace-user-section {
    position: static;
    margin-bottom: 16px;
  }

  .knowledge-shell {
    padding-top: 0;
  }

  .knowledge-header {
    flex-direction: column;
  }

  .chat-surface {
    min-height: 520px;
  }
}

@media (max-width: 768px) {
  .knowledge-workspace {
    padding: 22px 18px 20px;
  }

  .workspace-tabs {
    width: 100%;
    justify-content: space-between;
  }

  .workspace-tab {
    flex: 1;
    min-width: 0;
  }

  .chat-messages,
  .chat-input-area {
    padding-left: 18px;
    padding-right: 18px;
  }

  .chat-notice {
    padding-left: 18px;
    padding-right: 18px;
    align-items: flex-start;
    flex-direction: column;
  }

  .chat-bubble {
    max-width: 100%;
  }

  .knowledge-header,
  .hero-strip,
  .chat-surface {
    border-radius: 24px;
  }
}

@media (max-width: 560px) {
  .knowledge-header,
  .hero-strip {
    padding: 18px;
  }

  .workspace-title {
    font-size: 1.8rem;
  }

  .workspace-tabs {
    gap: 8px;
    padding: 4px;
  }

  .workspace-tab {
    padding: 10px 12px;
    font-size: 0.95rem;
  }

  .chat-messages,
  .chat-input-area {
    padding-left: 14px;
    padding-right: 14px;
  }

  .chat-item {
    gap: 10px;
  }

  .chat-avatar {
    width: 34px;
    height: 34px;
    flex-basis: 34px;
    border-radius: 12px;
  }

  .chat-bubble {
    padding: 14px 16px;
  }

  .chat-send-btn {
    width: 100%;
    min-width: 0;
  }
}

@media (max-width: 900px) {
  .workspace-user-section {
    display: none;
  }
}
</style>
