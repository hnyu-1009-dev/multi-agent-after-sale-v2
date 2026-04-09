<template>
  <div class="user-profile-card">
    <img :src="avatar" class="user-avatar" alt="当前用户头像" />
    <div class="user-info-dropdown">
      <div>
        <span class="user-profile-kicker">当前用户</span>
        <span class="user-name">{{ label }}</span>
      </div>
      <button class="btn-tertiary user-action-btn" @click="$emit('logout')">
        退出登录
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  avatar: {
    type: String,
    required: true
  },
  label: {
    type: String,
    required: true
  }
})

defineEmits(['logout'])
</script>

<style scoped>
.user-profile-card {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(17, 37, 63, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 12px 28px rgba(17, 37, 63, 0.08);
  backdrop-filter: blur(18px);
}

.user-avatar {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 16px;
  border: 1px solid rgba(17, 37, 63, 0.12);
  box-shadow: 0 10px 18px rgba(17, 37, 63, 0.08);
}

.user-info-dropdown {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.user-profile-kicker {
  display: block;
  margin-bottom: 2px;
  color: var(--ui-text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.user-name {
  display: block;
  color: var(--wh-navy-900);
  font-weight: 700;
  white-space: nowrap;
}

.user-action-btn {
  min-width: 96px;
  padding: 10px 14px;
}

@media (max-width: 768px) {
  .user-profile-card {
    width: 100%;
    justify-content: space-between;
  }

  .user-info-dropdown {
    flex: 1;
    justify-content: space-between;
  }
}
</style>
