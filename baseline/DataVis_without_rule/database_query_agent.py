"""
DatabaseQueryAgent - 移除规则约束版本

本文件已移除以下规则约束，让agent能够更自由地决定行为：

1. 移除了system prompt中的严格指导原则和"MUST"要求
2. 移除了工具参数的硬性限制（sample_size和max_rows的最大值约束）
3. 移除了强制性的查询验证要求
4. 移除了预定义的详细工作流程指导
5. 移除了预迭代步骤中的强制工具使用模式
6. 移除了严格的输出格式要求
7. 移除了文件存在性的阻塞验证，改为异常处理
8. 移除了参数验证约束，让agent自由选择参数值

现在agent可以根据情况自由选择SQL生成策略，不受预定义规则约束。
即使某些操作失败，agent也能继续尝试其他方法。
"""

import os
import json
import sqlite3
import pandas as pd
from typing import Dict, List, Tuple
import re
import base64
import altair as alt
import matplotlib.pyplot as plt
import traceback
import io
from contextlib import redirect_stdout, redirect_stderr

# 导入基类
from .utils.Agent import Agent


class DatabaseQueryAgent(Agent):
    """数据库与查询智能体（Database & Query Agent）
    
    负责分析数据库结构、理解表结构、构建并执行SQL查询。
    提供接口：
    - generate_sql_from_query: 根据用户查询生成SQL查询语句
    
    该智能体主要依赖LLM的结构化理解能力和SQL生成能力。
    """
    
    def __init__(self, model_type: str = "gemini-2.0-flash@gemini-2.0-flash", agent_name: str = "database_query_agent", agent_id: str = 0, use_log: bool = False):
        """初始化数据库与查询智能体
        
        Args:
            model_type: 使用的模型种类，格式为text_model@img_model，默认为qwen-max-2025-01-25@qwen-vl-max-2025-01-25
            agent_name: 智能体名称
            agent_id: 智能体ID
        """
        system_prompt = """You are a database analyst specializing in SQL query generation for data visualization tasks. Your goal is to understand user requirements and generate appropriate SQL queries.

## Capabilities
- Analyze database schemas and table structures
- Generate SQL queries based on user requests and visual references
- Execute and test SQL queries
- Work with various database structures and relationships

## Available Tools
- list_tables: Get database table names
- get_table: Get table structure and sample data
- get_foreign_keys: Get table relationships
- execute_sql: Execute SQL queries
- find_fields_in_tables: Find fields across tables

Use these tools and your expertise to create effective SQL queries that meet user needs.
"""

        super().__init__(model_type=model_type, system_prompt=system_prompt, agent_name=agent_name, agent_id=agent_id, use_log=use_log)
        
        # 注册数据库工具
        self._register_db_tools()
        
        self._log("数据库与查询智能体初始化完成")
    
    def _register_db_tools(self):
        """注册数据库相关工具"""
        # 1. 列出数据库表
        self.register_tool(
            tool_name="list_tables",
            tool_func=self._list_tables_tool,
            tool_description="Get a list of all table names in the database",
            tool_parameters={
                "db_path": {
                    "type": "string",
                    "description": "Database file path"
                }
            },
            required=["db_path"]
        )
        
        # 2. 获取指定表的结构和示例数据
        self.register_tool(
            tool_name="get_table",
            tool_func=self._get_table_tool,
            tool_description="Get structure information and sample data for one or more tables",
            tool_parameters={
                "db_path": {
                    "type": "string",
                    "description": "Database file path"
                },
                "table_names": {
                    "type": "array",
                    "description": "List of table names"
                },
                "sample_size": {
                    "type": "integer",
                    "description": "Number of sample rows to return from each table"
                }
            },
            required=["db_path", "table_names"]
        )
        
        # 3. 获取表之间的关系
        self.register_tool(
            tool_name="get_foreign_keys",
            tool_func=self._get_foreign_keys_tool,
            tool_description="Get foreign key relationships between tables",
            tool_parameters={
                "db_path": {
                    "type": "string",
                    "description": "Database file path"
                },
                "table_names": {
                    "type": "array",
                    "description": "List of table names (optional, if provided only returns foreign key relationships for those tables)"
                }
            },
            required=["db_path"]
        )
        
        # 4. 执行SQL查询
        self.register_tool(
            tool_name="execute_sql",
            tool_func=self._execute_sql_tool,
            tool_description="Execute SQL query and get results",
            tool_parameters={
                "db_path": {
                    "type": "string",
                    "description": "Database file path"
                },
                "sql_query": {
                    "type": "string",
                    "description": "SQL query to execute"
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Maximum number of rows to return"
                }
            },
            required=["db_path", "sql_query"]
        )
        
        # 5. 查找字段所在的表
        self.register_tool(
            tool_name="find_fields_in_tables",
            tool_func=self._find_fields_in_tables_tool,
            tool_description="Find tables containing specified field names",
            tool_parameters={
                "db_path": {
                    "type": "string",
                    "description": "Database file path"
                },
                "field_names": {
                    "type": "array",
                    "description": "List of field names to find in tables"
                }
            },
            required=["db_path", "field_names"]
        )
        
        self._log("数据库工具注册完成")
    
    def _list_tables_tool(self, db_path: str) -> str:
        """获取数据库中的所有表名
        
        Args:
            db_path: A数据库文件路径
            
        Returns:
            str: Markdown格式的表名列表
        """
        self._log(f"获取数据库表列表: {db_path}")
        
        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 获取表名列表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if not tables:
                return "No tables found in the database."
            
            # 构建Markdown格式的表名列表
            tables_md = f"## Tables in database: {os.path.basename(db_path)}\n\n"
            tables_md += "| Table Name |\n"
            tables_md += "| ---- |\n"
            
            for table in tables:
                table_name = table[0]
                if not table_name.startswith('sqlite_'):  # 跳过SQLite内部表
                    tables_md += f"| {table_name} |\n"
            
            self._log("成功获取数据库表列表")
            return tables_md
            
        except Exception as e:
            error_msg = f"获取数据库表列表失败: {str(e)}"
            self._log(error_msg)
            return f"Error: Failed to get table list: {str(e)}"
    
    def _get_table_tool(self, db_path: str, table_names: List[str], sample_size: int = 5) -> str:
        """获取特定表的结构信息和示例数据
        
        Args:
            db_path: 数据库文件路径
            table_names: 表名列表
            sample_size: 每个表的示例数据行数，默认为5
            
        Returns:
            str: Markdown格式的表结构信息和示例数据
        """
        self._log(f"获取表结构和示例数据: {table_names}, 示例行数: {sample_size}")
        
        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 构建Markdown格式的表结构和示例数据
            result_md = "## Database Table Information\n\n"
            
            for table_name in table_names:
                # 检查表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                if not cursor.fetchone():
                    result_md += f"### Table: {table_name}\n\nError: Table does not exist\n\n"
                    continue
                
                # 添加表标题
                result_md += f"### Table: {table_name}\n\n"
                
                # 获取表结构并添加
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                
                if not columns:
                    result_md += "Table has no column definitions.\n\n"
                    continue
                
                # 添加表结构信息
                result_md += "#### Structure:\n\n"
                result_md += "| Column Name | Data Type | Primary Key | Allow Null | Default Value |\n"
                result_md += "| ---- | -------- | ---- | -------- | ------ |\n"
                
                for col in columns:
                    col_name = col[1]
                    col_type = col[2]
                    is_pk = "Yes" if col[5] else "No"
                    not_null = "No" if col[3] else "Yes"
                    default_val = col[4] if col[4] is not None else ""
                    
                    result_md += f"| {col_name} | {col_type} | {is_pk} | {not_null} | {default_val} |\n"
                
                result_md += "\n"
                
                # 获取表的前N条数据作为示例
                cursor.execute(f"SELECT * FROM {table_name} LIMIT ?;", (sample_size,))
                sample_data = cursor.fetchall()
                
                # 添加示例数据
                result_md += "#### Sample Data:\n\n"
                
                if not sample_data:
                    result_md += "Table has no data.\n\n"
                    continue
                
                # 获取列名（已经从PRAGMA表中获取过了）
                col_names = [col[1] for col in columns]
                
                # 构建表头
                result_md += "| " + " | ".join(col_names) + " |\n"
                result_md += "| " + " | ".join(["----" for _ in col_names]) + " |\n"
                
                # 构建数据行
                for row in sample_data:
                    result_md += "| " + " | ".join([str(val) if val is not None else "" for val in row]) + " |\n"
                
                result_md += "\n"
            
            conn.close()
            
            self._log(f"成功获取表结构和示例数据: {table_names}")
            return result_md
            
        except Exception as e:
            error_msg = f"获取表结构和示例数据失败: {str(e)}"
            self._log(error_msg)
            return f"Error: Failed to get table information: {str(e)}"
    
    def _get_foreign_keys_tool(self, db_path: str, table_names: List[str] = None) -> str:
        """获取表之间的外键关系
        
        Args:
            db_path: 数据库文件路径
            table_names: 可选的表名列表，如果提供则只返回这些表的外键关系
            
        Returns:
            str: Markdown格式的外键关系
        """
        self._log(f"获取外键关系, 表名: {table_names if table_names else '所有表'}")
        
        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 获取表名列表
            if table_names:
                # 过滤出存在的表
                tables = []
                for table_name in table_names:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                    result = cursor.fetchone()
                    if result:
                        tables.append(result)
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
            
            # 构建Markdown格式的外键关系
            fk_md = "## Database Foreign Key Relationships\n\n"
            has_relations = False
            
            for table in tables:
                t_name = table[0]
                if t_name.startswith('sqlite_'):
                    continue  # 跳过SQLite内部表
                
                cursor.execute(f"PRAGMA foreign_key_list({t_name});")
                foreign_keys = cursor.fetchall()
                
                if foreign_keys:
                    has_relations = True
                    fk_md += f"### Foreign key relationships for table: {t_name}\n\n"
                    
                    for fk in foreign_keys:
                        ref_table = fk[2]  # 引用的表
                        from_col = fk[3]   # 本表的列
                        to_col = fk[4]     # 引用表的列
                        fk_md += f"- Column `{from_col}` references table `{ref_table}` column `{to_col}`\n"
                    
                    fk_md += "\n"
            
            conn.close()
            
            if not has_relations:
                fk_md += "No foreign key relationships detected between the specified tables.\n"
            
            self._log("成功获取外键关系")
            return fk_md
            
        except Exception as e:
            error_msg = f"获取外键关系失败: {str(e)}"
            self._log(error_msg)
            return f"Error: Failed to get foreign key relationships: {str(e)}"
    
    def _execute_sql_tool(self, db_path: str, sql_query: str, max_rows: int = 20) -> str:
        """执行SQL查询工具函数
        
        Args:
            db_path: 数据库文件路径
            sql_query: SQL查询语句
            max_rows: 返回的最大行数（默认为20）
            
        Returns:
            str: Markdown格式的查询结果
        """
        self._log(f"执行SQL查询: {sql_query}, 最大行数: {max_rows}")

        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            
            # 使用pandas执行查询并获取结果
            df = pd.read_sql_query(sql_query, conn)
            conn.close()
            
            if df.empty:
                return "Query returned no results."
            
            # 转换为Markdown格式的表格
            result_md = "## Query Results\n\n"
            
            # 添加表头
            result_md += "| " + " | ".join(df.columns) + " |\n"
            result_md += "| " + " | ".join(["----" for _ in df.columns]) + " |\n"
            
            # 添加数据行（最多显示max_rows行）
            displayed_rows = min(max_rows, len(df)) if max_rows > 0 else len(df)
            for _, row in df.iloc[:displayed_rows].iterrows():
                result_md += "| " + " | ".join([str(val) if val is not None else "" for val in row]) + " |\n"
            
            # 如果结果超过max_rows行，添加说明
            if max_rows > 0 and len(df) > max_rows:
                result_md += f"\n*Query returned {len(df)} rows, only showing the first {max_rows} rows above.*\n"
            
            # 添加数据统计信息
            result_md += "\n## Data Statistics\n\n"
            result_md += f"- Total rows: {len(df)}\n"
            result_md += f"- Total columns: {len(df.columns)}\n"
            
            self._log("成功执行SQL查询")
            
            return result_md
            
        except Exception as e:
            error_msg = f"执行SQL查询失败: {str(e)}"
            self._log(error_msg)
            return f"Error: Failed to execute SQL query: {str(e)}"
    
    def _find_fields_in_tables_tool(self, db_path: str, field_names: List[str]) -> str:
        """查找字段所在的表工具函数
        
        Args:
            db_path: 数据库文件路径
            field_names: 要查找的字段名列表
            
        Returns:
            str: Markdown格式的查找结果
        """
        self._log(f"查找字段所在的表: {field_names}")
        
        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [table[0] for table in cursor.fetchall() if not table[0].startswith('sqlite_')]
            
            if not tables:
                conn.close()
                return "No tables found in the database."
            
            # 初始化结果
            results = {}
            for field in field_names:
                results[field] = []
            
            # 遍历每个表检查字段
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                for field in field_names:
                    if field in column_names:
                        results[field].append(table)
            
            conn.close()
            
            # 构建Markdown格式的结果
            md_result = "## Field to Table Mapping Results\n\n"
            md_result += "| Field Name | Tables |\n"
            md_result += "| ---------- | ------ |\n"
            
            for field, tables in results.items():
                if tables:
                    table_list = ", ".join(tables)
                    md_result += f"| {field} | {table_list} |\n"
                else:
                    md_result += f"| {field} | *Not found in any table* |\n"
            
            self._log("成功查找字段所在的表")
            return md_result
            
        except Exception as e:
            error_msg = f"查找字段所在的表失败: {str(e)}"
            self._log(error_msg)
            return f"Error: Failed to find fields in tables: {str(e)}"
    
    def _img_to_img_url(self, img_path: str) -> str:
        """将图片转换为image_url
        
        支持jpg、png、jpeg格式
        
        Args:
            img_path: 图片文件路径
            
        Returns:
            str: 图片的data URL
            
        Raises:
            ValueError: 如果图片不存在或格式不支持
        """
        if not os.path.exists(img_path):
            self._log(f"图片文件不存在: {img_path}")
            raise ValueError(f"图片文件不存在: {img_path}")
            
        # 获取文件扩展名并确定mime type
        ext = os.path.splitext(img_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        
        if ext not in mime_types:
            self._log(f"不支持的图片格式: {ext}，仅支持 {', '.join(mime_types.keys())}")
            raise ValueError(f"不支持的图片格式: {ext}，仅支持 {', '.join(mime_types.keys())}")
        
        try:
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:{mime_types[ext]};base64,{encoded_string}"
        except Exception as e:
            error_msg = f"读取图片文件失败: {str(e)}"
            self._log(error_msg)
            raise ValueError(error_msg)

    def _execute_altair_code(self, code_string: str, output_path: str) -> dict:
        """执行Altair代码并保存图像 (Simplified for SQL Agent)
        
        Args:
            code_string: 要执行的Altair代码
            output_path: 输出图像的保存路径
            
        Returns:
            dict: 执行结果，包含状态和信息 {status: 'success'/'fail', info: 'message'}
        """
        self._log(f"Attempting to execute Altair code and save to: {output_path}")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        namespace = {
            'alt': alt,
            'pd': pd,
            'np': __import__('numpy'),
            'sqlite3': __import__('sqlite3'),
            'io': io,
            'os': os
        }
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            modified_code = code_string
            last_chart_var = None
            chart_assignments = re.findall(r'(\w+)\s*=\s*alt\.Chart', modified_code)
            chart_assignments += re.findall(r'(\w+)\s*=\s*\(.*\)\.resolve_scale', modified_code)
            chart_assignments += re.findall(r'(\w+)\s*=.*?(?:chart|Chart)', modified_code)
            if chart_assignments:
                last_chart_var = chart_assignments[-1]
            last_line_match = re.search(r'^(\w+)\s*$', modified_code.split('\n')[-1].strip())
            if last_line_match:
                last_chart_var = last_line_match.group(1)

            if last_chart_var and ".save(" not in modified_code and "alt.save(" not in modified_code:
                save_code = f"\n\n# Save chart for SQL agent context\n{last_chart_var}.save('{output_path}')\n"
                modified_code += save_code
            
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(modified_code, namespace)
            
            if not os.path.exists(output_path):
                for var_name, var_value in namespace.items():
                    if isinstance(var_value, alt.TopLevelMixin):
                        var_value.save(output_path)
                        break
            
            if os.path.exists(output_path):
                return {"status": "success", "info": "Chart image saved for context."}
            else:
                return {"status": "fail", "info": "Execution seemingly successful but image not saved."}
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            return {"status": "fail", "info": f"Failed to execute Altair code: {error_msg}"}

    def _execute_matplotlib_code(self, code_string: str, output_path: str) -> dict:
        """执行Matplotlib代码并保存图像 (Simplified for SQL Agent)
        
        Args:
            code_string: 要执行的Matplotlib代码
            output_path: 输出图像的保存路径
            
        Returns:
            dict: 执行结果，包含状态和信息 {status: 'success'/'fail', info: 'message'}
        """
        self._log(f"Attempting to execute Matplotlib code and save to: {output_path}")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        namespace = {
            'pd': pd,
            'plt': plt,
            'np': __import__('numpy'),
            'sqlite3': __import__('sqlite3'),
            'os': os
        }
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            plt.close('all') # Ensure clean state
            modified_code = code_string
            modified_code = modified_code.replace("plt.show()", "")
            if "plt.savefig(" not in modified_code:
                modified_code += f"\n\n# Save chart for SQL agent context\nplt.savefig('{output_path}', bbox_inches='tight')\n"
            
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(modified_code, namespace)
            plt.savefig(output_path, bbox_inches='tight') # Ensure save happens
            plt.close('all')
            
            if os.path.exists(output_path):
                return {"status": "success", "info": "Chart image saved for context."}
            else:
                return {"status": "fail", "info": "Execution seemingly successful but image not saved."}
            
        except Exception as e:
            plt.close('all') # Ensure cleanup on error
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            return {"status": "fail", "info": f"Failed to execute Matplotlib code: {error_msg}"}

    def generate_sql_from_query(self, db_path: str, user_query: str, reference_path: str = None, existing_code_path: str = None) -> Tuple[bool, str]:
        """根据用户查询直接生成SQL查询语句，内部自动处理schema linking的生成和验证
        
        Args:
            db_path: 数据库文件路径
            user_query: 用户查询字符串
            reference_path: (可选)参考图像或参考代码的文件路径(.png/.jpg/.jpeg或.py文件)
            existing_code_path: (可选)已有代码的文件路径
            
        Returns:
            Tuple[bool, str]: 状态（成功/失败）和SQL查询语句
        """
        self._log(f"开始从用户查询直接生成SQL查询，数据库: {db_path}")
        
        # 准备参考素材和图像URL
        reference_code = None
        reference_type = None
        existing_code = None
        img_sources = [] # [(url, description), ...]
        temp_dir = "./temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        # 处理参考文件
        if reference_path:
            if reference_path.lower().endswith('.py'):
                reference_type = "code"
                try:
                    with open(reference_path, 'r', encoding='utf-8') as f:
                        reference_code = f.read()
                    self._log(f"成功加载参考代码: {reference_path}")
                    # Attempt to execute and get image
                    temp_img_path = os.path.join(temp_dir, f"ref_code_vis_{self.agent_id}.png")
                    if "import matplotlib" in reference_code or "from matplotlib" in reference_code:
                        exec_result = self._execute_matplotlib_code(reference_code, temp_img_path)
                    else:
                        exec_result = self._execute_altair_code(reference_code, temp_img_path)
                    
                    if exec_result["status"] == "success" and os.path.exists(temp_img_path):
                        try:
                            img_url = self._img_to_img_url(temp_img_path)
                            img_sources.append((img_url, "Visualization generated from the Reference Code:"))
                            self._log(f"成功生成并转换参考代码图像: {temp_img_path}")
                        except Exception as e:
                            self._log(f"转换参考代码图像失败: {str(e)}")
                    else:
                        self._log(f"执行参考代码生成图像失败: {exec_result.get('info', 'Unknown error')}")
                        # Continue without the image, but with the code text
                except Exception as e:
                    self._log(f"加载或处理参考代码失败: {str(e)}")
                    # Continue without the image, but with the code text
            elif reference_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                reference_type = "image"
                try:
                    img_url = self._img_to_img_url(reference_path)
                    img_sources.append((img_url, "Reference Image provided by user:"))
                    self._log(f"成功加载并转换参考图像: {reference_path}")
                except Exception as e:
                    self._log(f"加载或转换参考图像失败: {str(e)}")
                    # Continue without the image
            else:
                self._log(f"不支持的参考文件格式: {reference_path}")
                # Continue without reference
        
        # 处理已有代码
        if existing_code_path:
            try:
                with open(existing_code_path, 'r', encoding='utf-8') as f:
                    existing_code = f.read()
                self._log(f"成功加载已有代码: {existing_code_path}")
                # Attempt to execute and get image
                temp_img_path = os.path.join(temp_dir, f"existing_code_vis_{self.agent_id}.png")
                if "import matplotlib" in existing_code or "from matplotlib" in existing_code:
                    exec_result = self._execute_matplotlib_code(existing_code, temp_img_path)
                else:
                    exec_result = self._execute_altair_code(existing_code, temp_img_path)
                
                if exec_result["status"] == "success" and os.path.exists(temp_img_path):
                    try:
                        img_url = self._img_to_img_url(temp_img_path)
                        img_sources.append((img_url, "Visualization generated from the Existing Code:"))
                        self._log(f"成功生成并转换现有代码图像: {temp_img_path}")
                    except Exception as e:
                        self._log(f"转换现有代码图像失败: {str(e)}")
                else:
                    self._log(f"执行现有代码生成图像失败: {exec_result.get('info', 'Unknown error')}")
            except Exception as e:
                self._log(f"加载或处理现有代码失败: {str(e)}")
                # Continue without the image, but with the code text
        
        # 构建提示词
        prompt = f"""
## SQL Query Generation Task
Generate an SQL query based on the user's visualization requirements.

### User Query
```plaintext
{user_query}
```

### Database Path
{db_path}

Create an SQL query that retrieves the data needed for the visualization described in the user query.
"""

        # If reference code was provided, add its text to the prompt
        if reference_type == "code" and reference_code:
            prompt += f"""
### Reference Code
```python
{reference_code}
```
Consider this reference code for context and patterns.
"""

        # If existing code was provided, add its text
        if existing_code:
            prompt += f"""
### Existing Code
```python
{existing_code}
```
Consider this existing code for context and patterns.
"""

        # Add image context if reference was an image file
        if reference_type == "image":
            prompt += """
### Reference Image Context
If an image is provided below, analyze its visual elements to understand the data structure needed.
"""

        prompt += """
### Output Format
<Final_Answer>
[SQL query]
</Final_Answer>
"""

        # Build the user messages list with image context
        user_content_list = []
        user_content_list.append({"type": "text", "text": prompt})

        if img_sources:
            self._log(f"Adding {len(img_sources)} image(s) to the prompt context.")
            for img_url, description in img_sources:
                # Add text description before the image
                user_content_list.append({"type": "text", "text": f"\n--- IMAGE CONTEXT ---\n{description}\n(Image follows)"})
                # Add the image URL
                user_content_list.append({"type": "image_url", "image_url": {"url": img_url}})
        
        # 直接开始对话，不预设工作流程
        user_messages = [{"role": "user", "content": user_content_list}]

        # 使用ReAct模式进行交互
        self._log("启动ReAct模式进行SQL生成")
        result, used_tool = self.chat_ReAct(
            user_messages=user_messages,
            # temperature=1.0,
            max_iterations=10
        )
        
        self._log(f"ReAct模式生成完成，使用工具: {'是' if used_tool else '否'}")
        
        # 提取SQL查询语句
        sql_query = self._extract_sql_from_result(result)
        
        # 返回结果，不强制验证
        if sql_query:
            self._log(f"成功提取SQL查询: {sql_query}")
            return True, sql_query
        else:
            self._log("无法提取SQL查询语句，返回原始结果")
            return False, result

    # 保留generate_sql_from_requirement作为兼容方法
    def generate_sql_from_requirement(self, db_path: str, requirement: str, reference_path: str = None, existing_code_path: str = None) -> Tuple[bool, str]:
        """根据用户需求直接生成SQL查询语句（兼容旧接口）
        
        Args:
            db_path: 数据库文件路径
            requirement: 用户需求字符串
            reference_path: (可选)参考图像或参考代码的文件路径(.png/.jpg/.jpeg或.py文件)
            existing_code_path: (可选)已有代码的文件路径
            
        Returns:
            Tuple[bool, str]: 状态（成功/失败）和SQL查询语句
        """
        return self.generate_sql_from_query(db_path, requirement, reference_path, existing_code_path)
            
    def _extract_sql_from_result(self, result: str) -> str:
        """从结果中提取SQL查询语句
        
        Args:
            result: LLM生成的结果文本
            
        Returns:
            str: 提取的SQL查询语句，如果没有找到则返回None
        """
        # 按优先级尝试不同的提取方法
        
        # 1. 先尝试从Final_Answer标签中提取
        final_pattern = r'<Final_Answer>\s*```(?:sql)?\s*([\s\S]*?)\s*```\s*</Final_Answer>'
        final_match = re.search(final_pattern, result, re.DOTALL | re.IGNORECASE)
        if final_match:
            sql_query = final_match.group(1).strip()
            self._log("成功从Final_Answer标签中提取SQL查询")
            return sql_query
            
        # 2. 如果没有找到标签，尝试从普通SQL代码块中提取
        sql_pattern = r'```(?:sql)?\s*([\s\S]*?)\s*```'
        sql_match = re.search(sql_pattern, result, re.DOTALL | re.IGNORECASE)
        if sql_match:
            sql_query = sql_match.group(1).strip()
            self._log("成功从代码块中提取SQL查询")
            return sql_query
            
        # 3. 如果还是没有找到，尝试直接使用正则查找SQL语句
        # 只匹配以SELECT开头的语句，不要求结尾有分号
        select_pattern = r'(SELECT[\s\S]*?)(;|$)'
        select_match = re.search(select_pattern, result, re.DOTALL | re.IGNORECASE)
        if select_match:
            sql_query = select_match.group(1).strip()
            self._log("使用正则表达式提取SQL查询")
            return sql_query
            
        # 如果所有方法都失败，返回None
        return None

    def execute_query(self, db_path: str, sql_query: str) -> Tuple[bool, Dict]:
        """执行SQL查询并返回结果
        
        Args:
            db_path: 数据库文件路径
            sql_query: SQL查询语句
            
        Returns:
            Tuple[bool, Dict]: 状态（成功/失败）和查询结果字典
        """
        self._log(f"开始执行SQL查询: {sql_query}")
        
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            error_msg = f"数据库文件不存在: {db_path}"
            self._log(error_msg)
            return False, {"error": f"Database file does not exist: {db_path}"}
        
        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            
            # 使用pandas执行查询并获取结果
            df = pd.read_sql_query(sql_query, conn)
            conn.close()
            
            # 转换DataFrame为字典格式
            result_dict = {
                "columns": df.columns.tolist(),
                "data": df.values.tolist(),
                "row_count": len(df),
                "column_count": len(df.columns)
            }
            
            # 添加数值列的统计信息
            stats = {}
            numeric_cols = df.select_dtypes(include=['number']).columns
            for col in numeric_cols:
                stats[col] = {
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median())
                }
            
            result_dict["statistics"] = stats
            
            self._log("成功执行SQL查询")
            return True, result_dict
            
        except Exception as e:
            error_msg = f"执行SQL查询失败: {str(e)}"
            self._log(error_msg)
            return False, {"error": f"Failed to execute SQL query: {str(e)}"}

if __name__ == "__main__":
    # 测试数据库与查询智能体
    import sys
    import os
    
    # 创建日志目录
    os.makedirs("./logs", exist_ok=True)
    
    # 初始化数据库与查询智能体
    db_agent = DatabaseQueryAgent(model_type="gemini-2.0-flash@gemini-2.0-flash", agent_id=50, use_log=True)
    
    db_agent._log("\n===== 测试 DatabaseQueryAgent =====")
    
    # 测试数据库路径
    db_path = "./database/activity_1.sqlite"
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        db_agent._log(f"\n数据库文件不存在: {db_path}")
        db_agent._log("请确保测试数据库文件存在")
        sys.exit(1)
    
    user_query = "Can you create an interactive scatter plot showing the relationship between students' ages and how many activities they participate in? I'd like to see each student represented as a circle, with different colors for each major so I can spot any patterns across different fields of study."
    db_path = "./database/activity_1.sqlite"
    # reference_path = "./DataVis-Bench/img/Uncertainties And Trends___line_chart_with_confidence_interval_band.png"

    status, sql_query_new = db_agent.generate_sql_from_query(db_path=db_path, user_query=user_query)

    db_agent._log(f"SQL查询生成结果: {status}")
    db_agent._log(f"生成的SQL查询: {sql_query_new}")
    
    db_agent._log("\n===== 测试完成 =====") 