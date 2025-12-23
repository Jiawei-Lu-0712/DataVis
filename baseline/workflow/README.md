# LLM-based Visualization Workflow

This is an implementation of a three-step LLM workflow for generating data visualizations using GPT-4. The workflow follows a systematic process to transform natural language queries into interactive visualizations.

## Workflow Implementation Process

### 1. SQL Generation Phase

1. **Database Schema Extraction**
   - Connects to the SQLite database
   - Extracts table structures, including:
     - Column information (name, type, nullability, primary key status)
     - Foreign key relationships
     - Sample data (first 3 rows)
   - Converts schema information into Markdown format for LLM processing

2. **SQL Query Generation**
   - Constructs a comprehensive prompt containing:
     - Database schema in Markdown format
     - User's natural language query
     - Optional reference code (for Type C tasks)
     - Optional reference image (for Type B tasks)
     - Optional existing code (for Type D tasks)
   - Uses LLM to generate appropriate SQL query
   - Extracts SQL query from LLM response using regex pattern matching

### 2. Visualization Code Generation Phase

1. **Code Generation Process**
   - Builds a detailed prompt including:
     - Database path
     - Generated SQL query
     - Original user query
     - Optional reference materials
   - LLM generates Altair visualization code with requirements:
     - Uses pandas for data processing
     - Implements Altair for visualization
     - Sets appropriate titles, labels, and colors
     - Includes interactive elements
     - Optimizes visualization appearance
     - Contains necessary imports
   - Extracts Python code from LLM response

2. **Code Structure Requirements**
   - Must be simple and straightforward
   - No error handling or defensive programming
   - Assumes valid data and inputs
   - Well-commented and ready to run
   - Follows specific format for imports and data processing

### 3. Code Evaluation and Debugging Phase

1. **Code Execution**
   - Executes code in an isolated process
   - Implements timeout mechanism (default 60 seconds)
   - Captures stdout and stderr
   - Handles process termination if needed
   - Restores original renderer settings

2. **Chart Extraction**
   - Identifies Altair chart objects in the code
   - Prioritizes complex charts with titles
   - Handles multiple chart scenarios
   - Extracts the most relevant visualization

3. **Error Handling and Debugging**
   - Captures and logs execution errors
   - Generates detailed error reports
   - Provides stack traces
   - Creates repair prompts for LLM
   - Returns fixed code and explanations

### 4. Result Processing

The workflow returns a comprehensive result dictionary containing:
- Original SQL query
- Initial visualization code
- Final fixed code
- Success status
- Error explanations or modification notes

### 5. Batch Processing Support

- Implements parallel processing using multiple CPU cores
- Automatically saves intermediate results
- Includes error recovery mechanisms
- Tracks progress of multiple tasks
- Saves results in structured format

## Directory Structure

- `database/`: SQLite database files
- `DataVis-Bench/`: Input task files in JSON format
- `results/`: Output directory for processed results
- `outputs/`: Directory for saving individual visualization outputs

## Requirements

- Python 3.7+
- SQLite3
- Pandas
- Altair
- OpenAI API access
- httpx
- tqdm
- multiprocessing

## Features

- Supports four types of visualization tasks:
  - Text-to-Visualization (Type A)
  - Visualization Modification (Type D)
  - Text-to-Visualization with Image Reference (Type B)
  - Text-to-Visualization with Code Reference (Type C)
- Parallel processing of multiple tasks
- Automatic saving of results with progress tracking
- Support for both code and image references
- Error handling and recovery

## How to Use

### Batch Processing

The main entry point is `run.py`, which processes a batch of visualization tasks:

```bash
python run.py
```

The script will:
1. Read tasks from the `DataVis-Bench/` directory
2. Process them in parallel using multiple CPU cores
3. Save results to `results/workflow_gpt_4o_mini/` directory
4. Track progress and save intermediate results

### Python API

```python
from workflow import VisWorkflow

# Initialize the workflow with your LLM client
workflow = VisWorkflow(llm_client=openai_llm_client)

# Process a single visualization task
results = workflow.process(
    db_path="path/to/database.sqlite",
    user_query="Your visualization request",
    reference_code=None,  # Optional: path to reference code file
    reference_image=None,  # Optional: path to reference image
    existing_code=None    # Optional: existing code for modification
)
```

## Task Types

The workflow supports four types of visualization tasks:

1. **Type A (Text-to-Visualization)**: Basic text input to visualization
   ```python
   workflow.process(db_path, user_query)
   ```

2. **Type B (Image Reference)**: Text input with reference image
   ```python
   workflow.process(db_path, user_query, reference_image="path/to/image.png")
   ```

3. **Type C (Code Reference)**: Text input with reference code
   ```python
   workflow.process(db_path, user_query, reference_code=code_string)
   ```

4. **Type D (Visualization Modification)**: Modify existing visualization
   ```python
   workflow.process(db_path, user_query, existing_code=existing_code_string)
   ``` 