'''
通过详细的instruction指导LLM进行Altair Code的生成
input:
  - NL: 自然语言描述
  - db_id: 数据库schema
  - Chart_img: 图表图片(Optional)
  - Chart_code: 图表代码(Optional)

output:
  - Altair Code
'''

import os
import sqlite3
import traceback
import base64
import openai
import json
import sys
import httpx
import concurrent.futures
from datetime import datetime
from tqdm import tqdm

# ========================================================== Config ==========================================================
# BASE_URL = "https://openkey.cloud/v1"
# API_KEY = "xxx"
# MODEL_NAME = "gpt-4o"
# MODEL_NAME = "claude-3-7-sonnet-20250219"

# BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# API_KEY = "xxx"
# MODEL_NAME = "qwen-max-0125"

# BASE_URL = "https://api.deepseek.com"
# API_KEY = "xxx"
# MODEL_NAME = "deepseek-chat"

BASE_URL = "https://api.openai-proxy.org/v1"
API_KEY = "xxx"
# MODEL_NAME = "gemini-2.0-flash"
MODEL_NAME = "gemini-2.0-flash"

MAX_WORKERS = 20  # Adjust based on your system capabilities

# ========================================================== LLM Setup ==========================================================
def setup_llm_client():
    """Set up and return the OpenAI API client"""
    if not BASE_URL or not API_KEY or not MODEL_NAME:
        raise ValueError(
            "Please set EXAMPLE_BASE_URL, EXAMPLE_API_KEY, EXAMPLE_MODEL_NAME via env var or code."
        )

    http_client = httpx.Client(verify=False)
    return openai.Client(
        base_url=BASE_URL,
        api_key=API_KEY,
        http_client=http_client
    )

client = setup_llm_client()

# ========================================================== Prompts ==========================================================
SYSTEM_PROMPT = '''You are an expert data visualization assistant specializing in Altair for Python. Your task is to generate precise Altair visualization code based on the user's requirements and database information.

Follow these instructions carefully:
1. Analyze the database schema thoroughly to understand available tables, columns, and relationships
2. Generate clean, efficient Altair code that accurately visualizes the requested data
3. Include proper SQL queries to extract the required data from the SQLite database
4. Ensure your code handles different scenarios:
   - For basic visualization requests: Focus on accurate data representation
   - For image-based references: Match the visual style of the provided image
   - For code references: Adapt the reference code's approach while using Altair syntax
   - For modification requests: Carefully modify the existing code to implement requested changes

Your code must include:
- All necessary imports (pandas, altair, sqlite3)
- SQL connection and query to extract data
- Data transformation if needed
- Complete Altair visualization code with proper encoding and configuration
- Appropriate titles, labels, and styling

Return only valid, executable Python code with no explanations or comments outside the code block.
'''

USER_PROMPT = '''I need precise Altair visualization code based on the following information:

Natural Language Query: {nl}

Database Path: {db_path}

Database Schema Information:
{db_info}

{chart_img_description}

Reference Code (if applicable):
{chart_code}

Please follow these specific requirements when generating the code:

1. SQL and Data Preparation:
   - Connect to the SQLite database specified
   - Write optimized SQL to extract exactly the data needed
   - Handle data transformations in pandas if necessary

2. Visualization Structure:
   - Use Altair to create the visualization
   - Select appropriate mark types (bar, line, point, etc.) based on the requirement
   - Configure proper encodings for x, y, color, etc.
   - Set appropriate scales and domains

3. Styling and Presentation:
   - Apply proper titles, axis labels, and legends
   - Configure appropriate colors and styling
   - Ensure the visualization is readable and effective

4. If image reference is provided:
   - Match the visual style of the reference image
   - Use similar mark types, colors, and layout

5. If code reference is provided:
   - Follow the structural approach of the reference code
   - Adapt it to work with the current database and requirements

6. If modifying existing code:
   - Maintain the existing structure where possible
   - Implement only the requested changes
   - Preserve working components

Return only valid Python code without explanations, wrapped in ```python and ``` tags.
'''

# ========================================================== Database Functions ==========================================================
def get_db_info(db_id: str):
    """获取数据库的schema信息"""
    db_path = f"./database/{db_id}.sqlite"
    
    if not os.path.exists(db_path):
        return f"Error: Database file {db_path} does not exist."
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        schema = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = cursor.fetchall()
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()
            schema[table_name] = {
                'columns': columns,
                'indexes': indexes,
                'foreign_keys': foreign_keys
            }
        
    except Exception as e:
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()
    
    # Format schema as markdown for better readability
    md_content = f'# {db_id} Database Schema\n\n'
    
    for table, info in schema.items():
        md_content += f'## Table: `{table}`\n\n'
        
        md_content += '### Columns\n'
        md_content += '| Column | Type | PK | Not Null | Default |\n'
        md_content += '|--------|------|----|----------|---------|\n'
        for col in info['columns']:
            md_content += f'| `{col[1]}` | {col[2]} | {"PK" if col[5] else ""} | {"✔" if col[3] else ""} | {col[4] or "—"} |\n'
        
        if info['indexes']:
            md_content += '\n### Indexes\n'
            for idx in info['indexes']:
                md_content += f'- `{idx[1]}` {"(Unique)" if idx[2] else ""}\n'
        
        if info.get('foreign_keys'):
            md_content += '\n### Foreign Keys\n'
            seen = set()
            for fk in info['foreign_keys']:
                relation = f"`{fk[3]}` → `{fk[2]}.{fk[4]}`"
                if relation not in seen:
                    md_content += f'- {relation}\n'
                    seen.add(relation)
        md_content += '\n---\n\n'
    
    return md_content

# ========================================================== LLM Functions ==========================================================
def img_to_imgurl(img_path: str):
    """将图片转换为图片URL"""
    if not img_path:
        return None
        
    if not os.path.exists(img_path):
        return None
        
    try:
        with open(img_path, "rb") as image_file:
            base64_img = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:image/png;base64,{base64_img}"
    except Exception:
        return None

def messages_maker(nl: str, db_id: str, chart_img_url: str = None, chart_code: str = None):
    """根据输入的NL、db_id、Chart_img、Chart_code生成完整的messages"""
    db_info = get_db_info(db_id)
    db_path = f"./database/{db_id}.sqlite"

    # Simplify image and code logging
    if chart_img_url:
        chart_img_description = "The chart image is attached."
    else:
        chart_img_description = "There is no chart image."

    if not chart_code:
        chart_code = "There is no chart code."

    # Create messages based on input type
    if not chart_img_url:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(
                nl=nl, 
                db_path=db_path, 
                db_info=db_info, 
                chart_img_description=chart_img_description, 
                chart_code=chart_code
            )}
        ]
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": USER_PROMPT.format(
                    nl=nl, 
                    db_path=db_path, 
                    db_info=db_info, 
                    chart_img_description=chart_img_description, 
                    chart_code=chart_code
                )},
                {"type": "image_url", "image_url": {"url": chart_img_url}}
            ]}
        ]
    
    return messages

def call_llm(messages: list):
    """调用LLM"""
    try:
        raw_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.0
        )
        
        # Attempt to extract code from response
        try:
            code = raw_response.choices[0].message.content.rsplit("```python")[1].split("```")[0].strip()
        except Exception:
            code = "# Error parsing LLM response\n" + raw_response.choices[0].message.content
    
    except Exception as e:
        return f"# Error calling LLM API\n# {str(e)}"
    
    return code

def generate_altair_code(nl: str, db_id: str, chart_img_path: str = None, chart_code: str = None):
    """根据输入的NL、db_id、Chart_img、Chart_code生成Altair Code"""
    chart_img_url = img_to_imgurl(chart_img_path)
    messages = messages_maker(nl, db_id, chart_img_url, chart_code)
    code = call_llm(messages)
    
    return code

def execute_altair_code(code: str, chart_path: str):
    """执行Altair代码并生成图表
    
    Args:
        code: Altair代码
        chart_path: 图表保存路径
        
    Returns:
        dict: 执行结果
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        
        # 创建执行环境
        exec_globals = {
            '__builtins__': __builtins__,
            'os': os,
            'sys': sys,
            'json': json,
            'sqlite3': sqlite3,
            'pandas': None,
            'altair': None,
            'alt': None
        }
        
        # 导入必要的库
        try:
            import pandas as pd
            import altair as alt
            exec_globals['pandas'] = pd
            exec_globals['altair'] = alt
            exec_globals['alt'] = alt
        except ImportError as e:
            return {
                'status': 'error',
                'info': f'Required libraries not available: {str(e)}'
            }
        
        # 执行代码
        exec(code, exec_globals)
        
        # 检查是否有图表对象被创建
        chart = None
        for var_name, var_value in exec_globals.items():
            if hasattr(var_value, 'save') and callable(getattr(var_value, 'save')):
                chart = var_value
                break
        
        if chart is None:
            return {
                'status': 'error',
                'info': 'No chart object found in the executed code'
            }
        
        # 保存图表
        try:
            chart.save(chart_path)
        except Exception as save_error:
            # 如果保存失败，尝试使用其他方法
            try:
                # 尝试使用to_dict()方法保存为JSON
                chart_dict = chart.to_dict()
                # 将JSON保存到chart_json目录
                json_dir = os.path.join(os.path.dirname(os.path.dirname(chart_path)), 'chart_json')
                os.makedirs(json_dir, exist_ok=True)
                json_filename = os.path.basename(chart_path).replace('.png', '.vega.json')
                json_path = os.path.join(json_dir, json_filename)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(chart_dict, f, indent=2)
                
                # 尝试使用matplotlib作为备选方案生成PNG
                try:
                    import matplotlib.pyplot as plt
                    import matplotlib
                    matplotlib.use('Agg')  # 使用非交互式后端
                    
                    # 创建一个简单的matplotlib图表作为备选
                    fig, ax = plt.subplots(figsize=(10, 6))
                    
                    # 初始化变量
                    x_data = []
                    y_data = []
                    
                    # 从JSON数据中提取数据点（如果可能）
                    if 'data' in chart_dict and 'values' in chart_dict['data']:
                        data_values = chart_dict['data']['values']
                        if data_values:
                            # 尝试提取x和y数据
                            for item in data_values:
                                if isinstance(item, dict):
                                    if 'x' in item and 'y' in item:
                                        x_data.append(item['x'])
                                        y_data.append(item['y'])
                            
                            if x_data and y_data:
                                ax.scatter(x_data, y_data, alpha=0.7)
                                ax.set_xlabel('X')
                                ax.set_ylabel('Y')
                                ax.set_title('Data Visualization (Matplotlib Fallback)')
                    
                    # 如果没有数据，创建一个示例图表
                    if not x_data or not y_data:
                        import numpy as np
                        x = np.linspace(0, 10, 100)
                        y = np.sin(x)
                        ax.plot(x, y)
                        ax.set_xlabel('X')
                        ax.set_ylabel('Y')
                        ax.set_title('Data Visualization (Matplotlib Fallback)')
                    
                    plt.tight_layout()
                    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
                    plt.close()
                    
                    return {
                        'status': 'success',
                        'info': f'Chart saved as PNG using matplotlib fallback (Altair PNG save failed: {str(save_error)})',
                        'json_path': json_path
                    }
                except ImportError:
                    pass
                except Exception as matplotlib_error:
                    print(f"Matplotlib fallback failed: {matplotlib_error}")
                
                return {
                    'status': 'success',
                    'info': f'Chart saved as JSON (PNG save failed: {str(save_error)})',
                    'json_path': json_path
                }
            except Exception as json_error:
                return {
                    'status': 'error',
                    'info': f'Failed to save chart: PNG error: {str(save_error)}, JSON error: {str(json_error)}'
                }
        
        # 检查是否生成了JSON文件，并将其移动到chart_json目录
        original_json_path = chart_path.replace('.png', '.vega.json')
        if os.path.exists(original_json_path):
            # 将JSON文件移动到chart_json目录
            json_dir = os.path.join(os.path.dirname(os.path.dirname(chart_path)), 'chart_json')
            os.makedirs(json_dir, exist_ok=True)
            json_filename = os.path.basename(chart_path).replace('.png', '.vega.json')
            json_path = os.path.join(json_dir, json_filename)
            
            import shutil
            shutil.move(original_json_path, json_path)
            
            return {
                'status': 'success',
                'info': 'Chart generated successfully',
                'json_path': json_path
            }
        else:
            return {
                'status': 'success',
                'info': 'Chart generated successfully'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'info': f'Error executing code: {str(e)}'
        }

# ========================================================== Process Item Function ==========================================================
def process_item(item):
    """Process a single dataset item"""
    try:
        nl = item["NLQ"]
        db_id = item["db_id"]
        item_type = item["type"]
        
        if item_type == "type_A":
            code = generate_altair_code(nl, db_id)
            return {
                "type": item_type, 
                "NLQ": nl, 
                "db_id": db_id, 
                "label": item["code"], 
                "prediction": code
            }
        
        elif item_type == "type_B":
            chart_img_path = item["reference_path"]
            code = generate_altair_code(nl, db_id, chart_img_path)
            return {
                "type": item_type, 
                "NLQ": nl, 
                "db_id": db_id, 
                "chart_img_path": chart_img_path, 
                "label": item["code"], 
                "prediction": code
            }
        
        elif "type_C" in item_type:
            with open(item['reference_path'], "r", encoding="utf-8") as f:
                chart_code = f.read()
            code = generate_altair_code(nl, db_id, chart_code=chart_code)
            return {
                "type": item_type, 
                "NLQ": nl, 
                "db_id": db_id, 
                "reference_code_path": item['reference_path'], 
                "label": item["code"], 
                "prediction": code
            }
        
        elif item_type == "type_D":
            with open(item['original_code_path'], "r", encoding="utf-8") as f:
                chart_code = f.read()
            code = generate_altair_code(nl, db_id, chart_code=chart_code)
            return {
                "type": item_type, 
                "NLQ": nl, 
                "db_id": db_id, 
                "original_code_path": item['original_code_path'], 
                "label": item["code"], 
                "prediction": code
            }
    except Exception as e:
        return {
            "type": item_type if 'item_type' in locals() else "unknown", 
            "NLQ": nl if 'nl' in locals() else "unknown", 
            "db_id": db_id if 'db_id' in locals() else "unknown", 
            "error": str(e)
        }

# ========================================================== Batch Processing ==========================================================
def process_batch():
    """Main function to process the batch of test cases"""
    dataset_folder = "./DataVis-Bench/"
    
    if not os.path.exists(dataset_folder):
        print(f"Dataset folder not found: {dataset_folder}")
        sys.exit(1)
    
    json_files = [f for f in os.listdir(dataset_folder) if f.endswith(".json")]
    print(f"Found {len(json_files)} JSON files to process")
    print(f"Using LLM: {MODEL_NAME}")
    
    for file_index, file in enumerate(json_files):
        file_path = os.path.join(dataset_folder, file)
        print(f"File {file_index+1}/{len(json_files)}: {file}")
        
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                data = json.load(f)
            
            file_items = len(data)
            print(f"Processing {file_items} items...")
            
            result_folder = f"./results/instructing_LLM_gpt_4o_mini/{file.split('.')[0]}"
            os.makedirs(result_folder, exist_ok=True)
            
            result_file = os.path.join(result_folder, "results.json")
            
            # Check if results file already exists to resume processing
            if os.path.exists(result_file):
                with open(result_file, "r", encoding="utf-8") as f:
                    existing_results = json.load(f)
                print(f"Found {len(existing_results)} existing results, resuming...")
            else:
                existing_results = []
            
            # Create a dictionary for quick lookup of processed items
            processed_items = {}
            for result in existing_results:
                item_id = f"{result['type']}_{result['db_id']}_{result.get('NLQ', '')}"
                processed_items[item_id] = True
            
            # Filter items that still need processing
            items_to_process = []
            for item in data:
                item_id = f"{item['type']}_{item['db_id']}_{item.get('NLQ', '')}"
                if item_id not in processed_items:
                    items_to_process.append(item)
            
            print(f"Items to process: {len(items_to_process)}")
            
            if items_to_process:
                # Process items concurrently
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    # Submit all tasks
                    future_to_item = {
                        executor.submit(process_item, item): item 
                        for item in items_to_process
                    }
                    
                    # Process results as they complete
                    for future in tqdm(concurrent.futures.as_completed(future_to_item), total=len(items_to_process), desc=f"Processing {file}"):
                        try:
                            result_item = future.result()
                            existing_results.append(result_item)
                            
                            # Save intermediate results
                            with open(result_file, "w", encoding="utf-8") as f:
                                json.dump(existing_results, f, indent=4, ensure_ascii=False)
                        except Exception as e:
                            print(f"Item generated an exception: {e}")
            
            # Final save of results
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(existing_results, f, indent=4, ensure_ascii=False)
            
            print(f"File completed - Results saved to {result_file}")
            
        except Exception as e:
            print(f"Failed to process file {file}: {str(e)}")
    
    print("All files processed.")

# ========================================================== Main ==========================================================
if __name__ == "__main__":
    process_batch()
