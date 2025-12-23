import json
import re
import traceback
import tempfile
import os
import altair as alt
import io
from contextlib import redirect_stdout, redirect_stderr
import ast
import pandas as pd
from multiprocessing import Process, Queue
import time

def _exec_altair_direct(code_string):
    """
    Execute Altair code directly without multiprocessing.
    """
    result = {
        'success': False,
        'chart': None,
        'output': '',
        'error': None
    }
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    namespace = {
        'alt': alt,
        'pd': pd
    }
    
    try:
        last_expr_value = None
        lines = code_string.split('\n')
        lines = [line for line in lines if ".to_json()" not in line and "print(" not in line and "exit(" not in line]
        modified_code = '\n'.join(lines).replace("exit()", "")
        modified_code = modified_code.replace(".show()", "")
        modified_code = modified_code.replace(".display(", "# .display(")
        original_renderer = alt.renderers.active
        alt.renderers.enable('default')
        
        try:
            parsed_code = ast.parse(modified_code)
            if parsed_code.body and isinstance(parsed_code.body[-1], ast.Expr):
                last_expr = ast.unparse(parsed_code.body[-1])
                code_without_last = ast.unparse(ast.Module(body=parsed_code.body[:-1], type_ignores=[]))
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code_without_last, namespace)
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    last_expr_value = eval(last_expr, namespace)
            else:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(modified_code, namespace)
        except SyntaxError:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(modified_code, namespace)
        
        chart = None
        if isinstance(last_expr_value, alt.TopLevelMixin):
            chart = last_expr_value
        else:
            if 'chart' in namespace and isinstance(namespace['chart'], alt.TopLevelMixin):
                chart = namespace['chart']
            else:
                # Otherwise look for charts in variables, prioritizing more complex charts
                chart_candidates = []
                for var_name, var_value in namespace.items():
                    if isinstance(var_value, alt.TopLevelMixin):
                        chart_candidates.append((var_name, var_value))
                
                if chart_candidates:
                    if len(chart_candidates) > 1:
                        final_charts = [c for _, c in chart_candidates if hasattr(c, 'title') and c.title is not None]
                        if final_charts:
                            chart = final_charts[0]
                        else:
                            chart = chart_candidates[-1][1]
                    else:
                        chart = chart_candidates[0][1]
        
        result['success'] = True
        result['chart'] = chart
        result['output'] = stdout_capture.getvalue()
        
    except Exception as e:
        result['success'] = False
        result['error'] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        result['output'] = stdout_capture.getvalue() + stderr_capture.getvalue()
    finally:
        alt.renderers.enable(original_renderer)
    
    return result

def exec_altair_code_in_process(code_string, queue):
    """
    Execute Altair code in a separate process to ensure counter consistency.
    
    Parameters:
    -----------
    code_string : str
        A string containing Python code with Altair visualization code
    queue : multiprocessing.Queue
        Queue to return execution results
        
    Returns:
    --------
    None, but puts the result in the queue
    """
    result = {
        'success': False,
        'chart': None,
        'output': '',
        'error': None
    }
    
    # Capture stdout and stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    # Create a namespace with commonly needed libraries
    namespace = {
        'alt': alt,
        'pd': pd
    }
    
    try:
        # Signal the start of execution
        queue.put({"status": "running"})
        
        last_expr_value = None
        modified_code = code_string
        modified_code = modified_code.replace(".show()", "")
        modified_code = modified_code.replace(".display(", "# .display(")
        original_renderer = alt.renderers.active
        alt.renderers.enable('default')
        
        try:
            parsed_code = ast.parse(modified_code)
            if parsed_code.body and isinstance(parsed_code.body[-1], ast.Expr):
                last_expr = ast.unparse(parsed_code.body[-1])
                code_without_last = ast.unparse(ast.Module(body=parsed_code.body[:-1], type_ignores=[]))
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code_without_last, namespace)
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    last_expr_value = eval(last_expr, namespace)
            else:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(modified_code, namespace)
        except SyntaxError:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(modified_code, namespace)
        
        chart = None
        if isinstance(last_expr_value, alt.TopLevelMixin):
            chart = last_expr_value
        else:
            if 'chart' in namespace and isinstance(namespace['chart'], alt.TopLevelMixin):
                chart = namespace['chart']
            else:
                # Otherwise look for charts in variables, prioritizing more complex charts
                chart_candidates = []
                for var_name, var_value in namespace.items():
                    if isinstance(var_value, alt.TopLevelMixin):
                        chart_candidates.append((var_name, var_value))
                
                if chart_candidates:
                    if len(chart_candidates) > 1:
                        final_charts = [c for _, c in chart_candidates if hasattr(c, 'title') and c.title is not None]
                        if final_charts:
                            chart = final_charts[0]
                        else:
                            chart = chart_candidates[-1][1]
                    else:
                        chart = chart_candidates[0][1]
        
        result['success'] = True
        result['chart'] = chart
        result['output'] = stdout_capture.getvalue()
        
    except Exception as e:
        result['success'] = False
        result['error'] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        result['output'] = stdout_capture.getvalue() + stderr_capture.getvalue()
    finally:
        alt.renderers.enable(original_renderer)
    
    queue.put(result)

def exec_altair_code(code_string, timeout=60):
    """
    Execute a Python code string that uses the Altair library and return the result.
    Attempts to use multiprocessing, but falls back to direct execution if multiprocessing fails.
    
    Parameters:
    -----------
    code_string : str
        A string containing Python code with Altair visualization code
    timeout : int
        Timeout in seconds (default 60)
        
    Returns:
    --------
    dict
        A dictionary containing:
        - 'success': boolean indicating if execution was successful
        - 'chart': The Altair chart object if successful, None otherwise
        - 'output': Any stdout output captured during execution
        - 'error': Error message if execution failed, None otherwise
    """
    # Check if code is accessing database
    is_db_operation = 'sqlite3' in code_string or 'connect(' in code_string
    
    # If direct execution would be simpler (no threading issues)
    if is_db_operation and 'jupyter' not in code_string:
        return _exec_altair_direct(code_string)
    
    try:
        # Try to use multiprocessing for isolation
        queue = Queue()
        
        # Execute the code in a separate process
        process = Process(target=exec_altair_code_in_process, args=(code_string, queue))
        process.start()
        
        # Wait for process to start running
        start_time = time.time()
        process_started = False
        
        # Wait up to 10 seconds for process to start
        while time.time() - start_time < 10:
            if not queue.empty():
                status = queue.get()
                if status.get("status") == "running":
                    process_started = True
                    break
            time.sleep(0.1)
        
        if not process_started:
            process.terminate()
            process.join()
            return _exec_altair_direct(code_string)
        
        # Set a timeout in case the process hangs
        process.join(timeout=timeout)
        
        # Check if the process is still alive (timed out)
        if process.is_alive():
            process.terminate()
            process.join()
            
            # If the process timed out, try direct execution as fallback
            return _exec_altair_direct(code_string)
        else:
            # Get the result from the queue if process completed
            try:
                if not queue.empty():
                    result = queue.get(block=False)
                    return result
                else:
                    return _exec_altair_direct(code_string)
            except Exception as e:
                return _exec_altair_direct(code_string)
        
    except Exception as e:
        return _exec_altair_direct(code_string)


def generate_eval_prompt(code, execution_result, user_query, reference_code=None, reference_image=None, existing_code=None):
    """Generate a prompt for the LLM to evaluate and debug the visualization code."""
    
    prompt = f"""You are a data visualization expert who specializes in Altair for Python. Evaluate the provided visualization code against the user's requirements and debug if necessary.

USER QUERY:
{user_query}

VISUALIZATION CODE:
```python
{code}
```

EXECUTION RESULT:
{execution_result}
"""

    if reference_code:
        prompt += f"""
REFERENCE CODE:
```python
{reference_code}
```
"""

    if reference_image:
        prompt += f"""
REFERENCE IMAGE:
The user provided a reference image that the visualization should stylistically match.
"""

    if existing_code:
        prompt += f"""
EXISTING CODE (that was being modified):
```python
{existing_code}
```
"""

    prompt += """
Please evaluate the code based on the following criteria:
1. Does it correctly address the user's requirements?
2. Is the visualization appropriate for the data and task?
3. Does it use Altair best practices?
4. If there are execution errors, what's causing them?
5. Does it match the style of any provided reference?

Then provide your assessment:
1. If the code is successful and meets requirements, respond with: "EVALUATION: SUCCESS"
2. If the code has execution errors or does not meet requirements, provide:
   - "EVALUATION: FAILURE"
   - A brief explanation of what's wrong
   - A complete corrected version of the code

Your response should follow this format:

EVALUATION: [SUCCESS or FAILURE]
[If FAILURE, include explanation here]

[If FAILURE, include complete corrected code here]
"""

    return prompt

def evaluate_and_debug_code(code, user_query, reference_code=None, reference_image=None, existing_code=None, llm_client=None):
    """
    Evaluate and debug the visualization code using LLM.
    
    Args:
        code: The Altair visualization code to evaluate
        user_query: The original user query
        reference_code: Optional reference code
        reference_image: Optional path to reference image
        existing_code: Optional existing code that was modified
        llm_client: A function that takes a prompt and returns an LLM response
        
    Returns:
        A tuple with (success_flag, final_code, explanation)
    """
    
    if not llm_client:
        error_msg = "LLM client function is required"
        raise ValueError(error_msg)
    
    # Execute the code to see if it works
    execution_result = exec_altair_code(code)['error']
    if execution_result == None:
        execution_result = "EXECUTION: SUCCESS"
    
    # Generate prompt for LLM evaluation
    prompt = generate_eval_prompt(
        code,
        execution_result,
        user_query,
        reference_code,
        reference_image,
        existing_code
    )
    
    # Get response from LLM
    eval_response = llm_client(prompt, reference_image)
    
    # Parse the evaluation response
    success = "EVALUATION: SUCCESS" in eval_response
    
    if success:
        return (True, code, "The visualization meets all requirements")
    else:
        # Extract explanation and fixed code
        explanation = ""
        fixed_code = code  # Default to original code
        
        # Look for explanation between EVALUATION: FAILURE and the code block
        if "EVALUATION: FAILURE" in eval_response:
            pattern = r"EVALUATION: FAILURE\s+(.*?)```python"
            match = re.search(pattern, eval_response, re.DOTALL)
            if match:
                explanation = match.group(1).strip()
        
        # Extract corrected code
        code_pattern = r"```python\s+(.*?)\s+```"
        code_match = re.search(code_pattern, eval_response, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()
        
        return (False, fixed_code, explanation)