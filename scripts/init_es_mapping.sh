#!/bin/bash
# ============================================
# ES 索引初始化脚本
# 功能: 创建 ai_chat_trace_index_snapshot 索引
# 用法: bash scripts/init_es_mapping.sh
# ============================================

ES_HOST="${ES_HOST:-http://localhost:9200}"
INDEX_NAME="ai_chat_trace_index_snapshot"

echo ">>> 正在初始化 ES 索引: ${INDEX_NAME} ..."
echo ">>> ES 地址: ${ES_HOST}"

# 删除已存在的索引（谨慎使用）
# curl -s -X DELETE "${ES_HOST}/${INDEX_NAME}" && echo ""

# 创建索引并设置映射
curl -s -X PUT "http://localhost:9200/ai_chat_trace_index_snapshot" \
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
      "timestamp":   { "type": "date" },

      "env_snapshot": {
        "properties": {
          "agent_name":     { "type": "keyword" },
          "agent_version":  { "type": "keyword" },
          "model_config": {
            "properties": {
              "provider":    { "type": "keyword" },
              "model_name":  { "type": "keyword" },
              "temperature": { "type": "float" },
              "top_p":       { "type": "float" },
              "max_tokens":  { "type": "integer" }
            }
          },
          "system_prompt": { "type": "text", "index": false }
        }
      },

      "dialogue_snapshot": {
        "properties": {
          "user_query_full":   { "type": "text", "index": false },
          "history_window":    { "type": "object", "enabled": false },
          "ai_response_full":  { "type": "text", "index": false },
          "finish_reason":     { "type": "keyword" },
          "total_tokens":      { "type": "integer" }
        }
      },

      "tool_snapshots": {
        "type": "nested",
        "properties": {
          "tool_name":     { "type": "keyword" },
          "tool_type":     { "type": "keyword" },
          "start_time":    { "type": "date" },
          "end_time":      { "type": "date" },
          "latency_ms":    { "type": "integer" },
          "status":        { "type": "keyword" },
          "input_args":    { "type": "text", "index": false },
          "output_result": { "type": "text", "index": false },
          "error_message": { "type": "text", "index": false }
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
