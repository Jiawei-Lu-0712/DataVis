# Instructing LLM for Data Visualization

This implementation demonstrates a detailed instruction-based approach for generating data visualizations using LLM. The system uses carefully crafted prompts to guide the LLM in generating accurate Altair visualization code.

## Implementation Process

### 1. LLM Setup and Configuration

1. **API Configuration**
   - Sets up OpenAI API client with custom base URL
   - Configures API key and model selection
   - Implements HTTP client with SSL verification disabled
   - Sets maximum number of concurrent workers

2. **System Prompt Design**
   - Defines expert role for the LLM
   - Specifies requirements for code generation
   - Outlines handling of different task types
   - Sets expectations for code structure and quality

### 2. Database Schema Processing

1. **Schema Extraction**
   - Connects to SQLite database
   - Extracts comprehensive schema information:
     - Table structures
     - Column definitions
     - Primary and foreign keys
     - Index information
   - Formats schema into detailed Markdown

2. **Schema Formatting**
   - Creates structured Markdown documentation
   - Includes:
     - Table descriptions
     - Column details (name, type, constraints)
     - Index information
     - Foreign key relationships
   - Ensures readability for LLM processing

### 3. Message Construction

1. **User Prompt Design**
   - Structured prompt template with sections:
     - Natural language query
     - Database path
     - Schema information
     - Reference materials (if any)
   - Detailed requirements for:
     - SQL and data preparation
     - Visualization structure
     - Styling and presentation
     - Reference handling

2. **Message Assembly**
   - Handles different input types:
     - Basic text queries
     - Image references
     - Code references
     - Existing code modifications
   - Formats messages according to input type
   - Includes image data when applicable

### 4. LLM Interaction

1. **API Call Implementation**
   - Makes API calls with temperature=0 for consistency
   - Handles API errors gracefully
   - Extracts code from response using regex
   - Provides error messages for parsing failures

2. **Response Processing**
   - Extracts Python code from LLM response
   - Handles malformed responses
   - Provides clear error messages
   - Maintains code formatting

### 5. Task Processing

1. **Single Item Processing**
   - Handles four task types:
     - Type A: Basic text-to-visualization
     - Type B: Image reference visualization
     - Type C: Code reference visualization
     - Type D: Code modification
   - Processes each type with appropriate parameters
   - Returns structured results

2. **Batch Processing**
   - Implements concurrent processing
   - Handles multiple JSON input files
   - Supports resume functionality
   - Saves intermediate results
   - Tracks progress with progress bars

### 6. Result Management

1. **Output Organization**
   - Creates structured output directories
   - Saves results in JSON format
   - Maintains file organization by task type
   - Includes metadata in results

2. **Error Handling**
   - Captures and logs processing errors
   - Maintains partial results
   - Provides detailed error information
   - Continues processing despite individual failures

## Directory Structure

- `database/`: SQLite database files
- `DataVis-Bench/`: Input task files in JSON format
- `results/`: Output directory for processed results
  - `instructing_LLM_gpt_4o_mini/`: Model-specific results
    - `Basic_Generation/`: Type A results
    - `Iterative_Refinement/`: Type D results
    - `Basic_Generation_with_img/`: Type B results
    - `Basic_Generation_with_code/`: Type C results

## Requirements

- Python 3.7+
- SQLite3
- OpenAI API access
- httpx
- tqdm
- concurrent.futures 