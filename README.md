# Multi-Agent After-Sale v2

一个面向智能售后场景的多 Agent 应用，基于 `FastAPI + Vue3 + LangChain + MySQL + Chroma` 构建，围绕技术问答、服务站查询、地图导航、知识库增强回答和会话级记忆展开。

项目的核心目标不是做一个简单的聊天页面，而是把多智能体编排、RAG、持久化 Memory、用户登录与会话管理整合成一套可本地开发、可容器化部署、可继续扩展的完整工程。

## 核心能力

- 3 Agent 分层协作：总控调度 Agent、技术专家 Agent、服务业务 Agent
- 多级回退策略：知识库未命中、专家不可用、外部工具异常时自动降级
- 多路检索、多路召回 RAG：向量检索 + 标题检索 + 去重 + 重排
- 会话级持久化 Memory：基于 LangChain `SQLChatMessageHistory` + MySQL
- 登录注册与用户会话管理：支持多用户、多会话隔离
- 流式响应：后端通过 SSE 持续推送 Agent 执行结果
- Docker / Docker Compose / ACR 部署：支持本地构建和镜像仓库部署

## 项目架构

### 1. 多 Agent 层

项目当前采用 3 Agent 分层设计：

1. `Orchestrator Agent`
   负责意图识别、任务拆解、能力路由与工具调度
2. `Technical Agent`
   负责技术问答、操作指导、故障分析等问题
3. `Service Agent`
   负责服务站查询、位置解析、导航相关业务

其中总控 Agent 不直接处理所有业务，而是将请求动态转交给专家 Agent，从而降低提示词耦合和单 Agent 过载问题。

### 2. RAG 层

知识库服务独立部署，形成完整的检索增强生成链路：

- 文档采集 / 上传
- 文本切分
- 向量化写入 Chroma
- 多路检索
- 候选文档去重与重排
- 大模型基于召回上下文生成答案

当前检索策略不是单一路径向量检索，而是：

- 第一条路径：向量语义检索
- 第二条路径：标题匹配检索
- 最终融合：去重 + 重排

这种设计对垂直售后知识场景更稳，既能命中语义相近问题，也能命中标题高度贴合的问题。

### 3. Memory 层

项目使用 MySQL 持久化会话记忆：

- 聊天正文：存放在 `langchain_chat_messages`
- 会话元数据：存放在 `chat_sessions`

当前记忆链路具备这些特点：

- 用户消息在请求进入时立即写库
- assistant 消息在最终答案生成后写库
- 支持按 `session_id` 维度恢复多轮上下文
- 支持历史会话恢复
- 支持旧版 JSON 会话向 MySQL 平滑迁移

详细说明见：

- [MEMORY_GUIDE.md](./MEMORY_GUIDE.md)

## 目录结构

```text
.
├─ backend
│  ├─ app                    # 主应用：多 Agent、用户系统、Memory、API
│  ├─ knowledge              # 知识库服务：RAG 检索与生成
│  ├─ pyproject.toml
│  └─ uv.lock
├─ front
│  └─ agent_web_ui           # Vue3 前端
├─ deploy
│  ├─ docker                 # Dockerfile
│  ├─ env                    # 部署环境变量模板与实际部署配置
│  ├─ nginx                  # Nginx 网关配置
│  └─ README.md              # Docker 部署说明
├─ docker-compose.yml        # 本地源码构建部署
├─ docker-compose.acr.yml    # ACR / 镜像仓库部署
└─ README.md
```

## 技术栈

### 后端

- FastAPI
- OpenAI Agents SDK
- LangChain
- SQLAlchemy
- PyMySQL
- HTTPX

### 知识库 / RAG

- LangChain Chroma
- Chroma Vector Store
- OpenAI Compatible Embedding / Chat API
- Jieba
- scikit-learn

### 前端

- Vue 3
- Vite
- Element Plus

### 基础设施

- MySQL
- Docker
- Docker Compose
- Nginx

## 核心流程

### 技术问题处理链路

1. 前端请求 `/api/query`
2. 后端进入 `MultiAgentService`
3. `SessionService` 准备历史上下文并记录用户消息
4. `Orchestrator Agent` 判断是否转交技术专家
5. 技术链路优先做知识库预检索
6. 若知识命中，直接返回增强结果
7. 若未命中或失败，回退技术专家 Agent
8. 若专家结果不可用，再进入通用技术兜底链路
9. 最终回答写入 MySQL Memory

### 服务站 / 导航处理链路

1. `Orchestrator Agent` 将请求路由到服务业务 Agent
2. 先解析用户位置
3. 再查询最近维修站
4. 必要时通过地图 MCP 完成导航能力调用

## 快速开始

### 环境要求

- Python `3.12`
- Node.js `20+`
- MySQL `8.0`
- 推荐使用 `uv` 管理 Python 依赖

## 本地开发启动

### 1. 准备环境变量

请确保至少准备这些配置文件：

- `backend/app/.env`
- `backend/knowledge/.env`

如果你使用 Docker 部署，还需要：

- `deploy/env/core-api.env`
- `deploy/env/kb-api.env`
- `deploy/env/db.env`
- `deploy/env/images.env`（镜像仓库部署时）

### 2. 启动知识库服务

```bash
cd backend
uv sync
uv run python -m knowledge.api.main
```

默认访问：

```text
http://127.0.0.1:8001/docs
```

### 3. 启动主后端服务

```bash
cd backend
uv run python -m app.api.main
```

默认访问：

```text
http://127.0.0.1:8000/docs
```

### 4. 启动前端

```bash
cd front/agent_web_ui
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

## Docker 部署

### 镜像仓库 / ACR 部署

1. 先构建并推送镜像
2. 在服务器准备 `deploy/env/*.env`
3. 使用 `docker-compose.acr.yml` 启动

```bash
docker compose --env-file deploy/env/images.env -f docker-compose.acr.yml up -d
```

当前部署结构包括：

- `core-db`：MySQL
- `core-api`：主应用服务
- `retrieval-api`：知识库服务
- `edge-web`：Nginx + 前端

更详细的部署说明见：

- [deploy/README.md](./deploy/README.md)

## 数据库说明

当前核心表包括：

- `users`：用户信息
- `user_auth_tokens`：登录 Token
- `chat_sessions`：会话元数据
- `langchain_chat_messages`：聊天正文
- `repair_shops`：服务站数据

## 常用接口

### 认证

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### 会话

- `POST /api/user_sessions`
- `POST /api/query`

### 知识库

- `POST /upload`
- `POST /query`

## 项目特色

### 1. 不是单 Agent，而是分层协作

项目通过总控 Agent 做任务编排，而不是让一个大 Prompt 同时负责所有能力，从架构上提升了可维护性和扩展性。

### 2. 不是单路 RAG，而是多路召回

通过“向量检索 + 标题匹配”两路召回降低漏召回概率，再通过去重和重排提高最终答案质量。

### 3. 不是前端缓存历史，而是持久化会话记忆

刷新页面、重启服务后仍能恢复历史，这是因为会话状态已经落在 MySQL 中，而不是仅保存在浏览器或进程内存。

### 4. 不是只做 Demo，而是考虑工程部署

项目包含用户系统、数据库持久化、流式输出、Docker/ACR 部署和 Nginx 代理，具备真实应用交付的基本形态。

## 开发建议

如果你准备继续扩展这个项目，建议优先从这几个方向入手：

- 为 Memory 增加摘要压缩和长期记忆
- 为 RAG 增加更强的 rerank 或 query rewrite
- 为多 Agent 路由增加更细粒度的评估指标
- 为工具调用链路增加更完整的可观测性与埋点
- 为服务站导航加入更准确的用户真实位置透传

## 说明

- `.env`、部署私密配置、证书和密钥文件已加入 `.gitignore`
- 旧版 `backend/app/user_memories` 仅作为迁移来源，当前主要 Memory 已切换到 MySQL
- 如果需要查看 Memory 设计细节，请优先阅读 [MEMORY_GUIDE.md](./MEMORY_GUIDE.md)
