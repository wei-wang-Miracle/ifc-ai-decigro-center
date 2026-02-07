# 客户标签管理PRD

## 1. 项目背景与目标

**目标**：实现对 `customer_tag`（标签）、`customer_tag_category`（分类）、`customer_tag_enum`（枚举值）的增删改查（CRUD）。
**核心体验**：左树右表（Left-Tree, Right-Table）布局，支持分类级联查询。

## 2. 数据库模型映射 (PostgreSQL)

### 2.1 实体关系

1. **Category (1) : (N) Category** - 自关联树形结构 (`parent_id`)。
2. **Category (1) : (N) Tag** - 分类包含多个标签 (`category_id`)。
3. **Tag (1) : (N) Enum** - 当 Tag 类型为枚举时，关联多个枚举值 (`tag_field` 为关联键)。

### 2.2 核心表结构简述

- **标签表 (`customer_tag`)**: 主键 `tag_field` (String), 包含 `tag_table`, `tag_desc`, `value_type` 等。
- **分类表 (`customer_tag_category`)**: 主键 `id` (Long), 包含 `parent_id`。
- **枚举表 (`customer_tag_enum`)**: 关联键 `tag_field` (String)。

## 3. UI/UX 设计规范

### 3.1 页面布局 (Layout)

- **整体结构**：左右分栏布局。
- **左侧 (20%宽度)**：标签分类树 (Category Tree)。
- 顶部包含 "新建分类" 按钮。
- 树节点支持展开/折叠。
- 树节点右键或悬浮菜单：编辑、删除、添加子分类。

- **右侧 (80%宽度)**：标签列表与操作区 (Tag List)。
- 顶部搜索栏：按标签名称/字段名搜索。
- 功能按钮："新建标签"。
- 数据表格：展示标签详情。
- 操作列：编辑、配置枚举（仅当类型=enum时显示）、删除。

### 3.2 交互逻辑 (Interaction)

1. **分类点击联动**：

- 点击左侧分类树的某个节点（例如 `Category_A`）。
- 右侧列表**必须**展示 `Category_A` **及其所有子孙分类**下的标签（需要后端支持递归查询）。

2. **全部标签**：

- 默认选中“根节点”或提供“全部”选项，展示所有标签。

---

## 4. 功能详细需求 (Functional Requirements)

### 4.1 标签分类管理 (Category - Left Panel)

#### A. 查询分类树 (Read)

- **接口**：`GET /api/tag-categories/tree`
- **逻辑**：返回嵌套的 JSON 结构。
- **前端**：渲染为 Tree 组件。

#### B. 新增/编辑分类 (Create/Update)

- **字段**：
- `Parent Category` (若是根节点则为空或0)
- `tag_name` (必填)
- `Sort Index` (默认1)

- **校验**：同级目录下名称不可重复。

#### C. 删除分类 (Delete)

- **逻辑**：
- **强校验**：如果该分类下存在 **子分类** 或 **已关联标签**，禁止删除，提示用户先处理子数据。
- **物理删除**：执行 DELETE 操作。

### 4.2 标签主数据管理 (Tag - Right Panel)

#### A. 标签列表查询 (Read)

- **接口**：`GET /api/tags`
- **入参**：
- `categoryId` (选填): 若存在，需查询该ID及其所有子ID下的标签。
- `keyword` (选填): 模糊匹配 `tag_name` 或 `tag_field`。
- `page`, `size`: 分页参数。

- **回显字段**：`tag_field`, `tag_name`, `tag_table`, `value_type`, `category_name`, `update_time`.

#### B. 新增/编辑标签 (Create/Update)

- **表单字段**：

1. **Tag Field** (主键): 英文，必填，**创建后不可修改**。
2. **Tag Name**: 中文，必填。
3. **Tag Table**: 来源表名，必填（如下拉选择或输入）。
4. **Category**: 所属分类（树选择器），必填。
5. **Value Type**: 下拉选择 (String, Number, Enum, Date, Array)。
6. **Description (`tag_desc`)**: 文本域，维护口径描述。
7. **Sort Index**: 数字。

- **特殊逻辑**：
- 当 `Value Type` 切换为 `Enum` 时，提示用户保存后需配置枚举值，或在当前表单下方动态显示枚举配置表格。

#### C. 删除标签 (Delete)

- **逻辑**：物理删除 `customer_tag` 记录。
- **级联**：同步删除 `customer_tag_enum` 中对应 `tag_field` 的所有记录。

### 4.3 标签枚举值管理 (Enum Config)

- **入口**：标签列表页操作栏，仅当 `value_type = 'enum'` 时可用。
- **交互**：弹窗 (Modal) 或 抽屉 (Drawer)。
- **功能**：
- 列表展示当前 `tag_field` 下的所有枚举。
- 新增/编辑行：`Enum Code` (存库值), `Enum Name` (展示值)。
- 删除行。

- **保存**：
- 保存到 `customer_tag_enum` 表，`tag_field` 字段自动填充为当前标签的字段名。

---
