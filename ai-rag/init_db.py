import psycopg
import sys
import os

# 将 src 目录加入路径，以便加载配置
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from ai_rag.config import get_settings

def init_db():
    """
    功能: 初始化 PostgreSQL 数据库，创建知识库元数据管理表
    """
    settings = get_settings()
    # 解析数据库连接串 (例如: postgresql://user:pass@host:port/dbname)
    db_url = settings.database_url
    
    print(f"正在连接数据库进行初始化: {db_url}")
    
    try:
        # 1. 检查并创建扩展及表
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                # 检查 pgvector 扩展
                print("检查 pgvector 扩展...")
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
                # 读取 SQL 文件并执行
                sql_path = os.path.join(os.path.dirname(__file__), "..", "docs", "sql", "knowledge_documents.sql")
                if os.path.exists(sql_path):
                    print(f"执行 SQL 脚本: {sql_path}")
                    with open(sql_path, "r", encoding="utf-8") as f:
                        sql_script = f.read()
                        cur.execute(sql_script)
                    print("数据库表结构初始化成功！")
                else:
                    print(f"错误: 找不到 SQL 脚本 {sql_path}")
                    
    except Exception as e:
        print(f"初始化数据库失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
