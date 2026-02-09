"""
数据库连接管理模块
使用 psycopg 连接池管理 PostgreSQL 连接
"""

import json
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

import psycopg
from psycopg.rows import dict_row
try:
    from psycopg_pool import ConnectionPool
    HAS_POOL = True
except ImportError:
    ConnectionPool = object
    HAS_POOL = False

from ..config import get_settings


class DatabaseManager:
    """
    功能: 数据库连接池管理器
    参数: database_url - PostgreSQL 连接字符串
    返回: DatabaseManager 实例，提供连接池和查询方法
    """
    
    def __init__(self, database_url: str):
        """
        功能: 初始化数据库连接池
        参数: database_url - PostgreSQL 连接字符串
        返回: None
        """
        if not HAS_POOL:
            print("[DatabaseManager] 警告: psycopg_pool 模块未安装，数据库直连功能将不可用。")
            self._pool = None
            return

        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=2,
            max_size=10,
            kwargs={"row_factory": dict_row}  # 返回字典格式的行
        )
    
    @contextmanager
    def get_connection(self):
        """
        功能: 获取数据库连接（上下文管理器）
        参数: 无
        返回: psycopg.Connection 实例
        """
        with self._pool.connection() as conn:
            yield conn
    
    def execute_query(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """
        功能: 执行查询并返回所有结果
        参数: 
            query - SQL 查询语句
            params - 查询参数（可选）
        返回: 字典列表，每个字典代表一行数据
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
    
    def get_tool_cards(self, is_online: bool = True) -> list[dict[str, Any]]:
        """
        功能: 获取所有工具卡片定义
        参数: is_online - 是否只获取上线的工具（默认 True）
        返回: tool_cards 表的记录列表
        """
        query = """
            SELECT 
                tool_name,
                tool_description,
                tool_tags,
                tool_version,
                tool_privileges,
                tool_protocol,
                url_path,
                reference_target,
                tool_parameters,
                output_schema,
                input_examples,
                output_examples,
                is_online
            FROM tool_cards
            WHERE is_online = %s
        """
        return self.execute_query(query, (is_online,))
    
    def get_tool_card_by_name(self, tool_name: str) -> dict[str, Any] | None:
        """
        功能: 根据工具名称获取单个工具卡片
        参数: tool_name - 工具唯一标识
        返回: 工具卡片字典，如果不存在则返回 None
        """
        query = """
            SELECT 
                tool_name,
                tool_description,
                tool_tags,
                tool_version,
                tool_privileges,
                tool_protocol,
                url_path,
                reference_target,
                tool_parameters,
                output_schema,
                input_examples,
                output_examples,
                is_online
            FROM tool_cards
            WHERE tool_name = %s
        """
        results = self.execute_query(query, (tool_name,))
        return results[0] if results else None
    
    def get_agent_cards(self, is_online: bool = True) -> list[dict[str, Any]]:
        """
        功能: 获取所有 Agent 卡片定义
        参数: is_online - 是否只获取上线的 Agent（默认 True）
        返回: agent_cards 表的记录列表
        """
        query = """
            SELECT 
                agent_name,
                agent_description,
                agent_alias,
                agent_tags,
                system_prompt,
                negative_prompt,
                bound_tools,
                reasoning_framework,
                agent_version,
                is_online
            FROM agent_cards
            WHERE is_online = %s
        """
        return self.execute_query(query, (is_online,))
    
    def get_agent_card_by_name(self, agent_name: str) -> dict[str, Any] | None:
        """
        功能: 根据 Agent 名称获取单个 Agent 卡片
        参数: agent_name - Agent 唯一标识
        返回: Agent 卡片字典，如果不存在则返回 None
        """
        query = """
            SELECT 
                agent_name,
                agent_description,
                agent_alias,
                agent_tags,
                system_prompt,
                negative_prompt,
                bound_tools,
                reasoning_framework,
                agent_version,
                is_online
            FROM agent_cards
            WHERE agent_name = %s
        """
        results = self.execute_query(query, (agent_name,))
        return results[0] if results else None
    
    def close(self):
        """
        功能: 关闭连接池
        参数: 无
        返回: None
        """
        if self._pool:
            self._pool.close()


# 全局单例
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """
    功能: 获取全局 DatabaseManager 单例
    参数: 无
    返回: DatabaseManager 实例
    """
    global _db_manager
    if _db_manager is None:
        settings = get_settings()
        _db_manager = DatabaseManager(settings.database_url)
    return _db_manager
