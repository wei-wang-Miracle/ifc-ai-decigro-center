#!/bin/bash
# ============================================
# ES 索引初始化脚本（v2 — graph_nodes 结构）
# 功能: 创建 ai_chat_trace_index_snapshot 索引
# 用法: bash scripts/init_es_mapping.sh
# ============================================

ES_HOST="${ES_HOST:-http://localhost:9200}"
INDEX_NAME="ai_chat_trace_index_snapshot"

echo ">>> 正在初始化 ES 索引: ${INDEX_NAME} ..."
echo ">>> ES 地址: ${ES_HOST}"

# 删除已存在的索引（升级时需要取消注释）
echo ">>> 正在尝试删除旧索引..."
curl -s -X DELETE "${ES_HOST}/${INDEX_NAME}" && echo ""

# 创建索引并设置映射（v2 — 与 trace_utils.py 同步）
curl -s -X PUT "${ES_HOST}/${INDEX_NAME}" \
  -H 'Content-Type: application/json' \
  -d '{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "5s"
  },
  "mappings": {
    "properties": {
      "trace_id":    { "type": "keyword" },
      "session_id":  { "type": "keyword" },
      "task_id":     { "type": "keyword" },
      "user_id":     { "type": "keyword" },
      "dept_id":     { "type": "keyword" },
      "start_time":  { "type": "date" },

      "dialogue_summary": {
        "properties": {
          "user_query":      { "type": "text", "index": false },
          "ai_response":     { "type": "text", "index": false },
          "history_length":  { "type": "integer" }
        }
      },

      "graph_nodes": {
        "type": "nested",
        "properties": {
          "node_name":   { "type": "keyword" },
          "start_time":  { "type": "date" },
          "end_time":    { "type": "date" },
          "latency_ms":  { "type": "integer" },
          "status":      { "type": "keyword" },

          "agent_snapshots": {
            "type": "nested",
            "properties": {
              "agent_name":     { "type": "keyword" },
              "agent_version":  { "type": "keyword" },
              "status":         { "type": "keyword" },
              "model_config":   { "type": "object", "enabled": false },
              "system_prompt":  { "type": "text", "index": false },

              "tools_snapshot": {
                "type": "nested",
                "properties": {
                  "tool_name":     { "type": "keyword" },
                  "tool_type":     { "type": "keyword" },
                  "start_time":    { "type": "date" },
                  "latency_ms":    { "type": "integer" },
                  "status":        { "type": "keyword" },
                  "input_args":    { "type": "object", "enabled": false },
                  "output_result": { "type": "text", "index": false },
                  "error_message": { "type": "text", "index": false }
                }
              }
            }
          }
        }
      }
    }
  }
}' | python3 -m json.tool 2>/dev/null || echo "(json 格式化失败，但请求可能已成功)"

echo ""
echo ">>> 验证索引映射..."
curl -s "${ES_HOST}/${INDEX_NAME}/_mapping" | python3 -m json.tool 2>/dev/null

echo ""
echo ">>> ES 索引初始化完成!"
