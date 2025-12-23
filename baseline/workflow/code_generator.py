import sqlite3
import json
import re

def generate_code_prompt(sql_query, user_query, db_path, reference_code=None, reference_image=None, existing_code=None):
    """Generate a prompt for the LLM to create Altair visualization code."""
    
    prompt = f"""You are a data visualization expert who specializes in Altair for Python. Create an Altair visualization based on the data and requirements below.

DATABASE PATH:
{db_path}

SQL QUERY:
{sql_query}

USER QUERY:
{user_query}
"""

    # Add reference code if provided
    if reference_code:
        prompt += f"""
REFERENCE CODE:
{reference_code}

Please use this reference code as inspiration for your visualization style and approach. Adapt it to work with the current data and requirements.
"""

    # Add reference to image if provided
    if reference_image:
        prompt += f"""
REFERENCE IMAGE:
The user has provided a reference image. Please create a visualization that matches the style and approach shown in the reference image.
"""

    # Add existing code if provided
    if existing_code:
        prompt += f"""
EXISTING CODE:
{existing_code}

Please modify this existing code to meet the new requirements while maintaining its overall structure.
"""

    prompt += """
Generate a complete Python script with Altair that:
1. Uses pandas to convert the data
2. Creates the appropriate visualization with Altair
3. Sets appropriate titles, labels, colors, and interactive elements
4. Optimizes the visualization appearance for readability
5. Includes any necessary imports and the complete code

IMPORTANT REQUIREMENTS:
1. DO NOT use try-except blocks or any other exception handling code
2. DO NOT include any error handling or defensive programming
3. Write the code assuming the data and inputs are valid
4. Keep the code simple and straightforward

Make sure the code is well-commented, handles edge cases, and is ready to run.

Your response should be ONLY the Python code, nothing else. Do not include explanations before or after the code.

Please use the following format for your response:
```python
import altair as alt
import pandas as pd
import sqlite3

conn = sqlite3.connect('<DATABASE PATH>')
query = '''
<SQL QUERY>
'''
df = pd.read_sql_query(query, conn)
conn.close()
<DATA PROCESSING>
chart = alt.Chart(df).mark_<MARK_TYPE>().encode(
    x='<X_AXIS>',
    y='<Y_AXIS>',
    color='<COLOR>',
    ...
)
...

# For Display in Jupyter Notebook
chart
```
"""
    
    return prompt

def generate_visualization_code(db_path, sql_query, user_query, reference_code=None, reference_image=None, existing_code=None, llm_client=None):
    """
    Generate Altair visualization code using LLM based on SQL results and user query.
    
    Args:
        db_path: Path to the SQLite database
        sql_query: SQL query to extract data
        user_query: The user's natural language query
        reference_code: Optional reference code
        reference_image: Optional path to reference image
        existing_code: Optional existing code
        llm_client: A function that takes a prompt and returns an LLM response
        
    Returns:
        The generated visualization code
    """
    if not llm_client:
        raise ValueError("LLM client function is required")
    
    # Generate prompt for LLM
    prompt = generate_code_prompt(
        sql_query,
        user_query,
        db_path,
        reference_code,
        reference_image,
        existing_code
    )
    
    # Get response from LLM
    visualization_code = llm_client(prompt, reference_image)

    # 从visualization_code中提取```python和```之间的内容
    visualization_code = re.search(r"```python(.*)```", visualization_code, re.DOTALL).group(1)
    
    return visualization_code