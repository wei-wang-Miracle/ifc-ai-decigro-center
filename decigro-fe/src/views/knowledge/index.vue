<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import request from "../../utils/request";
import {
  Upload,
  Search,
  Refresh,
  Delete,
  View,
  Timer,
  SuccessFilled,
  WarningFilled,
  CircleCloseFilled,
  DocumentAdd,
  Expand,
  Plus,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile, UploadRawFile } from "element-plus";

// ============================================
// 第一部分：类型与数据定义
// ============================================

// 文档处理状态枚举
type DocStatus = "PENDING" | "PARSING" | "EMBEDDING" | "SUCCESS" | "FAILED";

interface KnowledgeDoc {
  doc_id: string;
  file_name: string;
  doc_type: string;
  related_codes: string[];
  biz_tags: string[];
  publish_date: string | null;
  status: DocStatus;
  error_msg: string | null;
  chunk_count: number;
  create_time: string;
  update_time: string;
}

interface Chunk {
  chunk_id: string;
  doc_id: string;
  chunk_index: number;
  content: string;
  title_path: string[];
}

// 文档列表
const docList = ref<KnowledgeDoc[]>([]);
const loading = ref(false);
const totalCount = ref(0);

// 搜索参数
const searchForm = reactive({
  keyword: "",
  docType: "",
  page: 1,
  size: 12,
});

// 文档类型选项（可扩展）
const docTypeOptions = [
  { label: "全部类型", value: "" },
  { label: "研报分析", value: "研报" },
  { label: "基金年报", value: "年报" },
  { label: "名词释义", value: "名词释义" },
  { label: "制度规范", value: "制度规范" },
  { label: "市场快讯", value: "市场快讯" },
  { label: "技术文档", value: "技术文档" },
];

// ============================================
// 上传对话框
// ============================================
const uploadDialogVisible = ref(false);
const uploadLoading = ref(false);
const uploadForm = reactive({
  docType: "",
  relatedCodes: "",
  bizTags: "",
  publishDate: undefined as string | undefined,
});
const selectedFile = ref<File | null>(null);

const VALID_DOC_TYPES = ["研报", "年报", "名词释义", "制度规范", "市场快讯", "技术文档"];
const uploadFormRules = {
  docType: [{ required: true, message: "请选择文档分类", trigger: "change" }],
};

// ============================================
// Chunk 预览对话框
// ============================================
const chunkDialogVisible = ref(false);
const chunkLoading = ref(false);
const currentDocName = ref("");
const chunkList = ref<Chunk[]>([]);
const editingChunk = ref<Chunk | null>(null);
const editContent = ref("");

// ============================================
// 第二部分：API 交互逻辑
// ============================================

const fetchDocList = async () => {
  loading.value = true;
  try {
    const params: any = {
      page: searchForm.page,
      size: searchForm.size,
    };
    if (searchForm.keyword) params.keyword = searchForm.keyword;
    if (searchForm.docType) params.docType = searchForm.docType;

    const res: any = await request.get("/knowledge/list", { params });
    // 响应格式：{ code, message, data: { data: [...], total } }
    const payload = res?.data || res || {};
    docList.value = payload.data || payload || [];
    totalCount.value = payload.total || docList.value.length;
  } catch (e) {
    console.error("获取文档列表失败", e);
    ElMessage.error("获取列表失败，请检查 ai-rag 服务是否正常运行");
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  searchForm.page = 1;
  fetchDocList();
};

// 文件选择处理
const handleFileChange = (uploadFile: UploadFile) => {
  if (uploadFile.raw) {
    const raw = uploadFile.raw as UploadRawFile;
    const allowedTypes = [
      "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/plain",
      "text/markdown",
    ];
    if (!allowedTypes.includes(raw.type) && !raw.name.endsWith(".md")) {
      ElMessage.warning("仅支持 PDF、Word、Markdown 等格式");
      return;
    }
    selectedFile.value = raw;
  }
};

// 提交上传
const handleUploadSubmit = async () => {
  if (!selectedFile.value) {
    ElMessage.warning("请先选择要上传的文档文件");
    return;
  }
  if (!uploadForm.docType) {
    ElMessage.warning("请选择文档分类");
    return;
  }

  uploadLoading.value = true;
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    formData.append("docType", uploadForm.docType);
    formData.append("relatedCodes", uploadForm.relatedCodes || "");
    formData.append("bizTags", uploadForm.bizTags || "");
    if (uploadForm.publishDate)
      formData.append("publishDate", uploadForm.publishDate);

    await request.post("/knowledge/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    ElMessage.success("文档已上传，正在后台异步处理中...");
    uploadDialogVisible.value = false;
    resetUploadForm();
    setTimeout(fetchDocList, 1500); // 稍等片刻后刷新，状态可能已更新为 PARSING
  } catch (e: any) {
    ElMessage.error("上传失败: " + (e?.message || "请检查网络连接"));
  } finally {
    uploadLoading.value = false;
  }
};

const resetUploadForm = () => {
  Object.assign(uploadForm, {
    docType: "",
    relatedCodes: "",
    bizTags: "",
    publishDate: undefined,
  });
  selectedFile.value = null;
};

// 删除文档
const handleDelete = async (doc: KnowledgeDoc) => {
  await ElMessageBox.confirm(
    `确定要删除文档 "${doc.file_name}" 吗？\n此操作将同时彻底清除该文档的所有向量 Chunk，不可恢复！`,
    "⚠️ 危险操作确认",
    {
      type: "warning",
      confirmButtonText: "确认删除",
      cancelButtonText: "取消",
      confirmButtonClass: "el-button--danger",
    },
  );
  try {
    await request.delete(`/knowledge/${doc.doc_id}`);
    ElMessage.success("文档已删除");
    fetchDocList();
  } catch (e) {
    ElMessage.error("删除失败");
  }
};

// 重新处理文档
const handleReprocess = async (doc: KnowledgeDoc) => {
  await ElMessageBox.confirm(
    `是否重新处理文档 "${doc.file_name}"？\n将清空旧的切块数据并重新向量化。`,
    "重新处理确认",
    { type: "info" },
  );
  try {
    await request.post(`/knowledge/${doc.doc_id}/reprocess`);
    ElMessage.success("已触发重新处理，请稍后刷新查看状态");
    fetchDocList();
  } catch (e) {
    ElMessage.error("操作失败");
  }
};

// 预览 Chunk 切块
const handleViewChunks = async (doc: KnowledgeDoc) => {
  if (doc.status !== "SUCCESS") {
    ElMessage.warning("文档尚未处理完成，无法预览切块");
    return;
  }
  currentDocName.value = doc.file_name;
  chunkDialogVisible.value = true;
  chunkLoading.value = true;
  editingChunk.value = null;
  try {
    const res: any = await request.get(`/knowledge/${doc.doc_id}/chunks`);
    const payload = res?.data || res || {};
    chunkList.value = payload.data || payload || [];
  } catch (e) {
    ElMessage.error("获取切块详情失败");
  } finally {
    chunkLoading.value = false;
  }
};

// 进入 Chunk 编辑模式
const handleEditChunk = (chunk: Chunk) => {
  editingChunk.value = chunk;
  editContent.value = chunk.content;
};

// 保存 Chunk 修改
const handleSaveChunk = async (chunk: Chunk) => {
  if (!editContent.value.trim()) {
    ElMessage.warning("内容不能为空");
    return;
  }
  try {
    const formData = new FormData();
    formData.append("content", editContent.value);
    await request.put(
      `/knowledge/${chunk.doc_id}/chunks/${chunk.chunk_id}`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    // 更新本地状态
    const idx = chunkList.value.findIndex((c) => c.chunk_id === chunk.chunk_id);
    if (idx !== -1) chunkList.value[idx].content = editContent.value;
    ElMessage.success("Chunk 已修正并重新向量化");
    editingChunk.value = null;
  } catch (e) {
    ElMessage.error("保存失败");
  }
};

// 状态辅助函数
const getStatusLabel = (status: DocStatus) => {
  const map: Record<DocStatus, string> = {
    PENDING: "等待处理",
    PARSING: "解析中...",
    EMBEDDING: "向量化中...",
    SUCCESS: "处理完成",
    FAILED: "处理失败",
  };
  return map[status] || status;
};

const getStatusType = (status: DocStatus) => {
  const map: Record<DocStatus, string> = {
    PENDING: "#94a3b8",
    PARSING: "#f59e0b",
    EMBEDDING: "#3b82f6",
    SUCCESS: "#10b981",
    FAILED: "#ef4444",
  };
  return map[status] || "#94a3b8";
};


// ============================================
// Markdown 渲染（内联实现，无需外部依赖）
// 支持：标题、表格、代码块、粗体、斜体、内联代码、段落
// ============================================
const renderMarkdown = (md: string): string => {
  if (!md) return "";
  let html = md
    // 第一步：保护代码块（避免内部内容被后续规则了解）
    .replace(
      /```(\w*)\n([\s\S]*?)```/gm,
      (_, lang, code) =>
        `<pre class="md-pre"><code class="md-code-block">${escapeHtml(code.trimEnd())}</code></pre>`,
    )
    // 标题 h1-h6
    .replace(/^###### (.+)$/gm, "<h6 class='md-h'>$1</h6>")
    .replace(/^##### (.+)$/gm, "<h5 class='md-h'>$1</h5>")
    .replace(/^#### (.+)$/gm, "<h4 class='md-h'>$1</h4>")
    .replace(/^### (.+)$/gm, "<h3 class='md-h'>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2 class='md-h'>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1 class='md-h'>$1</h1>")
    // 表格：匹配完整的表格块
    .replace(/\|(.+)\|\n\|[-| :]+\|\n((\|.+\|\n?)+)/gm, (match: string) => {
      const lines = match.trim().split("\n");
      const header = lines[0]
        .split("|")
        .slice(1, -1)
        .map((c: string) => `<th>${c.trim()}</th>`)
        .join("");
      const rows = lines
        .slice(2)
        .map(
          (row: string) =>
            `<tr>${row
              .split("|")
              .slice(1, -1)
              .map((c: string) => `<td>${c.trim()}</td>`)
              .join("")}</tr>`,
        )
        .join("");
      return `<div class="md-table-wrap"><table class="md-table"><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
    })
    // 粗体 / 斜体
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // 内联代码
    .replace(/`([^`]+)`/g, "<code class='md-inline-code'>$1</code>")
    // 分隔线
    .replace(/^---$/gm, "<hr class='md-hr'>")
    // 段落：空行分隔的非标签行
    .replace(/\n{2,}/g, "</p><p class='md-p'>")
  ;
  return `<div class="md-body"><p class="md-p">${html}</p></div>`;
};

// HTML 转义（代码块内内容防注入）
const escapeHtml = (s: string) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

onMounted(() => fetchDocList());
</script>

<template>
  <div class="knowledge-registry">
    <!-- ============= 顶部操作栏 ============= -->
    <div class="header-bar">
      <div class="header-left">
        <div class="header-icon">
          <el-icon class="text-white" size="20"><DocumentAdd /></el-icon>
        </div>
        <div class="header-info">
          <h3 class="header-title">RAG 知识库管理</h3>
          <p class="header-subtitle">
            VECTOR KNOWLEDGE BASE · POWERED BY RAGLITE
          </p>
        </div>
        <el-button
          type="primary"
          :icon="Upload"
          class="upload-btn"
          @click="uploadDialogVisible = true"
        >
          上传文档
        </el-button>
      </div>
      <div class="header-right">
        <el-select
          v-model="searchForm.docType"
          placeholder="文档类型"
          clearable
          class="w-36"
          @change="handleSearch"
        >
          <el-option
            v-for="o in docTypeOptions"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
        <el-input
          v-model="searchForm.keyword"
          placeholder="搜索文档名称"
          clearable
          class="w-44"
          @keyup.enter="handleSearch"
        />
        <el-button :icon="Search" @click="handleSearch" />
        <el-button :icon="Refresh" @click="fetchDocList" />
      </div>
    </div>

    <!-- ============= 统计数据条 ============= -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-num">{{ totalCount }}</span>
        <span class="stat-label">文档总数</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-num success">{{
          docList.filter((d) => d.status === "SUCCESS").length
        }}</span>
        <span class="stat-label">已向量化</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-num warning">{{
          docList.filter((d) =>
            ["PARSING", "EMBEDDING", "PENDING"].includes(d.status),
          ).length
        }}</span>
        <span class="stat-label">处理中</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-num danger">{{
          docList.filter((d) => d.status === "FAILED").length
        }}</span>
        <span class="stat-label">失败</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-num">{{
          docList.reduce((s, d) => s + (d.chunk_count || 0), 0).toLocaleString()
        }}</span>
        <span class="stat-label">向量 Chunks</span>
      </div>
    </div>

    <!-- ============= 文档卡片网格 ============= -->
    <div class="doc-grid" v-loading="loading">
      <div v-if="docList.length === 0 && !loading" class="empty-state">
        <el-icon size="64" class="empty-icon"><DocumentAdd /></el-icon>
        <p class="empty-text">知识库为空</p>
        <p class="empty-sub">
          点击"上传文档"将 PDF / Word / Markdown 注入知识库
        </p>
        <el-button
          type="primary"
          :icon="Upload"
          @click="uploadDialogVisible = true"
          >立即上传</el-button
        >
      </div>

      <div v-for="doc in docList" :key="doc.doc_id" class="doc-card">
        <!-- 状态指示条（顶部） -->
        <div
          class="card-status-bar"
          :style="{ background: getStatusType(doc.status) }"
        />

        <!-- 文档类型标签 -->
        <div class="card-type-badge">{{ doc.doc_type }}</div>

        <!-- 文件名 -->
        <div class="card-filename" :title="doc.file_name">
          <span class="filename-text">{{ doc.file_name }}</span>
        </div>

        <!-- 状态标签 -->
        <div class="card-status-row">
          <div
            class="status-pill"
            :style="{
              background: getStatusType(doc.status) + '20',
              borderColor: getStatusType(doc.status),
              color: getStatusType(doc.status),
            }"
          >
            <el-icon
              v-if="['PARSING', 'EMBEDDING'].includes(doc.status)"
              class="spinning"
              ><Timer
            /></el-icon>
            <el-icon v-else-if="doc.status === 'SUCCESS'"
              ><SuccessFilled
            /></el-icon>
            <el-icon v-else-if="doc.status === 'FAILED'"
              ><CircleCloseFilled
            /></el-icon>
            <el-icon v-else><WarningFilled /></el-icon>
            {{ getStatusLabel(doc.status) }}
          </div>
          <span v-if="doc.status === 'SUCCESS'" class="chunk-count">
            {{ (doc.chunk_count || 0).toLocaleString() }} chunks
          </span>
        </div>

        <!-- 元数据信息 -->
        <div class="card-meta">
          <div v-if="doc.related_codes?.length" class="meta-row">
            <span class="meta-label">关联代码</span>
            <div class="meta-tags">
              <span
                v-for="code in doc.related_codes.slice(0, 3)"
                :key="code"
                class="code-tag"
                >{{ code }}</span
              >
              <span v-if="doc.related_codes.length > 3" class="more-tag"
                >+{{ doc.related_codes.length - 3 }}</span
              >
            </div>
          </div>
          <div class="meta-row">
            <span class="meta-label">上传时间</span>
            <span class="meta-value mono">{{ doc.create_time }}</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="card-actions">
          <el-tooltip content="预览切块详情" placement="top">
            <el-button
              circle
              size="small"
              :icon="View"
              :disabled="doc.status !== 'SUCCESS'"
              @click="handleViewChunks(doc)"
            />
          </el-tooltip>
          <el-tooltip
            v-if="doc.status === 'FAILED'"
            content="重新处理"
            placement="top"
          >
            <el-button
              circle
              size="small"
              :icon="Refresh"
              type="warning"
              @click="handleReprocess(doc)"
            />
          </el-tooltip>
          <el-tooltip content="删除文档" placement="top">
            <el-button
              circle
              size="small"
              :icon="Delete"
              type="danger"
              @click="handleDelete(doc)"
            />
          </el-tooltip>
        </div>

        <!-- 错误信息展示 -->
        <div v-if="doc.status === 'FAILED' && doc.error_msg" class="error-msg">
          {{ doc.error_msg }}
        </div>
      </div>
    </div>

    <!-- ============= 上传文档对话框 ============= -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="📄 上传文档到知识库"
      width="560px"
      draggable
    >
      <div class="upload-dialog-body">
        <!-- 拖拽上传区域 -->
        <el-upload
          class="upload-zone"
          drag
          :auto-upload="false"
          :limit="1"
          accept=".pdf,.doc,.docx,.txt,.md"
          :on-change="handleFileChange"
          :show-file-list="false"
        >
          <div class="upload-dragger-content">
            <el-icon size="40" class="upload-icon"><Upload /></el-icon>
            <div class="upload-text">
              <span class="upload-main-text"
                >拖拽文件到此处，或<em>点击上传</em></span
              >
              <span class="upload-sub-text"
                >支持 PDF / Word / Markdown / TXT，单文件不超过 50MB</span
              >
            </div>
          </div>
          <div v-if="selectedFile" class="selected-file-info">
            <el-icon><DocumentAdd /></el-icon>
            <span>{{ selectedFile.name }}</span>
            <span class="file-size"
              >{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB</span
            >
          </div>
        </el-upload>

        <el-divider>文档元数据</el-divider>

        <el-form
          :model="uploadForm"
          label-width="100px"
          style="padding: 0 12px"
        >
          <el-form-item label="文档分类" required>
            <el-select
              v-model="uploadForm.docType"
              placeholder="请选择..."
              class="w-full"
            >
              <el-option
                v-for="t in VALID_DOC_TYPES"
                :key="t"
                :label="t"
                :value="t"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="关联代码">
            <el-input
              v-model="uploadForm.relatedCodes"
              placeholder="如：000001,000002（英文逗号分隔）"
            />
            <div class="form-hint">
              重要！填写后 AI 可精准定向检索该基金代码相关文档
            </div>
          </el-form-item>
          <el-form-item label="业务标签">
            <el-input
              v-model="uploadForm.bizTags"
              placeholder="如：A股,大盘（英文逗号分隔）"
            />
          </el-form-item>
          <el-form-item label="发布日期">
            <el-date-picker
              v-model="uploadForm.publishDate"
              type="date"
              placeholder="选择文档发布日期"
              value-format="YYYY-MM-DD"
              class="w-full"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button
          @click="
            uploadDialogVisible = false;
            resetUploadForm();
          "
          >取消</el-button
        >
        <el-button
          type="primary"
          :loading="uploadLoading"
          @click="handleUploadSubmit"
        >
          上传并入库
        </el-button>
      </template>
    </el-dialog>

    <!-- ============= Chunk 预览对话框 ============= -->
    <el-dialog
      v-model="chunkDialogVisible"
      :title="`切块预览 — ${currentDocName}`"
      width="800px"
      draggable
    >
      <div class="chunk-dialog-tip">
        共 <strong>{{ chunkList.length }}</strong> 个 Chunk。 RAGLite
        通过最优语义切分算法确定切块边界，点击编辑图标可修正 OCR
        识别错误并重新向量化。
      </div>

      <div class="chunk-list" v-loading="chunkLoading">
        <div v-for="chunk in chunkList" :key="chunk.chunk_id" class="chunk-item">
          <!-- Chunk 头部 -->
          <div class="chunk-header">
            <span class="chunk-index">#{{ chunk.chunk_index + 1 }}</span>
            <span v-if="chunk.title_path?.length" class="chunk-path">
              {{ chunk.title_path.join(" › ") }}
            </span>
            <el-button
              v-if="editingChunk?.chunk_id !== chunk.chunk_id"
              size="small"
              text
              type="primary"
              @click="handleEditChunk(chunk)"
              >编辑</el-button
            >
            <template v-else>
              <el-button
                size="small"
                type="success"
                @click="handleSaveChunk(chunk)"
                >保存</el-button
              >
              <el-button size="small" @click="editingChunk = null"
                >取消</el-button
              >
            </template>
          </div>

          <!-- Chunk 内容：浏览模式使用 Markdown 渲染 -->
          <div
            v-if="editingChunk?.chunk_id !== chunk.chunk_id"
            class="chunk-content"
            v-html="renderMarkdown(chunk.content)"
          />
          <el-input
            v-else
            v-model="editContent"
            type="textarea"
            :rows="6"
            class="chunk-editor"
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="chunkDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ========== 整体布局 ========== */
.knowledge-registry {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family: "Inter", "PingFang SC", sans-serif;
}

/* ========== 顶部操作栏 ========== */
.header-bar {
  background: #fff;
  border: 2px solid #000;
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 4px 4px 0 #000;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-icon {
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, #4285f4, #174ea6);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(66, 133, 244, 0.3);
}
.header-title {
  font-weight: 800;
  font-size: 18px;
  margin: 0;
  color: #111;
}
.header-subtitle {
  font-size: 10px;
  color: #999;
  margin: 0;
  font-family: "JetBrains Mono", monospace;
  letter-spacing: 0.5px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.upload-btn {
  font-weight: 700;
}
.w-36 {
  width: 144px;
}
.w-44 {
  width: 176px;
}

/* ========== 统计数据条 ========== */
.stats-bar {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 0;
  flex-shrink: 0;
}
.stat-item {
  flex: 1;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-num {
  font-size: 24px;
  font-weight: 800;
  color: #1a202c;
  font-family: "JetBrains Mono", monospace;
}
.stat-num.success {
  color: #10b981;
}
.stat-num.warning {
  color: #f59e0b;
}
.stat-num.danger {
  color: #ef4444;
}
.stat-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.stat-divider {
  width: 1px;
  height: 40px;
  background: #e2e8f0;
  margin: 0 8px;
}

/* ========== 文档卡片网格 ========== */
.doc-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  padding: 4px 2px;
}

/* 空状态 */
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 0;
  color: #94a3b8;
}
.empty-icon {
  opacity: 0.3;
}
.empty-text {
  font-size: 20px;
  font-weight: 700;
  color: #475569;
  margin: 0;
}
.empty-sub {
  font-size: 13px;
  color: #94a3b8;
  margin: 0;
}

/* 文档卡片 */
.doc-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.25s;
  position: relative;
}
.doc-card:hover {
  border-color: #4285f4;
  box-shadow: 0 8px 24px rgba(66, 133, 244, 0.15);
  transform: translateY(-2px);
}

.card-status-bar {
  height: 4px;
  width: 100%;
  flex-shrink: 0;
  transition: background 0.3s;
}

.card-type-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 10px;
  font-weight: 800;
  color: #174ea6;
  background: #e8f0fe;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 0.3px;
}

.card-filename {
  padding: 16px 16px 8px;
  min-height: 56px;
  display: flex;
  align-items: flex-start;
}
.filename-text {
  font-size: 14px;
  font-weight: 700;
  color: #1a202c;
  line-height: 1.5;
  word-break: break-all;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-status-row {
  padding: 0 16px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid;
}

.spinning {
  animation: spin 1.2s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.chunk-count {
  font-size: 11px;
  color: #94a3b8;
  font-family: "JetBrains Mono", monospace;
  margin-left: auto;
}

.card-meta {
  padding: 0 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.meta-label {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  width: 52px;
  flex-shrink: 0;
}
.meta-value {
  font-size: 12px;
  color: #475569;
}
.meta-value.mono {
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}
.meta-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.code-tag {
  font-size: 10px;
  font-weight: 700;
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fcd34d;
  padding: 1px 6px;
  border-radius: 4px;
  font-family: "JetBrains Mono", monospace;
}
.more-tag {
  font-size: 10px;
  color: #94a3b8;
  padding: 1px 4px;
}

.card-actions {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.error-msg {
  padding: 8px 16px;
  background: #fff5f5;
  border-top: 1px solid #fed7d7;
  font-size: 11px;
  color: #e53e3e;
  font-family: monospace;
  word-break: break-all;
  line-height: 1.5;
}

/* ========== 上传对话框 ========== */
.upload-dialog-body {
  padding: 0 8px;
}
.upload-zone :deep(.el-upload-dragger) {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  background: #f8faff;
  transition: all 0.2s;
}
.upload-zone :deep(.el-upload-dragger:hover) {
  border-color: #4285f4;
  background: #e8f0fe;
}
.upload-dragger-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.upload-icon {
  color: #4285f4;
  opacity: 0.7;
}
.upload-main-text {
  font-size: 14px;
  color: #475569;
}
.upload-main-text em {
  color: #4285f4;
  font-style: normal;
  font-weight: 700;
}
.upload-sub-text {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  display: block;
}
.selected-file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #e8f0fe;
  border-top: 1px dashed #4285f4;
  font-size: 13px;
  color: #174ea6;
  font-weight: 600;
}
.file-size {
  margin-left: auto;
  color: #6b7280;
  font-size: 11px;
  font-family: monospace;
}
.form-hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}
.w-full {
  width: 100%;
}

/* ========== Chunk 预览对话框 ========== */
.chunk-dialog-tip {
  padding: 10px 16px;
  background: #eff6ff;
  border-radius: 8px;
  font-size: 13px;
  color: #1e40af;
  margin-bottom: 16px;
  border: 1px solid #bfdbfe;
}
.chunk-list {
  max-height: 480px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chunk-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.chunk-header {
  background: #f8fafc;
  padding: 8px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #e5e7eb;
}
.chunk-index {
  font-size: 11px;
  font-weight: 900;
  color: #4285f4;
  font-family: "JetBrains Mono", monospace;
  background: #e8f0fe;
  padding: 2px 6px;
  border-radius: 4px;
}
.chunk-path {
  font-size: 11px;
  color: #64748b;
  flex: 1;
}
.chunk-content {
  padding: 12px 14px;
  font-size: 13px;
  color: #374151;
  line-height: 1.7;
  background: #fff;
  max-height: 360px;
  overflow-y: auto;
}

/* ===== Markdown 渲染样式 ===== */
.chunk-content :deep(.md-body),
.chunk-content :deep(p.md-p) {
  margin: 0 0 8px;
  line-height: 1.75;
  color: #374151;
  font-size: 13px;
}
.chunk-content :deep(.md-h) {
  font-weight: 700;
  color: #111827;
  margin: 12px 0 6px;
  line-height: 1.4;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 4px;
}
.chunk-content :deep(h1.md-h) { font-size: 18px; }
.chunk-content :deep(h2.md-h) { font-size: 16px; }
.chunk-content :deep(h3.md-h) { font-size: 15px; }
.chunk-content :deep(h4.md-h),
.chunk-content :deep(h5.md-h),
.chunk-content :deep(h6.md-h) { font-size: 13px; }
.chunk-content :deep(.md-table-wrap) {
  overflow-x: auto;
  margin: 8px 0;
}
.chunk-content :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: #fff;
}
.chunk-content :deep(.md-table th) {
  background: #eff6ff;
  color: #1e40af;
  font-weight: 700;
  padding: 6px 10px;
  border: 1px solid #bfdbfe;
  text-align: left;
  white-space: nowrap;
}
.chunk-content :deep(.md-table td) {
  padding: 5px 10px;
  border: 1px solid #e5e7eb;
  color: #374151;
  vertical-align: top;
}
.chunk-content :deep(.md-table tr:hover td) {
  background: #f0f9ff;
}
.chunk-content :deep(.md-pre) {
  background: #1e2535;
  border-radius: 6px;
  padding: 12px 14px;
  margin: 8px 0;
  overflow-x: auto;
}
.chunk-content :deep(.md-code-block) {
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 12px;
  color: #e2e8f0;
  white-space: pre;
  display: block;
}
.chunk-content :deep(.md-inline-code) {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  background: #f1f5f9;
  color: #e11d48;
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid #e2e8f0;
}
.chunk-content :deep(.md-hr) {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 10px 0;
}
.chunk-content :deep(strong) {
  font-weight: 700;
  color: #1a202c;
}
.chunk-editor {
  padding: 8px;
}
</style>
