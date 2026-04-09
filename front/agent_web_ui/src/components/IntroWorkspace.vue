<template>
  <div class="intro-workspace">
    <div class="workspace-user-section">
      <UserProfileBadge :avatar="userAvatar" :label="userLabel" @logout="$emit('logout')" />
    </div>
    <div class="intro-shell">
      <header class="intro-header">
        <div class="intro-header-copy">
          <span class="intro-kicker">功能介绍</span>
          <h2 class="intro-title">智慧百应售后服务平台能做什么</h2>
          <p class="intro-copy">
            本系统面向中文用户，提供售后问答、知识库检索与常见技术问题辅助说明，适合用于售后问题快速解答，线下维修服务引导和新用户快速上手。
          </p>
        </div>
        <div class="intro-badge">新用户上手页</div>
      </header>

      <section class="intro-grid">
        <article class="intro-card">
          <span class="card-kicker">系统能力</span>
          <h3>你可以用它完成这些事情</h3>
          <div class="mini-list">
            <div class="mini-item">
              <strong>售后问题咨询</strong>
              <span>输入设备故障、系统安装、使用疑问或操作异常，系统会给出中文说明与处理建议。</span>
            </div>
            <div class="mini-item">
              <strong>知识库内容检索</strong>
              <span>进入知识库查询页后，可根据问题或关键词检索已有资料，查看平台沉淀的知识内容。</span>
            </div>
            <div class="mini-item">
              <strong>对话记录回看</strong>
              <span>历史会话会保存在左侧列表中，方便回顾之前的问题、答案和排查思路。</span>
            </div>
          </div>
        </article>
        <article class="intro-card">
          <span class="card-kicker">输入例句</span>
          <h3>可以直接这样提问</h3>
          <div class="example-list">
            <div class="example-item">我想恢复出厂设置，操作前需要注意什么？</div>
            <div class="example-item">如何使用 U 盘安装 Windows7 操作系统？</div>
            <div class="example-item">开机蓝屏怎么办？</div>
            <div class="example-item">打印机无法连接网络，常见原因有哪些？</div>
            <div class="example-item">电脑开机后黑屏，但风扇还在转，应该怎么排查？</div>
            <div class="example-item">请帮我在知识库里查找主板故障的处理方法。</div>
          </div>
        </article>
        <article class="intro-card intro-card-wide">
          <span class="card-kicker">如何使用</span>
          <h3>首次使用建议按这个顺序体验</h3>
          <div class="path-list">
            <div class="path-step">
              <span class="step-index">1</span>
              <div>
                <strong>先确定你的目标</strong>
                <p>如果你想直接提问，请点击新建会话；如果你想查找已有资料，请进入知识库查询。</p>
              </div>
            </div>
            <div class="path-step">
              <span class="step-index">2</span>
              <div>
                <strong>用完整中文描述问题</strong>
                <p>尽量写清楚设备类型、当前现象、报错信息和你的目标，这样系统更容易给出准确回答。</p>
              </div>
            </div>
            <div class="path-step">
              <span class="step-index">3</span>
              <div>
                <strong>根据回复继续追问</strong>
                <p>如果第一轮答案不够具体，可以继续补充现场情况、系统版本或期望结果，系统会结合上下文继续回答。</p>
              </div>
            </div>
          </div>
          <div class="intro-actions">
            <button type="button" class="btn-primary intro-action-btn" @click="$emit('open-knowledge')">
              进入知识库查询
            </button>
            <button type="button" class="btn-secondary intro-action-btn" @click="$emit('start-chat')">
              开始新对话
            </button>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup>
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

defineEmits(['open-knowledge', 'start-chat', 'logout'])
</script>

<style scoped>
.intro-workspace {
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

.intro-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 100%;
  max-width: 1480px;
  margin: 0 auto;
  padding-top: clamp(74px, 9vw, 82px);
}

.intro-header,
.intro-card {
  border: 1px solid rgba(150, 112, 58, 0.12);
  border-radius: 30px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(247, 243, 235, 0.9));
  box-shadow: var(--ui-shadow-md);
  backdrop-filter: blur(16px);
}

.intro-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 28px;
}

.intro-header-copy {
  max-width: 760px;
}

.intro-kicker,
.card-kicker {
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--wh-red-500);
}

.intro-title,
.intro-card h3 {
  margin: 12px 0 10px;
  color: var(--wh-navy-900);
  font-family: "Georgia", "Times New Roman", serif;
  letter-spacing: -0.03em;
}

.intro-title {
  font-size: clamp(2rem, 2.8vw, 2.8rem);
}

.intro-copy,
.intro-card p,
.mini-item span {
  margin: 0;
  color: var(--ui-text-muted);
  line-height: 1.7;
}

.intro-badge {
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

.intro-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  gap: 18px;
}

.intro-card {
  padding: 24px;
}

.intro-card-wide {
  display: flex;
  flex-direction: column;
}

.path-list,
.mini-list,
.example-list {
  display: grid;
  gap: 14px;
  margin-top: 12px;
}

.path-step,
.mini-item,
.example-item {
  display: flex;
  gap: 14px;
  padding: 16px;
  border: 1px solid rgba(17, 37, 63, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.7);
}

.example-item {
  color: var(--wh-navy-900);
  line-height: 1.7;
}

.step-index {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--wh-navy-900), var(--wh-navy-800));
  color: #fff;
  font-size: 0.92rem;
  font-weight: 700;
}

.path-step strong,
.mini-item strong {
  display: block;
  margin-bottom: 4px;
  color: var(--wh-navy-900);
}

.intro-actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
  padding-top: 20px;
}

.intro-action-btn {
  min-width: 156px;
}

@media (max-width: 1100px) {
  .intro-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .workspace-user-section {
    position: static;
    margin-bottom: 16px;
  }

  .intro-shell {
    padding-top: 0;
  }

  .intro-header {
    flex-direction: column;
  }
}

@media (max-width: 768px) {
  .intro-workspace {
    padding: 22px 18px 20px;
  }

  .intro-header,
  .intro-actions {
    flex-direction: column;
  }

  .intro-card,
  .intro-header {
    border-radius: 24px;
  }

  .path-step,
  .mini-item,
  .example-item {
    padding: 14px;
  }
}

@media (max-width: 560px) {
  .intro-header,
  .intro-card {
    padding: 18px;
  }

  .intro-title {
    font-size: 1.8rem;
  }

  .intro-actions {
    gap: 10px;
  }

  .intro-action-btn {
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
