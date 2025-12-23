import sqlite3
import re

def schema_to_markdown(schema_info):
    """Convert database schema information to markdown format."""
    markdown = "# Database Schema\n\n"
    
    for table_name, table_info in schema_info.items():
        markdown += f"## Table: `{table_name}`\n\n"
        
        # Add columns section
        markdown += "### Columns\n\n"
        markdown += "| Name | Type | Nullable | Primary Key |\n"
        markdown += "|------|------|----------|-------------|\n"
        
        for col in table_info["columns"]:
            markdown += f"| {col['name']} | {col['type']} | {'Yes' if col['nullable'] else 'No'} | {'Yes' if col['primary_key'] else 'No'} |\n"
        markdown += "\n"
        
        # Add foreign keys section if any exist
        if table_info["foreign_keys"]:
            markdown += "### Foreign Keys\n\n"
            markdown += "| ID | Sequence | Referenced Table | From Column | To Column |\n"
            markdown += "|----|----------|------------------|-------------|-----------|\n"
            
            for fk in table_info["foreign_keys"]:
                markdown += f"| {fk['id']} | {fk['seq']} | {fk['table']} | {fk['from']} | {fk['to']} |\n"
            markdown += "\n"
        
        # Add sample data section
        if table_info["sample_data"]:
            markdown += "### Sample Data\n\n"
            if table_info["sample_data"]:
                # Get column names for headers
                headers = [col["name"] for col in table_info["columns"]]
                markdown += "| " + " | ".join(headers) + " |\n"
                markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                
                for row in table_info["sample_data"]:
                    markdown += "| " + " | ".join(str(cell) for cell in row) + " |\n"
            markdown += "\n"
        
        markdown += "---\n\n"
    
    return markdown

def get_database_schema(db_path):
    """Extract database schema information from the given database."""
    schema_info = {}
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        
        for table in tables:
            # Get schema for each table
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            
            # Format column information
            column_info = []
            for col in columns:
                column_info.append({
                    "name": col[1],
                    "type": col[2],
                    "nullable": not col[3],
                    "primary_key": bool(col[5])
                })
            
            # Get sample data (first 3 rows)
            cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
            sample_data = cursor.fetchall()
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            foreign_keys = cursor.fetchall()
            fk_info = []
            
            for fk in foreign_keys:
                fk_info.append({
                    "id": fk[0],
                    "seq": fk[1],
                    "table": fk[2],
                    "from": fk[3],
                    "to": fk[4]
                })
            
            # Store all table information
            schema_info[table] = {
                "columns": column_info,
                "sample_data": sample_data,
                "foreign_keys": fk_info
            }
        
        conn.close()
        return schema_to_markdown(schema_info)
    
    except Exception as e:
        print(f"Error extracting database schema: {e}")
        return f"# Error\n\nError extracting database schema: {str(e)}"

def generate_sql_prompt(db_schema, user_query, reference_code=None, reference_image=None, existing_code=None):
    """Generate a prompt for the LLM to create SQL."""
    prompt = f"""You are a SQL expert. Based on the database schema and the user's request, generate an appropriate SQL query.

DATABASE SCHEMA:
{db_schema}

USER QUERY:
{user_query}
"""

    # Add reference code if provided
    if reference_code:
        prompt += f"""
REFERENCE CODE:
{reference_code}
"""

    # Add reference to image if provided 
    if reference_image:
        prompt += f"""
REFERENCE IMAGE:
The user has provided a reference image. Please consider the visualization style shown in the image.
"""

    # Add existing code if provided
    if existing_code:
        prompt += f"""
EXISTING CODE:
{existing_code}
"""

    prompt += """
Generate ONLY the SQL query needed to extract the data for this visualization.
Your response should be ONLY the SQL query, nothing else.

Please use the following format for your response:
```sql
<SQL QUERY>
```
"""
    
    return prompt

def generate_sql(db_path, user_query, reference_code=None, reference_image=None, existing_code=None, llm_client=None):
    """
    Generate SQL using LLM based on database schema and user query.
    
    Args:
        db_path: Path to the SQLite database
        user_query: The user's natural language query
        reference_code: Optional reference code
        reference_image: Optional path to reference image
        existing_code: Optional existing code
        llm_client: A function that takes a prompt and returns an LLM response
        
    Returns:
        The generated SQL query
    """
    if not llm_client:
        raise ValueError("LLM client function is required")
    
    # Extract database schema
    db_schema = get_database_schema(db_path)
    
    # Generate prompt for LLM
    prompt = generate_sql_prompt(
        db_schema, 
        user_query, 
        reference_code, 
        reference_image, 
        existing_code
    )
    
    # Get response from LLM
    sql_query = llm_client(prompt, reference_image)

    # 从sql_query中提取```sql和```之间的内容
    sql_query = re.search(r"```sql(.*)```", sql_query, re.DOTALL).group(1)
    
    return sql_query