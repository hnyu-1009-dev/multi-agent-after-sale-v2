# Memory 使用说明

## 1. 这套 Memory 的目标

这个项目现在的 memory 目标不是“做长期知识记忆推理”，而是把**用户会话历史**可靠地保存下来，并在下一轮对话时把最近几轮上下文重新喂给 Agent。

它主要解决 4 个问题：

1. 用户刷新页面后，历史消息还能恢复。
2. 服务重启后，历史消息不会丢失。
3. 多个会话可以分开管理，而不是所有消息混在一起。
4. 旧版保存在 `user_memories/*.json` 里的会话，可以平滑迁移到 MySQL。

## 2. 整体结构

当前 memory 由 3 层组成：

1. 消息正文层：`LangChainSessionMemory`
   位置：[langchain_session_memory.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/infrastructure/memory/langchain_session_memory.py)
   负责把 user / assistant 消息保存到 `langchain_chat_messages` 表。

2. 会话业务层：`SessionService`
   位置：[session_service.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/services/session_service.py)
   负责什么时候写消息、什么时候读消息、如何裁剪上下文、如何迁移旧数据。

3. 会话元数据层：`ChatSessionRepository`
   位置：[chat_session_repository.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/repositories/chat_session_repository.py)
   负责维护 `chat_sessions` 表里的会话列表信息，例如预览、更新时间、总消息数。

## 3. 数据存在哪里

### 3.1 聊天正文表

正文不在 `chat_sessions` 里，而是在 LangChain 使用的表中：

- 表名：`langchain_chat_messages`
- 作用：保存每一条 user / assistant 消息
- 分组方式：按 `session_id`

这张表由 `SQLChatMessageHistory` 使用。你可以理解为：

- `session_id` = 这个会话的主键
- 每条消息 = 这个会话下的一行记录

### 3.2 会话列表表

会话列表信息保存在：

- 表名：`chat_sessions`

它只存：

- `session_id`
- `user_id`
- `last_message_preview`
- `total_messages`
- `created_at`
- `updated_at`

所以：

- `chat_sessions` 用来给前端展示“有哪些会话”
- `langchain_chat_messages` 用来还原“每个会话里说了什么”

## 4. 一次对话时，memory 是怎么工作的

用户发一条新消息时，主链路大致是：

1. 前端调用 `/api/query`
   位置：[routers.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/api/routers.py)

2. 后端进入 `MultiAgentService.process_task(...)`
   位置：[agent_service.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/services/agent_service.py)

3. 在真正执行 Agent 前，会先调用：
   `session_service.prepare_history(...)`

4. 紧接着调用：
   `session_service.record_user_message(...)`

5. Agent 跑完，拿到最终答案后，再调用：
   `session_service.record_assistant_message(...)`

也就是说，现在的写入策略是：

- 用户消息：收到请求后立即写库
- assistant 消息：最终答案生成完成后写库

这就是你之前问到的“是不是实时写数据库”：

- 不是按 token 流式实时写
- 但已经是按消息级别的及时写入

## 5. prepare_history 做了什么

`prepare_history(...)` 是进入模型前最关键的方法之一。

它会做三件事：

1. 规范化 `session_id`
   如果前端没传，就使用默认的 `default_session`

2. 触发旧版 JSON 迁移
   如果当前会话在 MySQL 里还不存在，但旧版 JSON 文件存在，就先导入 MySQL

3. 生成模型上下文
   它会从数据库读取最近若干轮消息，再拼上：
   - system prompt
   - 最近 N 轮 user / assistant 消息
   - 当前这次 user 输入

最终产出的是标准的：

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "上一轮问题"},
  {"role": "assistant", "content": "上一轮回答"},
  {"role": "user", "content": "这一次的问题"}
]
```

## 6. 上下文裁剪是怎么做的

裁剪发生在：

- [langchain_session_memory.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/infrastructure/memory/langchain_session_memory.py)
- 方法：`build_context(...)`

关键参数：

- `max_turn`

逻辑是：

- 1 轮通常等于 2 条消息：`user + assistant`
- 所以代码里会截取最近 `max_turn * 2` 条消息

例如：

- `max_turn=3`
- 实际会保留最近 6 条消息
- 相当于保留最近 3 轮完整对话

这样做的目的：

1. 控制 prompt 大小
2. 避免历史越来越长导致模型变慢
3. 保留短期上下文，而不是无限堆叠全部历史

## 7. 为什么前端刷新后还能恢复历史

前端刷新后并不是直接从浏览器拿完整消息正文，而是：

1. 用本地保存的 token 恢复登录态
2. 调用 `/api/user_sessions`
3. 后端执行 `session_service.get_all_sessions_memory(user_id)`
4. 该方法从 `chat_sessions` 和 `langchain_chat_messages` 里重新组装会话列表和消息正文

所以历史能恢复的根本原因是：

- 历史已经持久化在 MySQL
- 前端刷新后重新从后端拉取

## 8. 旧版 JSON Memory 是怎么迁移的

旧版 memory 目录在：

- `backend/app/user_memories`

旧版仓库代码在：

- [session_repository.py](d:/WorkSystem/multi-agent-after-sale-v2/backend/app/repositories/session_repository.py)

迁移流程：

1. 当用户访问某个会话时，`SessionService` 会先检查 `chat_sessions` 里有没有这条会话
2. 如果没有，就尝试去旧版 JSON 目录里读同名会话文件
3. 如果找到了，就把其中的 `user` / `assistant` 消息导入 `langchain_chat_messages`
4. 同时补一条 `chat_sessions` 元数据

这个迁移是“按需迁移”，不是启动时全量扫描。

优点：

- 不需要一次性迁整个历史库
- 只有真正访问到的会话才会迁移
- 减少启动成本

## 9. 去重逻辑是怎么做的

当前项目做了两类去重：

### 9.1 用户消息去重

位置：`record_user_message(...)`

逻辑：

- 如果当前会话最后一条消息已经是同样内容的 `HumanMessage`
- 就不重复写入

这主要用于防止：

- 页面重放请求
- 前端误重复提交
- 某些重试路径造成的重复写库

### 9.2 assistant 消息去重

位置：`record_assistant_message(...)`

逻辑：

- 如果当前会话最后一条消息已经是同样内容的 `AIMessage`
- 就不重复写入

### 9.3 整轮去重

位置：`has_matching_tail(...)`

逻辑：

- 检查最后两条消息是否正好等于这次的 `user + assistant`
- 如果完全一致，就跳过整轮写入

这个主要服务于兼容旧的 `save_history(...)` 路径。

## 10. 这套 memory 的使用方式

### 10.1 最常用：准备上下文

```python
chat_history = session_service.prepare_history(
    user_id=user_id,
    session_id=session_id,
    user_input=user_query,
    max_turn=3,
)
```

适用场景：

- 准备发给 Agent / LLM 的上下文

### 10.2 记录用户消息

```python
session_service.record_user_message(user_id, session_id, user_query)
```

适用场景：

- 请求一进来就先把用户输入落库

### 10.3 记录 assistant 消息

```python
session_service.record_assistant_message(user_id, session_id, final_answer)
```

适用场景：

- 模型最终输出完成后，把答案落库

### 10.4 获取用户全部会话

```python
sessions = session_service.get_all_sessions_memory(user_id)
```

适用场景：

- 前端刷新页面后重新加载左侧会话列表和历史消息

### 10.5 读取单个会话历史

```python
history = session_service.load_history(user_id, session_id)
```

适用场景：

- 调试
- 单会话恢复
- 某些管理接口

## 11. 你在数据库里应该怎么看

### 11.1 看有哪些会话

```sql
SELECT session_id, user_id, last_message_preview, total_messages, created_at, updated_at
FROM chat_sessions
ORDER BY updated_at DESC;
```

### 11.2 看聊天正文

```sql
SELECT *
FROM langchain_chat_messages
ORDER BY id DESC
LIMIT 50;
```

### 11.3 看某个会话的全部消息

```sql
SELECT *
FROM langchain_chat_messages
WHERE session_id = '你的session_id'
ORDER BY id ASC;
```

## 12. 常见问题

### 12.1 为什么 `chat_sessions` 里有会话，但正文不多？

因为 `chat_sessions` 只存元数据，不存完整正文。正文在 `langchain_chat_messages`。

### 12.2 为什么页面能恢复历史，但浏览器本地没看到完整消息缓存？

因为历史不是主要靠浏览器本地存，而是刷新后重新从后端拉取。真正的数据源是 MySQL。

### 12.3 为什么用户消息先出现，assistant 消息后出现？

因为当前策略是：

- 用户消息在请求进入时立即入库
- assistant 消息在最终答案完成后入库

这是刻意设计出来的，目的是降低异常时的丢消息风险。

### 12.4 这套 memory 是不是 LangGraph 那种复杂长期记忆？

不是。

当前它本质上还是：

- 会话级消息历史持久化
- 最近几轮上下文裁剪
- 页面刷新 / 服务重启可恢复

它更像“可靠的会话记忆层”，不是“复杂的长期知识记忆系统”。

## 13. 如果你后续要继续增强 memory，可以从哪里下手

### 方向 1：流式增量写入 assistant 消息

现在 assistant 是在最终答案完成后一次写入。你后续可以改成：

- 流式输出时先缓冲 chunk
- 定时或结束时增量写入
- 支持更细粒度的恢复

### 方向 2：区分短期记忆和长期记忆

现在只有会话历史。以后可以拆成：

- 短期记忆：最近几轮对话
- 长期记忆：用户偏好、设备信息、常用地点等摘要信息

### 方向 3：做摘要压缩

当会话很长时，可以把较老的消息压缩成摘要，再和最近几轮一起送给模型。

### 方向 4：按用户做跨会话共享记忆

现在 memory 主要是按 `session_id` 隔离。以后可以增加一层“用户级摘要记忆”，让不同会话之间共享部分用户信息。

## 14. 你现在应该如何理解这套 memory

一句话总结：

- `langchain_chat_messages` 负责存“消息正文”
- `chat_sessions` 负责存“会话目录”
- `SessionService` 负责决定“什么时候写、写什么、怎么读、怎么迁移”
- Agent 每次只取最近几轮，而不是把全历史全部塞进 prompt

如果你后面继续改 memory，优先记住这条边界：

- **消息正文逻辑改 `LangChainSessionMemory`**
- **写入时机和会话编排改 `SessionService`**
- **会话列表字段改 `ChatSessionRepository`**
