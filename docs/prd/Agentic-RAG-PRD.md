# Agentic RAG (智能体检索增强生成) 子系统 PRD

## 1. 文档概述

### 1.1 编写目的

本文档旨在为 NexusGraph (DeciGro Center) 系统引入 **Agentic RAG（智能体化检索增强生成）** 能力提供详细的产品需求说明与架构设计蓝图。
区别于传统的“无脑检索、整块拼接”的普通 RAG，Agentic RAG 将依托当前系统的 `ai-engine` (LangGraph) 编排能力和 `bus-kernel` (Java) 数据基座，让大模型在检索过程中充当**策略规划师**与**质量裁判员**，实现“意图改写 -> 混合检索 -> 质量打分 -> 失败重试 -> 融合生成”的闭环，彻底根治 RAG 场景下的幻觉与低级匹配问题。

### 1.2 架构定位

- **数据存储与检索能力基座 (`bus-kernel`)**：负责 PDF/Word 文件的解析、分块 (Chunking)、向量化 (Embedding)、元数据提取、知识库管理 CRUD，以及暴露基于 ElasticeSearch/向量库 的混合检索 API (ToolCard)。
- **智能检索编排与评估 (`ai-engine`)**：负责拦截用户复杂的知识型查询，将其**动态重写**为针对 `bus-kernel` API 的精准结构化查询，并在获取文档片段后使用 LLM 进行**交叉评估打分**和**反思重试**，最终融合生成合规答案。

---

## 2. 核心架构与阶段流转 (AI Engine 侧)

Agentic RAG 在 `ai-engine` 中需要被设计为一个**独立的高阶智能体工作流 (Sub-graph/Node)**，而不是粗暴地混合在普通的 Tool Calling 循环中。核心流转包含以下 4 个阶段：

### 2.1 阶段一：检索前处理 (Pre-Retrieval & Rewrite)

**目标**：解决用户自然语言提问过于口语化、概念模糊、缺少上下文，导致底层向量检索命中率低的问题。
**核心思想**：大模型充当“查询翻译官” (Query Rewriter)。
**实现原理**：

1.  **意图消解**：将用户输入（如“000001最近咋样”）翻译为标准化、专业化的查询短语（如“000001 基金 近期表现 风险分析”）。
2.  **多路拆解**：如果用户问题包含多个维度（“告诉我什么是夏普比率，顺便查一下000001的夏普比率”），Planner 需要将其拆解为独立的两条查询意图。
3.  **元数据提取**：基于 Prompt，引导 LLM 提取出时间范围、文档类型等**结构化过滤条件**，准备传给 `bus-kernel` 的检索工具。

### 2.2 阶段二：混合检索执行 (Execution)

**目标**：精准、低噪地从海量知识库中召回最相关的 Document Chunks。
**核心思想**：利用 `bus-kernel` 的强大 ToolCard 能力，执行带元数据过滤的混合查询。
**实现原理**：
`ai-engine` 通过组装好的参数，调用 `bus-kernel` 的 `advanced_knowledge_search` API。底层执行：

- **硬过滤 (Pre-filter)**：先用提取的结构化元数据（如 `docType="考核文档"`）在 ES 中过滤掉 99% 不相关的文档块。
- **混合召回 (Hybrid Search)**：对剩余的 1% 文档库，同时执行 Dense Vector (语义向量相似度) 和 BM25 (精准关键字匹配)，并将结果通过 RRF (倒数排序融合) 打分排序，返回 Top K 结果。

### 2.3 阶段三：结果交叉评估 (Grading & Evaluation)

**目标**：建立 RAG 的防火墙，绝不把不相关的“知识垃圾”喂给最终生成节点，防止幻觉发生。
**核心思想**：大模型作为裁判 (Document Grader)。
**实现原理**：

1.  引入专门的 `rag_grade_node`。
2.  系统并发出发一个轻量级 LLM (如 gpt-4o-mini 或严格控制 temperature 的模型)，执行二元分类判定：`返回的 Chunk 是否包含回答用户 Query 的有效信息？(Yes/No)`。
3.  **客观标准**：
    - **相关性 (Relevance)**：语义是否匹配。
    - **信息量 (Informativeness)**：哪怕主题匹配，但内容是否足以解答问题（例如文档只提了变动，没提变动原因，打分 No）。

### 2.4 阶段四：反思重试与兜底 (Reflection & Fallback)

**目标**：赋予 Agent “查不到就换个角度查，再查不到就诚实承认”的韧性特征。
**核心思想**：基于评估结果的条件反馈循环。
**实现原理**：

1.  若阶段三所有的 Chunk 均被打分为 "No"，流程回退到 **阶段一 (Rewrite)**。大模型会被注入反思 Prompt：“你之前的搜索词 X 失败了，请尝试扩展同义词或更换维度重新生成搜索词 Y”。
2.  设置最大重试计数器 (如 `max_retry=3`) 防止 LangGraph 死循环消耗 Token。
3.  **兜底机制 (Fallback)**：到达最大重试次数仍失败时，强制流转到外部工具（如 Web Search）补齐时效性知识，或**强制模型交白卷**：“在内部知识库中未检索到明确信息”，杜绝模型凭借过时的内部预训练参数强行编造。

### 2.5 阶段五：融合与自查 (Synthesis & Hallucination Check - 可选/高阶)

**目标**：生成最终连贯回答，并在输出前进行最后一次基于 Grounding 的静默自查。
**实现原理**：
Responder 获取所有评估为 "Yes" 的优质文档块作为上下文生成。生成后（或流式输出的同时），有一个后台校验器比对：“这句结论在上下文中能找到确切依据吗？” 若为 No，拒绝输出该句话。

---

## 3. Bus-Kernel 知识库管理后端设计

为了支撑前台极为灵活、苛刻的 Agentic RAG 请求，`bus-kernel` 必须提供一整套完善的知识运营系统。

### 3.1 知识库文档结构定义 (Document Table)

记录上传的原始文件元数据。

| 字段名称       | 字段类型    | 说明                    | 示例 / 注释                                            |
| :------------- | :---------- | :---------------------- | :----------------------------------------------------- |
| `doc_id`       | String(PK)  | 文档唯一ID              | `doc_fc5a90d8...`                                      |
| `file_name`    | String      | 原文件名                | `2024年富国天惠年报.pdf`                               |
| `file_url`     | String      | 物理存储路径(OSS/MinIO) | `/minio/knowledge/2024/...`                            |
| `doc_type`     | String/Enum | 文档所属分类池          | `研报`, `制度规范`, `名词释义`                         |
| `biz_tags`     | JSONB       | 业务辅助标签            | `["A股", "大盘"]`                                      |
| `publish_date` | Date        | 文档发布时间            | 用户限定检索时间范围                                   |
| `status`       | Enum        | 文档解析状态            | `PENDING`, `PARSING`, `EMBEDDING`, `SUCCESS`, `FAILED` |
| `tenant_code`  | String      | 租户隔离(若有)          | -                                                      |
| `created_by`   | String      | 上传人                  | -                                                      |

### 3.2 向量存储结构设计 (Chunk/Vector Index - Elasticsearch 等)

切碎的知识块和高维向量，是提供给 AI 工具检索的真正标的物。

| 字段名称       | 字段类型      | 说明                   | RAG 价值                                                    |
| :------------- | :------------ | :--------------------- | :---------------------------------------------------------- |
| `chunk_id`     | String(PK)    | 切块唯一ID             | `chunk_uuid`                                                |
| `doc_id`       | String(FK)    | 归属的主文档ID         | 用于找回出处和文件链接                                      |
| `chunk_index`  | Integer       | 块序号 (0, 1, 2...)    | 命中后可通过 `index±1` 召回上下文，解决块边界信息截断问题   |
| `content`      | Text          | 切片纯文本内容         | 经过标准或自定义 IK 分词，用于 BM25 关键词匹配得分          |
| `embedding`    | Vector(Dense) | 高维语义向量表示       | 如 1536 维 float 数组，用于 KNN 语义相似度计算得分          |
| `title_path`   | Keyword[]     | 该块所在的文档层级路径 | 如 `["前言", "产品风险"]`，大模型结合它能更好地理解块的主旨 |
| `doc_type`     | Keyword       | 冗余父表字段：文档分类 | **关键！** AI 通过大类限定检索范围，防止跨库干扰            |
| `publish_date` | Date          | 冗余父表字段：时间戳   | AI 可指令“只搜三个月内发生的事”                             |

### 3.3 文档解析与向量化生命周期 (Pipeline)

由于解析和向量化极为耗时，需采用**异步队列任务机制**。

1.  **文件上传 (Upload)**：前端传文件及提取的基础元数据写入 `Document Table`，状态置为 `PENDING`，文件入 OSS。
2.  **文本切割 (Chunking)**：这是 RAG 的玄学与核心。
    - **策略注意点**：不能粗暴按字数长短切断。需要识别 PDF/Word 的逻辑边界（如遇见标题换行、句号换段）。
    - **重叠窗口 (Overlap)**：每个 Chunk 与下一个 Chunk 必须保持一定的字符重叠（如 500字一块，重叠 50字），防止关键概念恰好被一刀切成两段导致两者均搜不出。
3.  **向量抽取 (Embedding)**：调用 Embedding 模型 API（如 `text-embedding-3-small` 或本地 BGE 模型），将每个 Chunk 转化为数组。
4.  **向量入库 (Indexing)**：将 Chunk 以及所有的关联元数据（docType 等）作为一个 Document 写入 ES 或 Vector DB，状态置为 `SUCCESS`。

### 3.4 后台管理 API 清单 (参考)

- **文档库管理**：
  - `POST /knowledge/upload`：上传接口（附带文件与分类等元数据）。
  - `GET /knowledge/page`：分页查看库内文件及其向量化状态。
  - `DELETE /knowledge/{docId}`：物理删除文件，并**级联移除 ES 中对应 docId 的所有 Chunks**，保持纯净。
- **人工微调与补偿**：
  - `GET /knowledge/chunks/{docId}`：预览某个长文档被切分的明细块。
  - `PUT /knowledge/chunks/{chunkId}`：人工修正某个 Chunk 的文本（如 OCR 识别错误导致 RAG 老失败，管理员可以直接进去改字重新触发一下 Embedding）。

---

## 4. Agent 与 ToolCard 建设要点

### 4.1 Bus-Kernel RAG 高级工具暴露 (`AdvancedKnowledgeSearchTool`)

这是 `bus-kernel` 向 `ai-engine` 暴露的杀手锏。

**Tool_Description**:

> 你是一个高级知识库检索专家。当用户在询问专业名词含义、规章制度、研究报告详情、或者你不了解的新鲜事时，必须调用本工具。
> 请尽量利用你知道的实体信息（如基金代码）作为参数，以缩小搜索范围。

**Tool_Parameters (JsonSchema)**:

- `query` (String, 必填): 用于去匹配知识库语意的查询主词。
- `exact_keyword` (String, 选填): 如果你怀疑存在生僻专有名词，将其填在这里，系统会增加精确关键词匹配权重。
- `must_match_doc_type` (String, 选填): 当你需要查询特定类型文档时填写（枚举值说明...）。

### 4.2 AI Engine Agent 挂载策略

建议不在普通的通识 Executor 上零散挂载该检索工具，而是创建一个系统级 **`rag_specialist_agent`**（知识增强检索专家智能体）。

**System Prompt (核心大脑约束)**:

> 你的职责是通过工具从集团非结构化知识库中获取权威信息。
> 你必须经过多轮检索确认事实。如果在工具返回的知识中找不到明确支撑用户问题的段落，你不能凭借自身记忆捏造事实，请回答“资料库中暂无相关说明”。

**LangGraph 路由集成**：
当 `dispatcher` 判断需要动用 RAG 时，转交给针对 `rag_specialist_agent` 设计的专属子图流程（包含 evaluate 和 retry Node，即第二章中描述的流转路径）。

---

## 5. 项目落地建议

1. **分期 MVP 演进**：
   - **Stage 1**: 先用关系型数据库跑通普通的 `检索 -> 丢给模型回答` 的粗糙 RAG，验证文本解析(Chunking)流程是否顺畅。
   - **Stage 2**: 把数据切向 ES，利用 `ToolCard` 让大模型学会丢过滤参数进去（体会混合检索加元的威力）。
   - **Stage 3**: 在 `ai-engine` 端，利用 LangGraph 加入 `Grade` 评估节点这把“达摩克利斯之剑”，阻断低质回答，此时方宣告完成 Agentic RAG。
2. **切片质量决定下限**：
   重中之重是文本的切分策略（Markdown 分隔符切分优于按长度盲切）；表格数据的提取极其困难，建议剥离出来变成结构化数据库，知识库仅放纯本文分析段落。
3. **审计基建不可缺位**：
   RAG 每次召唤几万字的 Chunk、经历多轮失败重试，Token 开销极大。务必在每个 Node 做好审计埋点，便于在后台看到每一笔消耗是为了寻找哪一句话。
