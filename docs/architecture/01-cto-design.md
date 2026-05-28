# ProjectOS — CTO 架构设计文档

## 1. 系统定位

ProjectOS 是 Solo Company 的**多项目指挥中心**。

在单项目时代，Solo Company = 1 CEO + 1 Secretary + 1 套 Agents → 1 个项目。

在多项目时代，ProjectOS = 1 CEO + 1 Secretary + N 套 Agents → N 个项目。

ProjectOS 不替代单项目 `solo`，也不 import `solo.core.*`。当前实现优先作为 read-only/control-plane：

- 注册已有 `.solo/config.yaml` 的项目。
- 通过公开 `solo ... --json` 命令读取状态、详情、健康检查。
- 必要时通过 `solo dispatch --json` 把任务派进子项目。
- 通过 ProjectOS 自己的 cross task graph 管理跨项目依赖和下发顺序。
- 不直接写子项目 `.solo/state/*`，子项目仍是状态源。

## 2. 核心概念

### 2.1 项目（Project）

一个项目 = 一个 git 仓库 + 一个 Solo Company 团队。

```yaml
project:
  id: project-a-hotspot
  name: "Social Hotspot Daily"
  repo: "https://github.com/NoahStransky/social-hotspot-daily"
  local_path: "projects/project-a-hotspot/repo"
  status: active    # active | paused | archived
  team:
    cto: enabled
    dev: enabled
    qa: enabled
    growth: disabled
  agents:
    - role: dev
      status: idle
      current_task: null
    - role: qa
      status: idle
      current_task: null
```

### 2.2 任务（Task）

项目内遗留任务模型，主要用于旧 scheduler 测试和单项目队列。

```yaml
task:
  id: TASK-20260423-001
  project_id: project-a-hotspot
  phase: dev          # cto | dev | qa | review | merge
  title: "Add unit tests"
  status: in_progress
  branch: feat/TASK-20260423-001-add-unit-tests
  assignee: dev       # 哪个 agent 在执行
  created_at: "2026-04-23T04:00:00Z"
  completed_at: null
```

### 2.3 跨项目任务（CrossProjectTask）

CEO 级任务会在 ProjectOS 中保存为一个 project-level graph。每个节点对应一个已注册的 `solo` 项目，ProjectOS 只保存路由、依赖、子项目 `solo_task_id` 和聚合状态；具体 phase / agent / artifact 仍由子项目 `.solo/` 保存。

```yaml
cross_task:
  id: XPROJ-20260528-001
  title: "Build billing feature"
  status: in_progress
  project_tasks:
    - project_id: backend
      solo_task_id: TASK-backend
      status: completed
      depends_on: []
    - project_id: frontend
      solo_task_id: TASK-frontend
      status: in_progress
      depends_on: [backend]
```

第一版 CLI 闭环：

```bash
solo-os project add ../backend --id backend
solo-os project add ../frontend --id frontend
solo-os dispatch "Build billing feature" --project backend --project frontend --depends frontend:backend --json
solo-os run --until done --json
solo-os status --json
```

### 2.4 Agent 实例（Agent Instance）

Agent 是**角色**不是**进程**。一个 Dev Agent 可以串行服务多个项目。

```yaml
agent_instance:
  id: dev-001
  role: dev
  current_project: project-a-hotspot
  current_task: TASK-20260423-001
  status: busy        # idle | busy | error
  history:
    - project: project-b-api
      task: TASK-20260423-000
      duration: 1200s
```

## 3. 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        CEO (Human)                               │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Secretary Agent                               │
│  • 接收 CEO 任务 → 分配到具体项目                                  │
│  • 监控所有项目状态                                                │
│  • 调度 Agent 资源（避免冲突）                                     │
│  • 汇总报告                                                        │
└──────────────────────┬───────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Project A    │ │ Project B    │ │ Project C    │
│ (hotspot)    │ │ (API svc)    │ │ (landing)    │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ CTO Agent    │ │ CTO Agent    │ │ CTO Agent    │
│ Dev Agent    │ │ Dev Agent    │ │ Dev Agent    │
│ QA Agent     │ │ QA Agent     │ │ QA Agent     │
│ Growth Agent │ │ Growth Agent │ │ Growth Agent │
└──────────────┘ └──────────────┘ └──────────────┘
         │             │             │
         └─────────────┴─────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
    ┌─────────────────┐  ┌─────────────────┐
    │ ProjectOS Core  │  │ Cross-Project   │
    │ • Registry      │  │ Dependencies    │
    │ • Scheduler     │  │ • API contract  │
    │ • State         │  │ • Sync protocol │
    │ • Dashboard     │  │                 │
    └─────────────────┘  └─────────────────┘
```

## 4. 核心模块设计

### 4.1 Registry（项目注册表）

文件：`projectos/core/registry.py`

职责：
- CRUD 项目
- 持久化到 `projects.json`
- 查询项目状态

```python
class ProjectRegistry:
    def __init__(self, db_path: str = "projectos/projects.json"):
        self.db_path = Path(db_path)
        self._projects: Dict[str, Project] = {}
        self._load()
    
    def create(self, project: Project) -> str:
        """注册新项目，返回 project_id"""
    
    def get(self, project_id: str) -> Optional[Project]:
    
    def list(self, status: Optional[str] = None) -> List[Project]:
    
    def update(self, project_id: str, **kwargs):
    
    def delete(self, project_id: str):
    
    def _save(self):
        """原子写入 JSON"""
```

### 4.2 Scheduler（Agent 调度器）

文件：`projectos/core/scheduler.py`

职责：
- 为任务分配 Agent
- 避免同一 Agent 同时服务多个项目
- 队列管理（任务排队）

```python
class AgentScheduler:
    def __init__(self, registry: ProjectRegistry):
        self.registry = registry
        self.agents: Dict[str, AgentInstance] = {}
    
    def assign(self, task: Task, role: str) -> Optional[str]:
        """
        为任务分配可用 Agent。
        策略：
        1. 找 idle 的该角色 Agent
        2. 如果没有，创建新 Agent 实例（受 max_concurrency 限制）
        3. 如果满了，加入队列
        """
    
    def release(self, agent_id: str):
        """Agent 完成任务，标记 idle，检查队列"""
    
    def queue(self, task: Task) -> int:
        """任务入队，返回队列位置"""
    
    def get_queue(self, project_id: Optional[str] = None) -> List[Task]:
    
    def can_start(self, project_id: str, role: str) -> bool:
        """检查指定项目的指定角色是否可以开始新任务"""
```

调度策略：
- 默认每个角色每个项目最多 1 个并发 Agent
- Dev Agent 全局最多 3 个并发（避免资源耗尽）
- 高优先级任务可以抢占队列

### 4.3 State（状态管理）

文件：`projectos/core/state.py`

职责：
- 项目状态持久化
- 任务状态流转
- 崩溃恢复

```python
class StateManager:
    def __init__(self, base_dir: str = "projectos/state"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def snapshot(self, project_id: str) -> Dict:
        """生成项目状态快照"""
    
    def restore(self, project_id: str) -> Dict:
        """从快照恢复"""
    
    def transition(self, task_id: str, from_phase: str, to_phase: str):
        """任务状态流转（带校验）"""
        # cto → dev → qa → review → merge
        # 不允许反向跳转（除非是 retry）
```

状态机：

```
created → cto → dev → qa → review → merged
            ↓     ↓     ↓       ↓
          retry retry retry   reject → dev
```

### 4.4 Dependency（项目依赖）

文件：`projectos/core/dependency.py`

职责：
- 管理项目间依赖关系
- 跨项目 API 契约检查
- 构建顺序

```python
class DependencyManager:
    def __init__(self, registry: ProjectRegistry):
        self.registry = registry
    
    def add_dependency(self, project_id: str, depends_on: str, contract: Dict):
        """
        project_id 依赖 depends_on。
        contract 定义接口契约：
        {
            "endpoint": "/api/v1/hotspots",
            "schema": "openapi.json",
            "version": "1.0.0"
        }
        """
    
    def get_dependencies(self, project_id: str) -> List[str]:
        """获取项目依赖列表"""
    
    def get_dependents(self, project_id: str) -> List[str]:
        """获取依赖本项目的其他项目"""
    
    def validate_contract(self, provider: str, consumer: str) -> bool:
        """验证 provider 的接口是否满足 consumer 的契约"""
    
    def build_order(self) -> List[str]:
        """拓扑排序，返回构建顺序（处理循环依赖报错）"""
```

### 4.5 Dashboard（看板 CLI）

文件：`projectos/core/dashboard.py` + `projectos/__main__.py`

```bash
# CLI 命令
python -m projectos list                          # 所有项目看板
python -m projectos status project-a-hotspot      # 单个项目详情
python -m projectos create my-project --repo ...  # 注册新项目
python -m projectos task add project-a "fix bug"  # 添加任务
python -m projectos pause project-b               # 暂停项目
python -m projectos resume project-b              # 恢复项目
python -m projectos deps --visualize              # 依赖图
python -m projectos dispatch "build billing" --project backend --project frontend --depends frontend:backend
python -m projectos run --until done              # 推进最新跨项目任务
python -m projectos retry backend --phase dev_pool # 桥接 child solo retry
python -m projectos reopen frontend --phase qa     # 桥接 child solo reopen
python -m projectos status                        # 全局项目和跨项目任务状态
```

### 4.6 CrossTaskStore + Orchestrator

文件：

- `projectos/core/cross_task.py`
- `projectos/core/orchestrator.py`

职责：

- 在 `projectos/state/cross_tasks.json` 保存 CEO 级任务图。
- 在 `projectos/state/events.jsonl` 追加 cross task / project task 事件。
- 根据 `--depends consumer:provider` 维护 project node 阻塞关系。
- 对 ready node 调用 `solo dispatch --json`。
- 对 in-progress node 调用 `solo run --until done --json`。
- 对下游 ready node，在 dispatch 前读取已完成依赖的 `solo inspect --json`，注入上游 task status、progress 和 artifact manifest。
- 根据 child solo 返回结果更新 project node 状态。

边界：

- ProjectOS 不写 child `.solo/state/*`。
- ProjectOS 不直接调 `solo.core.*`。
- 子项目失败时，ProjectOS 记录 `failed_reason`；恢复通过 child `solo retry/reopen` bridge 完成。

## 5. 项目内 Solo Company 实例化

每个项目在 `projects/<name>/agents/` 下有独立配置：

```
projects/project-a-hotspot/
├── agents/
│   ├── secretary.md      # 项目级 Secretary prompt（继承全局 + 项目上下文）
│   ├── cto.md            # 项目级 CTO prompt
│   ├── dev.md            # 项目级 Dev prompt
│   ├── qa.md             # 项目级 QA prompt
│   └── growth.md         # 项目级 Growth prompt
├── workspace/
│   └── tasks.json        # 项目自己的任务状态
└── repo/                 # git clone 的代码（或本地路径）
```

Agent Prompt 继承机制：
- 全局 prompt 在 `projectos/agents/prompts/`
- 项目级 prompt 覆盖全局同名 prompt
- 项目级 prompt 自动注入项目上下文（repo 路径、技术栈、历史决策）

## 6. 数据模型

### 6.1 Project

```python
@dataclass
class Project:
    id: str
    name: str
    repo_url: str
    local_path: str
    status: str  # active | paused | archived
    created_at: str
    team: Dict[str, bool]  # role -> enabled
    dependencies: List[str]  # project_ids
    metadata: Dict  # 技术栈、语言等
```

### 6.2 Task

```python
@dataclass
class Task:
    id: str
    project_id: str
    title: str
    description: str
    phase: str  # cto | dev | qa | review | merge | done
    status: str  # pending | in_progress | blocked | completed | failed
    priority: int  # 1-5
    branch: Optional[str]
    assignee: Optional[str]  # agent_id
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    parent_task: Optional[str]  # 子任务支持
```

### 6.3 AgentInstance

```python
@dataclass
class AgentInstance:
    id: str
    role: str  # secretary | cto | dev | qa | growth
    status: str  # idle | busy | error
    current_project: Optional[str]
    current_task: Optional[str]
    history: List[Dict]
```

## 7. 边界情况处理

| 场景 | 处理策略 |
|------|---------|
| Agent 超时 | Scheduler 标记 error，释放资源，任务回 queue |
| 项目并发冲突 | 同一项目的 Dev Agent 串行，不同项目可并行 |
| 循环依赖 | DependencyManager.build_order() 检测并报错 |
| 依赖项目未就绪 | 消费者任务 block，等 provider 完成 |
| 崩溃恢复 | StateManager.restore() 从快照恢复 |
| Agent 资源耗尽 | 新任务入队，CEO 收到队列积压告警 |

## 8. 技术栈

- Python 3.10+
- 数据存储：JSON 文件（无需外部数据库）
- 配置：YAML
- CLI：argparse / click
- 可选 Web Dashboard：FastAPI + 静态 HTML

## 9. 实现优先级

### Progress Log

#### 2026-05-28

- 实现 `CrossTaskStore`，新增 `projectos/state/cross_tasks.json` 和 `projectos/state/events.jsonl`。
- 新增 `CrossProjectOrchestrator`，支持创建 cross task、按依赖 dispatch ready project nodes、调用 child `solo run --until done --json` 推进子项目。
- CLI `dispatch` 兼容单项目旧用法，同时支持跨项目任务：`solo-os dispatch "..." --project backend --project frontend --depends frontend:backend --json`。
- CLI 新增 `solo-os run --until done --json` 推进最新或指定 cross task。
- CLI `solo-os status --json` 在不传 project id 时输出项目摘要和 cross task summary。
- 新增最小闭环测试，覆盖 backend -> frontend 依赖下发、运行和状态聚合。
- 当前验证：Docker Python 3.12 环境中 `pytest tests/ -q` 通过，`35 passed`。

继续推进依赖上下文传递：

- 下游 project node dispatch 前会读取已完成依赖项目的 `solo inspect --json`。
- 注入内容包括 upstream `solo_task_id`、task status、dashboard progress、run summary 和最多 12 条 artifact manifest。
- 新增测试确认 frontend 收到 backend 的 `TASK-backend` 和 `api-contract.json` artifact 线索。
- 当前验证：Docker Python 3.12 环境中 `pytest tests/ -q` 通过，`35 passed`。

继续推进恢复桥接：

- `SoloProjectAdapter` 新增 `retry()` 和 `reopen()`，只调用公开 child `solo retry/reopen --json`。
- `CrossProjectOrchestrator` 新增 `retry(project_id, phase|agent)` 和 `reopen(project_id, phase)`。
- CLI 新增 `solo-os retry <project_id> --phase/--agent ...` 和 `solo-os reopen <project_id> --phase ...`。
- 恢复成功后 project node 回到 `in_progress`，清除 `failed_reason` 和 `completed_at`，并记录 ProjectOS event。
- 新增测试覆盖 failed node 通过 retry/reopen bridge 恢复。
- 当前验证：Docker Python 3.12 环境中 `pytest tests/ -q` 通过，`36 passed`。

### Next Priorities

1. **P0 Done** — Registry + solo adapter + read-only dashboard。
2. **P0 Done** — CrossTaskStore + cross-project dispatch/run/status 最小闭环。
3. **P1 Done** — 把上游项目 `inspect` summary/artifact manifest 注入下游 prompt。
4. **P1 Done** — 增加 cross-task retry/reopen bridge，调用 child `solo retry/reopen`。
5. **P1** — richer dashboard：project node progress、failed reason、dependency graph。
6. **P2** — Web Dashboard（可视化）。
7. **P2** — Agent Prompt 模板系统。

## 10. 与现有项目的集成

Project A（social-hotspot-daily）和 Project B（API 服务）作为**示例项目**内嵌：

- 演示如何注册项目
- 演示跨项目依赖（B 提供 API，A 消费 API）
- 演示独立 Solo Company 团队运行
