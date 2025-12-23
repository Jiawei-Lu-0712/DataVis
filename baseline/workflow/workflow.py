from typing import Callable, Dict, Optional, Any

from sql_generator import generate_sql
from code_generator import generate_visualization_code
from code_evaluator import evaluate_and_debug_code

class VisWorkflow:
    """
    A simple workflow for generating data visualizations using LLM.
    The workflow follows three main steps:
    1. SQL generation
    2. Visualization code generation
    3. Evaluation and debugging
    """
    
    def __init__(self, llm_client: Callable[[str], str]):
        """
        Initialize the workflow with an LLM client.
        
        Args:
            llm_client: A function that takes a prompt and returns an LLM response
        """
        self.llm_client = llm_client
        self.results = {
            "sql": None,
            "code": None,
            "final_code": None,
            "success": False,
            "explanation": None
        }
    
    def process(self, 
                db_path: str,
                user_query: str,
                reference_code: Optional[str] = None,
                reference_image: Optional[str] = None,
                existing_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Process the user query through the workflow.
        
        Args:
            db_path: Path to the SQLite database
            user_query: The user's natural language query
            reference_code: Optional reference code
            reference_image: Optional path to reference image
            existing_code: Optional existing code (for task type D)
            
        Returns:
            A dictionary containing the results of the workflow
        """
        # Step 1: Generate SQL query
        sql_query = generate_sql(
            db_path=db_path,
            user_query=user_query,
            reference_code=reference_code,
            reference_image=reference_image,
            existing_code=existing_code,
            llm_client=self.llm_client
        )
        self.results["sql"] = sql_query
        
        # Step 2: Generate visualization code
        vis_code = generate_visualization_code(
            db_path=db_path,
            sql_query=sql_query,
            user_query=user_query,
            reference_code=reference_code,
            reference_image=reference_image,
            existing_code=existing_code,
            llm_client=self.llm_client
        )
        self.results["code"] = vis_code
        
        # Step 3: Evaluate and debug the code - only once
        success, fixed_code, explanation = evaluate_and_debug_code(
            code=vis_code,
            user_query=user_query,
            reference_code=reference_code,
            reference_image=reference_image,
            existing_code=existing_code,
            llm_client=self.llm_client
        )
        
        self.results["final_code"] = fixed_code
        self.results["success"] = success
        self.results["explanation"] = explanation
        
        return self.results