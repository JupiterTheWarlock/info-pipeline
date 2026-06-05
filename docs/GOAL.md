# InfoPipeline Demo Evolution Goal

## 1. 目标

把当前 InfoPipeline demo 继续实现为一个面向个人信息摄取、筛选、分析和回看的工作台。

首阶段目标不是做通用新闻聚合器，而是服务以下偏好：

- 独立游戏方向：indie game、game dev、Steam/itch.io、发行与商业化、工具链、玩法设计、开发者经验。
- AI 方向：AI 产品、模型能力、agent 工具链、应用开发、开源项目、行业变化。

首批信息源：

- X / Twitter
- Reddit
- linux.do
- 知乎

输出形态：

- 后台按配置运行可插拔采集节点。
- LLM 对候选内容做分类、摘要、重要性评分和偏好匹配。
- Web UI 以紧凑 dashboard / browser 方式浏览日期、来源、主题、评分和报告。

## 2. 当前 Demo 状态

当前代码已经具备基础 pipeline：

- `main.py` 负责 CLI 入口：collect、analyze、report、push、web。
- `collectors/` 下已有多个 collector，包括 `twitter.py`、`reddit.py`、`zhihu.py`。
- `lib/llm.py` 已支持 OpenAI-compatible `/chat/completions` 调用。
- `web/server.py` 提供 `/api/tree`、`/api/report/<date>`、`/api/stats`。
- `web/index.html` 是单文件前端，当前更像传统 sidebar + markdown preview。

当前主要差距：

- collector 注册写死在 `main.py`，不够插件化。
- collector 配置缺少统一 schema、能力描述、运行状态和失败语义。
- 还没有 `linux.do` collector。
- AI 只是分析 batch 和生成报告，尚未成为可配置的“偏好过滤 + 评测”环节。
- UI 尚未按 `jthewl-frontend-design` 的紧凑暗色工具风格重构。
- 缺少对采集质量、AI 输出质量、运行耗时和失败原因的评测视图。

## 3. 目标架构

目标 pipeline：

```text
source plugin config
  -> collector registry
  -> collector node run
  -> normalized item
  -> dedup
  -> AI preference analysis
  -> report generation
  -> web dashboard / optional distribution
```

### 3.1 Collector Node

每个信息源都是一个可插拔节点。节点应有统一协议：

```python
class CollectorNode:
    name: str
    display_name: str
    source_type: str
    capabilities: set[str]

    def collect(self, context: CollectorContext) -> CollectorResult:
        ...
```

建议拆分：

- `collectors/base.py`：统一接口、context、result、item normalize helper。
- `collectors/registry.py`：注册、按配置启用、按名字加载。
- `collectors/sources/*.py` 或保留现有目录但改成统一导出。

节点返回结构应包含：

- `new_count`
- `seen_count`
- `errors`
- `started_at`
- `finished_at`
- `source_metrics`

这样 Web UI 可以展示每个信息源的运行健康度。

### 3.2 Normalized Item

所有平台进入数据库前应归一化为同一种 item：

- `url`
- `canonical_url`
- `source`
- `source_detail`
- `title`
- `content`
- `author`
- `published_at`
- `collected_at`
- `language`
- `tags`
- `raw`

其中 `raw` 保存平台原始字段，避免后续丢信息。

## 4. 首批信息源策略

### 4.1 X / Twitter

当前已有 `collectors/twitter.py`，通过 opencli 搜索或 timeline。

目标能力：

- 支持账号列表。
- 支持关键词搜索。
- 支持主题 query，例如独立游戏、AI agent、game dev。
- 支持按最近时间窗口采集。
- 失败时区分登录、限流、opencli 不可用、无结果。

推荐初始配置：

```yaml
collectors:
  twitter:
    enabled: true
    limit: 30
    keywords:
      - "indie game"
      - "gamedev"
      - "AI agent"
      - "LLM app"
```

### 4.2 Reddit

当前已有 `collectors/reddit.py`。

目标能力：

- 支持 subreddit hot/new/top。
- 支持 subreddit 分组：独立游戏、AI、开发工具。
- 支持 score/comment_count 进入 `raw` 和后续 AI 排序。

推荐初始配置：

```yaml
collectors:
  reddit:
    enabled: true
    limit: 50
    subreddits:
      - "indiegames"
      - "indiegaming"
      - "gamedev"
      - "LocalLLaMA"
      - "ArtificialInteligence"
      - "MachineLearning"
```

### 4.3 linux.do

当前没有 collector，需要新增。

目标能力：

- 优先实现公开页面/RSS/可访问接口的采集，不绕过权限。
- 采集帖子标题、链接、作者、时间、分类、正文摘要。
- 支持关键词或分类过滤。
- 如果需要登录态，必须作为本地配置输入，不写进仓库。

推荐初始配置：

```yaml
collectors:
  linuxdo:
    enabled: true
    limit: 50
    categories: []
    keywords:
      - "AI"
      - "agent"
      - "独立游戏"
      - "游戏开发"
```

### 4.4 知乎

当前已有 `collectors/zhihu.py`，通过 opencli search。

目标能力：

- 支持关键词搜索。
- 支持问题、回答、文章类型标记。
- 支持中文偏好词。
- 失败时区分 opencli 缺失、登录问题、无结果。

推荐初始配置：

```yaml
collectors:
  zhihu:
    enabled: true
    limit: 30
    keywords:
      - "独立游戏"
      - "游戏开发"
      - "AI 产品"
      - "智能体"
      - "大语言模型应用"
```

## 5. AI 接入目标

目标模型配置：

```yaml
llm:
  base_url: "https://api.deepseek.com"
  api_key: "${DEEPSEEK_API_KEY}"
  model: "deepseek-v4-flash"
  max_tokens: 4096
  timeout_seconds: 60
```

注意：

- API key 只写入本地 `config.yaml` 或 `.env`，不进入 git。
- 目标文档和示例配置只保留环境变量名。
- 当前 `lib.config` 尚未展开 `${DEEPSEEK_API_KEY}`，实现时需要补上环境变量解析，或只在本地 `config.yaml` 写入真实 key。
- 当前用户提供的 key 应作为本地运行凭据使用，不能写入受版本控制文件。

### 5.1 AI 分析能力

现有 `analyze_items()` 需要从简单分类扩展为偏好分析：

- `category`：主题分类。
- `score`：通用重要性，1-10。
- `preference_score`：对“独立游戏 / AI”偏好的匹配度，1-10。
- `summary`：一句话摘要。
- `why_relevant`：为什么值得看。
- `risk`：是否可能是低质量、标题党、重复、广告、噪音。
- `tags`：结构化标签。

报告生成应优先排序：

```text
preference_score desc
score desc
source confidence desc
published_at desc
```

### 5.2 AI Prompt 方向

系统角色：

```text
你是一个为独立游戏开发者和 AI 工具实践者服务的信息筛选助手。
你需要判断每条信息是否值得用户花时间阅读，并解释原因。
```

分类建议：

- Indie Game / 独立游戏
- Game Dev / 游戏开发
- AI Product / AI 产品
- AI Engineering / AI 工程
- Agents / 智能体
- Tools / 工具链
- Business / 商业化
- Other / 其他

## 6. UI 重构目标

使用 `jthewl-frontend-design` 的方向，将 UI 作为紧凑型开发者 dashboard，而不是 landing page。

### 6.1 信息架构

第一屏应该是可操作界面：

- 左侧：来源和日期树。
- 顶部：运行状态、刷新、采集、分析、报告入口。
- 中部：候选信息列表，支持来源、分类、评分、偏好匹配过滤。
- 右侧或下方：选中 item / report 预览。

### 6.2 视觉规则

默认使用暗色终端风格：

```css
--accent: #DA7756;
--accent-bright: #E8985C;
--accent-dim: #B85D3A;
--accent-glow: rgba(218, 119, 86, 0.4);
--bg-deep: #0A0908;
--bg-card: rgba(14, 12, 10, 0.85);
--text-primary: #E8E0D8;
--text-secondary: #8A7E74;
--text-bright: #FAF0E8;
--border: #2E2520;
--border-light: #4A3D33;
```

交互要求：

- hover、focus、selected、disabled、empty、error 状态完整。
- 不使用默认 `<select>`；过滤器使用自定义菜单。
- 长 URL、标题、路径必须截断或换行，不撑破布局。
- 移动端堆叠为 header、filter strip、list、detail。
- 不做大 hero、不做渐变按钮、不做装饰性背景。

## 7. 运行和评测目标

接入 AI 后需要执行并评测，不只看是否无报错。

### 7.1 最小运行链路

```powershell
python -m pytest
python main.py --collect --collectors twitter,reddit,zhihu,linuxdo
python main.py --analyze
python main.py --report
python main.py --web
```

如果 `linuxdo` 尚未完成，则先跑：

```powershell
python main.py --collect --collectors twitter,reddit,zhihu
```

### 7.2 评测指标

采集评测：

- 每个 source 是否有结果。
- 每个 source 的失败原因是否清晰。
- 去重是否生效。
- raw 字段是否保留关键平台字段。

AI 评测：

- JSON 输出是否稳定可解析。
- 分类是否落入允许枚举。
- `score` 和 `preference_score` 是否符合独立游戏 / AI 偏好。
- 摘要是否能说明“为什么值得看”。

UI 评测：

- 桌面和移动宽度无横向溢出。
- filter menu、tree row、按钮有 hover/focus/selected 状态。
- 空状态和错误状态能指出当前来源、日期或过滤条件。
- 报告 Markdown 可读，列表和链接不遮挡。

## 8. 里程碑

### M1: 目标和配置稳定

- 完成目标文档。
- 更新 `config.yaml.example`，加入 DeepSeek 示例、四个首批平台和偏好分类。
- 明确 secrets 只进本地 `config.yaml` 或环境变量。

### M2: Collector 插件架构

- 新增 collector registry。
- 现有 X / Reddit / 知乎 collector 迁移到统一接口。
- 新增 `linuxdo` collector。
- CLI 支持按节点名运行。

### M3: AI 偏好分析

- 接入 DeepSeek endpoint/model。
- 扩展分析结果字段。
- 增加解析失败 fallback 和测试。
- 生成偏好排序报告。

### M4: UI 重构

- 按紧凑 dashboard 重写 `web/index.html`。
- 增加来源状态、过滤器、列表和 report preview。
- 增加 API 支持必要数据。

### M5: 执行和评测

- 本地跑测试。
- 用四个平台执行采集。
- 执行 AI 分析和报告生成。
- 记录评测结果和下一步缺口。

## 9. 验收标准

本阶段完成时，需要满足：

- `docs/GOAL.md` 清楚描述后续实现方向和验收标准。
- `config.yaml.example` 能表达首批信息源和 AI 偏好目标。
- X、Reddit、linux.do、知乎都能作为独立 collector 节点被启用或关闭。
- AI 使用 DeepSeek OpenAI-compatible 接口完成偏好分析。
- Web UI 符合紧凑暗色工具风格，并能浏览采集结果和分析报告。
- 至少完成一次端到端运行记录：collect、analyze、report、web。
- 失败项必须有明确原因，例如登录态、平台限制、网络、配置、LLM 输出解析。
