# AGENTS.md — Nocturne Memory 项目上下文

> 本文件为 AI Agent（Copilot / Antigravity / Cursor / Claude 等）提供项目全局上下文。
> 任何 Agent 在参与本项目的开发前，应先阅读此文件。

---

## 1. 项目概述

**Nocturne Memory** 是一个基于 MCP (Model Context Protocol) 的 AI Agent 长期记忆服务器。核心理念是"第一人称记忆主权"——AI 自主决定记什么、怎么组织，人类通过 Dashboard 审计和回滚。

- **版本**: v1.2.0（当前）→ v2.0.0（优化目标）
- **协议**: MIT
- **仓库**: https://github.com/Fu0000/AI-Agent-Memory

---

## 2. 项目结构

```
nocturne_memory/
├── backend/                        # Python 后端 (FastAPI + MCP)
│   ├── main.py                     # FastAPI 应用入口 (v1.2.0)
│   ├── mcp_server.py               # MCP 协议服务器 (1122 行, 7 个 MCP Tools)
│   ├── mcp_wrapper.py              # Windows CRLF 兼容层
│   ├── run_sse.py                  # SSE 传输启动脚本
│   ├── auth.py                     # Bearer Token ASGI 中间件
│   ├── health.py                   # /health 健康检查端点
│   ├── requirements.txt            # Python 依赖
│   ├── Dockerfile                  # 后端 Docker 构建
│   ├── api/                        # REST API 路由
│   │   ├── browse.py               # 记忆浏览 API (258 行)
│   │   ├── review.py               # 审查与回滚 API (908 行, 最复杂)
│   │   ├── maintenance.py          # 孤儿记忆清理 API (51 行)
│   │   └── utils.py                # Diff 工具函数
│   ├── db/                         # 数据库层
│   │   ├── sqlite_client.py        # 异步 ORM 客户端 (2250 行, 核心)
│   │   ├── snapshot.py             # Changeset 快照存储 (357 行)
│   │   ├── neo4j_client.py         # Neo4j 旧版客户端 (仅迁移用)
│   │   └── migrations/             # 数据库迁移脚本
│   │       ├── runner.py           # 迁移执行引擎
│   │       ├── 001_*.py ~ 008_*.py # 8 个迁移脚本
│   ├── models/
│   │   └── schemas.py              # Pydantic 数据模型 (67 行)
│   └── scripts/
│       └── migrate_neo4j_to_sqlite.py
├── frontend/                       # React 前端 (Vite + TailwindCSS)
│   ├── package.json                # React 18 + Vite 7 + TailwindCSS 3
│   ├── nginx.conf                  # Nginx 反向代理 (Docker 用)
│   ├── Dockerfile                  # 前端 Docker 构建
│   └── src/
│       ├── App.jsx                 # 路由 + Token 鉴权状态管理
│       ├── lib/api.js              # HTTP 客户端封装
│       ├── components/             # 通用组件 (DiffViewer, TokenAuth 等)
│       └── features/
│           ├── memory/             # Memory Explorer 页面
│           ├── review/             # Review & Audit 页面
│           └── maintenance/        # Brain Cleanup 页面
├── docs/                           # 文档
│   ├── TOOLS.md                    # MCP 工具参考文档
│   ├── system_prompt.md            # AI 行为指导 System Prompt (167 行)
│   ├── nocturne_memory_analysis.md # 项目全面分析报告
│   ├── deep_evaluation.md          # 深度评估报告
│   ├── optimization_roadmap.md     # 生产化优化清单
│   ├── PLAN.md                     # ★ 工程优化执行计划 (任务跟踪)
│   └── images/                     # 架构图, 截图
├── docker-compose.yml              # 4 服务编排 (postgres + api + sse + nginx)
├── .env.example                    # 环境变量模板
├── demo.db                         # SQLite 示例数据库
├── AGENTS.md                       # ★ 本文件
└── README.md                       # 项目文档 (632 行, 中文)
```

---

## 3. 技术栈

### 后端

| 技术 | 版本 | 用途 |
|---|---|---|
| Python | 3.10+ | 运行时 |
| FastAPI | ≥0.109 | REST API 框架 |
| SQLAlchemy | ≥2.0 (async) | ORM，支持 SQLite + PostgreSQL |
| aiosqlite | ≥0.19 | SQLite 异步驱动 |
| asyncpg | ≥0.29 | PostgreSQL 异步驱动 |
| MCP SDK | ≥0.1.0 | Model Context Protocol |
| pyahocorasick | ≥2.0 | 豆辞典多模式匹配 |
| uvicorn | ≥0.27 | ASGI 服务器 |

### 前端

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 18.2 | UI 框架 |
| Vite | 7.3 | 构建工具 |
| TailwindCSS | 3.3 | 样式 |
| React Router | 6.20 | 前端路由 |
| Axios | 1.6 | HTTP 客户端 |
| Lucide React | 0.290 | 图标库 |

---

## 4. 核心架构概念

### 4.1 数据模型 (5 实体)

| 实体 | 表名 | 职责 | 关键字段 |
|---|---|---|---|
| **Node** | `nodes` | 概念的永久锚点 (UUID) | `uuid` (PK) |
| **Memory** | `memories` | 内容版本 | `node_uuid` (FK), `content`, `deprecated`, `migrated_to` |
| **Edge** | `edges` | 有向关系 (parent→child) | `parent_uuid`, `child_uuid`, `name`, `priority`, `disclosure` |
| **Path** | `paths` | URI 路由缓存 | `domain` (PK), `path` (PK), `edge_id` (FK) |
| **GlossaryKeyword** | `glossary_keywords` | 触发词绑定 | `keyword`, `node_uuid` (FK) |

**核心原则**: Node UUID 不变 → 内容更新创建新 Memory，旧的标记 `deprecated`。Edge/Path 引用 Node UUID，所以更新内容不影响图结构。

### 4.2 ORM 分层架构

`sqlite_client.py` 采用严格的 4 层分层：

| 层 | 方法前缀 | 职责 | 事务管理 |
|---|---|---|---|
| Layer 0 | `_ensure_*`, `_insert_*`, `_resolve_*` | 单行/单表原语 | 接收 session，不开事务 |
| Layer 1 | `_deprecate_*`, `_safely_delete_*`, `_get_subtree_*` | 多行表域操作 | 接收 session |
| Layer 2 | `_cascade_delete_*`, `_create_edge_with_*` | 跨表级联 | 接收 session |
| Layer 3 | `create_memory`, `update_memory`, `remove_path` | 业务操作 | 自行管理事务 |

> **重要**: 修改 ORM 代码时必须遵循此分层。低层方法不得直接调用高层方法。

### 4.3 MCP Tools (7 个)

| 工具 | 读/写 | 核心行为 |
|---|---|---|
| `read_memory` | 读 | 支持 5 种 `system://` 虚拟路由；正文自动附加 Glossary 超链接 |
| `create_memory` | 写 | 四表联创 (Node+Memory+Edge+Path)；返回后提醒绑定触发词 |
| `update_memory` | 写 | **仅 Patch/Append 模式，禁止全量替换**；旧版本 deprecated |
| `delete_memory` | 写 | 只删路径，不删内容；级联删子路径 |
| `add_alias` | 写 | 同一内容多个入口；跨域别名 |
| `manage_triggers` | 写 | 绑定/解绑 Glossary 关键词 |
| `search_memory` | 读 | SQL LIKE 子字符串匹配 |

### 4.4 系统特殊 URI

- `system://boot` — 启动引导，加载 `CORE_MEMORY_URIS` 指定的核心记忆
- `system://index` / `system://index/<domain>` — 全量/分域路径索引
- `system://recent` — 最近修改的记忆
- `system://glossary` — 豆辞典全量映射

> 这些 URI 不存在于数据库中，在 `mcp_server.py` 中硬编码拦截处理。

---

## 5. 开发环境设置

### 本地开发 (SQLite 模式)

```bash
# 1. 后端
cd backend
cp ../.env.example ../.env          # 编辑 .env 设置 DATABASE_URL
pip install -r requirements.txt
python -m uvicorn main:app --port 8000 --reload

# 2. 前端
cd frontend
npm install
npm run dev                          # 默认 http://localhost:5173

# 3. MCP Server (stdio 模式，供 Claude/Cursor 使用)
cd backend
python mcp_server.py
```

### Docker 部署 (PostgreSQL 模式)

```bash
cp .env.example .env                 # 编辑 .env 设置 PostgreSQL 和 API_TOKEN
docker-compose up -d
# 前端: http://localhost:80
# API:  http://localhost:80/api/
# SSE:  http://localhost:80/sse
```

---

## 6. 关键配置 (.env)

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `DATABASE_URL` | ✓ | SQLite demo | 数据库连接 URL |
| `VALID_DOMAINS` | ✗ | `core,writer,game,notes` | 允许的 URI 域名空间 |
| `CORE_MEMORY_URIS` | ✗ | `core://agent,...` | `system://boot` 加载的记忆 |
| `API_TOKEN` | ✗ | *(空=关闭)* | Bearer Token 鉴权 |
| `SNAPSHOT_DIR` | ✗ | `./snapshots` | Changeset 存储目录 |

---

## 7. 工程优化执行计划

### 7.1 计划文档

所有优化工作以 **[docs/PLAN.md](docs/PLAN.md)** 为唯一真相源 (single source of truth)。

- 优化项编号: `OPT-1` ~ `OPT-8`
- 子任务编号: `OPT-1.1`, `OPT-1.2`, ...
- 每项含: 任务描述、完成标准、checkbox 状态

### 7.2 优化项总览

| 编号 | 名称 | 优先级 | Phase |
|---|---|---|---|
| OPT-1 | 自动化测试覆盖 | P0 | Phase 1 (Week 1-2) |
| OPT-2 | Changeset 迁移到数据库 | P0 | Phase 1 |
| OPT-3 | 混合搜索层 (语义+精确) | P1 | Phase 2 (Week 3-4) |
| OPT-4 | 自动回忆注入机制 | P1 | Phase 2 |
| OPT-5 | 多租户隔离 | P1 | Phase 3 (Week 5-6) |
| OPT-6 | System Prompt 行为内化 | P2 | Phase 3 |
| OPT-7 | 可观测性与指标 | P2 | Phase 4 (Week 7-8) |
| OPT-8 | API 限流与幂等 | P2 | Phase 4 |

### 7.3 每次更新流程

完成一个子任务后，执行以下标准流程：

```
1. 编码       → 在对应目录编写/修改代码
2. 测试       → 确保既有测试通过 + 新增测试覆盖变更
3. PLAN.md    → 勾选完成的 checkbox，在更新日志追加记录
4. Git 提交   → 使用规范的 commit message (见下方)
5. Git 推送   → push 到 origin/main
```

---

## 8. Git 提交规范

### 8.1 Commit Message 格式

```
<type>(<scope>): <subject>

[body]

[footer]
```

| type | 含义 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat(search): add semantic embedding layer` |
| `fix` | 修 bug | `fix(orm): repair version chain on middle deletion` |
| `refactor` | 重构 | `refactor(snapshot): migrate changeset to database` |
| `test` | 测试 | `test(orm): add cycle detection tests (10 cases)` |
| `docs` | 文档 | `docs: update PLAN.md with OPT-1.2 completion` |
| `chore` | 构建/配置 | `chore: add pytest to requirements.txt` |
| `perf` | 性能 | `perf(glossary): optimize Aho-Corasick cache invalidation` |

### 8.2 Scope 约定

| scope | 对应目录/模块 |
|---|---|
| `orm` | `backend/db/sqlite_client.py` |
| `mcp` | `backend/mcp_server.py` |
| `snapshot` | `backend/db/snapshot.py` |
| `review` | `backend/api/review.py` |
| `browse` | `backend/api/browse.py` |
| `auth` | `backend/auth.py` |
| `search` | 搜索相关 (OPT-3) |
| `recall` | 自动回忆 (OPT-4) |
| `tenant` | 多租户 (OPT-5) |
| `metrics` | 可观测性 (OPT-7) |
| `frontend` | `frontend/src/` |
| `docker` | Docker 相关配置 |

### 8.3 Footer 中标注优化项

每个与 PLAN.md 相关的提交，在 footer 中标注对应的优化项编号：

```
test(orm): add cycle detection and cascade delete tests

- test_cycle_detection_self_loop: A→A denied
- test_cycle_detection_indirect: A→B→C, C→A denied
- test_cascade_delete_cleans_all: 4-table cascade verified

Refs: OPT-1.2
```

---

## 9. 数据库迁移规范

### 新增迁移脚本

```
backend/db/migrations/
├── 001_v1.0.0_add_migrated_to.py
├── ...
├── 008_v1.2.0_add_glossary_keywords.py
├── 009_v2.0.0_add_changeset_table.py    ← 新增格式
└── runner.py                             ← 迁移引擎
```

**命名规则**: `{序号}_v{版本}_{描述}.py`

**迁移脚本结构**:
```python
"""描述"""

async def migrate(engine):
    async with engine.begin() as conn:
        # 检查是否已迁移
        # 执行 DDL
        # 回填数据 (如需)
```

### 迁移安全守则

- 迁移引擎会在执行前自动备份 SQLite 数据库
- **禁止**: 在迁移中删除有数据的列（先新列 → 回填 → 下个版本再删旧列）
- **必须**: 每个迁移脚本内置幂等检查（重复执行不报错）

---

## 10. 编码规范

### Python 后端

- **异步优先**: 所有数据库操作使用 `async/await`
- **类型注解**: 所有函数签名需要 type hints
- **Session 管理**: 使用 `async with self.session() as session` 上下文管理器
- **ORM 分层**: 严格遵循 Layer 0-3 分层（见 §4.2）
- **错误处理**: 业务错误抛 `ValueError`；权限错误抛 `PermissionError`；框架错误让它自然传播

### React 前端

- **组件**: 函数式组件 + Hooks
- **样式**: TailwindCSS utility classes
- **状态**: useState/useEffect，无 Redux
- **API**: 统一走 `lib/api.js` 封装的 axios 实例

### 通用

- **缩进**: Python 4 空格，JS/JSX 2 空格
- **引号**: Python 双引号 `"`，JS 双引号 `"`
- **文件编码**: UTF-8，LF 换行

---

## 11. 测试规范 (OPT-1 建立后生效)

### 测试目录

```
backend/tests/
├── conftest.py              # 共享 fixture (内存 SQLite)
├── test_sqlite_client.py    # ORM 层 (~40 cases)
├── test_mcp_tools.py        # MCP 工具 (~20 cases)
├── test_review.py           # 审查/回滚 (~15 cases)
└── test_auth.py             # 鉴权 (~8 cases)
```

### 运行测试

```bash
cd backend
pip install pytest pytest-asyncio
pytest -v                    # 全部测试
pytest tests/test_sqlite_client.py -v    # 单文件
pytest -k "cycle"            # 按关键词筛选
```

### 测试原则

- **每个 OPT 子任务必须附带对应测试**
- **禁止**: 测试依赖外部服务或网络
- **Fixture**: 使用内存 SQLite (`sqlite+aiosqlite:///:memory:`)，每个测试完全隔离
- **命名**: `test_{功能}_{场景}` (e.g. `test_cycle_detection_prevents_indirect_loop`)

---

## 12. 参考文档

| 文档 | 路径 | 说明 |
|---|---|---|
| **工程执行计划** | [docs/PLAN.md](docs/PLAN.md) | 优化任务跟踪 (★ 最常更新) |
| **项目分析报告** | [docs/nocturne_memory_analysis.md](docs/nocturne_memory_analysis.md) | 全面技术分析 |
| **深度评估** | [docs/deep_evaluation.md](docs/deep_evaluation.md) | 优劣势批判性分析 |
| **优化路线图** | [docs/optimization_roadmap.md](docs/optimization_roadmap.md) | 优化方案详细设计 |
| **MCP 工具文档** | [docs/TOOLS.md](docs/TOOLS.md) | 7 个 MCP Tool 参考 |
| **System Prompt** | [docs/system_prompt.md](docs/system_prompt.md) | AI 行为指导 (167 行) |
| **README** | [README.md](README.md) | 用户指南 (632 行) |

---

## 13. 注意事项 (Gotchas)

> [!CAUTION]
> **修改 `sqlite_client.py` 前必读**

1. **ROOT_NODE_UUID** = `00000000-0000-0000-0000-000000000000`。这是所有顶级 Edge 的 parent。不要动它。
2. **环检测 BFS** (`_would_create_cycle`): 检查的是 child→parent 方向的可达性，不是 parent→child。
3. **版本链**: `Memory.migrated_to` 指向新版本的 ID。删除中间版本时必须修复链条（`_safely_delete_memory` 已处理）。
4. **Path 复合主键**: `(domain, path)` 是联合主键，不能单独用 path 做唯一查询。
5. **Glossary 缓存**: `_glossary_automaton` 是进程级缓存，DB 指纹变化才重建。跨进程写入（Web API 修改 → MCP Server 读取）依赖 DB 指纹检测。
6. **`snapshot.py` 的 "首次触碰" 语义**: `record()` 只在 `before` 为空时写入 before 状态，后续只更新 after。这保证了 before 冻结为最原始状态。

> [!WARNING]
> **修改 `mcp_server.py` 前必读**

1. `system://` URI 不是数据库记录，是代码中硬编码的虚拟路由。
2. `update_memory` **故意不支持全量替换**。这是安全设计，不是遗漏。
3. `create_memory` 返回值的末尾会附加"提醒绑定触发词"的文字，这是有意为之。
4. Glossary 超链接注入在 `_fetch_and_format_memory()` 中，读取时自动附加到输出末尾。

> [!IMPORTANT]
> **git 操作提醒**

1. 本仓库 fork 自 `Dataojitori/nocturne_memory`，origin 已切换到 `Fu0000/AI-Agent-Memory`。
2. `.env` 文件已在 `.gitignore` 中，**绝不提交**。
3. `demo.db` 是示例数据库，包含少量测试数据，可提交。
4. `snapshots/` 目录已在 `.gitignore` 中，changeset 快照不提交。
