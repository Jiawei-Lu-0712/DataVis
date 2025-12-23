"""
CoordinatorAgent - 移除规则约束版本

本文件已移除以下规则约束，让agent能够更自由地决定行为：

1. 移除了system prompt中的严格工作流程规则（CRITICAL WORKFLOW RULES）
2. 移除了工具描述中的约束条件（如"ONLY after evaluate_visualization"）
3. 移除了工具函数中的严格先决条件检查
4. 移除了评估工具中的强制性下一步指导
5. 移除了预定义的工作流程步骤（pre-iteration step）
6. 移除了任务提示词中的详细工作流程指导
7. 简化了评估结果的返回，不再强制指定下一步操作
8. 完全移除了任务类型确定机制（Type A/B/C/D）
9. 移除了基于任务类型的预定义处理逻辑
10. 简化了process_item方法，不再根据类型分别处理
11. 移除了所有工具函数中的参数验证约束，改为异常处理
12. 简化了工具函数中的状态检查，更加宽容地处理部分失败情况

现在agent可以根据情况自由选择使用哪些工具以及使用顺序，不受任何预定义规则约束。
工具调用失败时会通过异常处理机制提供错误信息，而不是预先阻止调用。
即使某些操作部分失败，agent也能继续尝试其他操作。
"""

import os
import re
from typing import Dict, List, Tuple
import json

# 导入基类和其他智能体
from .utils.Agent import Agent
from .database_query_agent import DatabaseQueryAgent
from .code_generation_agent import CodeGenerationAgent
from .validation_evaluation_agent import ValidationEvaluationAgent


class CoordinatorAgent(Agent):
    """协调器智能体（Coordinator Agent）
    
    作为整个系统的核心控制单元，负责解析任务类型，协调各专业智能体的工作，并确保信息的正确流动。
    
    核心责任：
    1. 确定任务类型（A/B/C/D）
    2. 根据任务类型设计执行路径
    3. 调用各专业智能体并传递必要信息
    4. 管理任务状态和中间结果
    5. 实施错误恢复和重试策略
    6. 收集最终结果并整合输出
    """
    
    def __init__(self, model_type: str = "gemini-2.0-flash@gemini-2.0-flash", agent_name: str = "coordinator_agent", agent_id: str = None, use_log: bool = False):
        """初始化协调器智能体
        
        Args:
            model_type: 使用的模型种类，格式为text_model@img_model，默认为qwen-max-2025-01-25@qwen-vl-max-2025-01-25
            agent_name: 智能体名称
            agent_id: 智能体ID
            use_log: 是否使用日志
        """
        system_prompt = """You are a visualization system coordinator that orchestrates specialized agents to create data visualizations. Your task is to analyze requirements, coordinate data preparation, generate visualization code, and ensure quality.

## Available Tools
- generate_sql_from_query: Creates SQL to extract data
- generate_visualization_code: Creates visualization code
- modify_visualization_code: Fixes code issues
- evaluate_visualization: Validates visualization and provides improvement recommendations

Use these tools as needed to complete the visualization task effectively. You may have access to reference materials (images, code) or existing code to work with, but approach each task flexibly based on the specific requirements.
"""

        super().__init__(model_type=model_type, system_prompt=system_prompt, agent_name=agent_name, agent_id=agent_id, use_log=use_log)
        
        # 初始化任务状态和中间结果存储
        self.user_query = None
        self.db_path = None
        self.reference_path = None
        self.existing_code = None
        self.existing_code_path = None
        self.sql_query = None
        self.visualization_code = None
        self.evaluation_result = None
        
        # 评估结果详细信息
        self.evaluation_passed = False
        self.sql_recommendations = []
        self.recommendations = []
        
        # 初始化各专业智能体实例(用于注册工具)
        self._db_agent = DatabaseQueryAgent(model_type=model_type, agent_id=agent_id, use_log=use_log)
        self._code_agent = CodeGenerationAgent(model_type=model_type, agent_id=agent_id, use_log=use_log)
        self._validation_agent = ValidationEvaluationAgent(model_type=model_type, agent_id=agent_id, use_log=use_log)

        # 注册各专业智能体工具
        self._register_agent_tools()

        self.chat_status(False)
        
        self._log("协调器智能体初始化完成")
    
    def _register_agent_tools(self):
        """注册各专业智能体工具"""
        # 1. 数据库与查询智能体工具
        self.register_tool(
            tool_name="generate_sql_from_query",
            tool_func=self._generate_sql_from_query_tool,
            tool_description="Generate SQL query based on user query and database schema",
            tool_parameters={},
            required=[]
        )
        
        # 2. 代码生成智能体工具
        self.register_tool(
            tool_name="generate_visualization_code",
            tool_func=self._generate_visualization_code_tool,
            tool_description="Generate visualization code based on user query, database, and SQL query",
            tool_parameters={},
            required=[]
        )
        
        self.register_tool(
            tool_name="modify_visualization_code",
            tool_func=self._modify_visualization_code_tool,
            tool_description="Modify visualization code based on evaluation recommendations or other requirements",
            tool_parameters={},
            required=[]
        )
        
        # 3. 验证评估智能体工具
        self.register_tool(
            tool_name="evaluate_visualization",
            tool_func=self._evaluate_visualization_tool,
            tool_description="Evaluate if visualization meets requirements and provide improvement suggestions",
            tool_parameters={},
            required=[]
        )
        
        self._log("智能体工具注册完成")
    
    def _generate_sql_from_query_tool(self) -> Dict:
        """生成SQL查询工具
        
        Returns:
            Dict: 操作状态和简要说明
        """
        self._log(f"调用生成SQL查询工具")
        
        try:
            status, result = self._db_agent.generate_sql_from_query(self.db_path, self.user_query)
            
            # 无论成功与否，都尝试保存结果
            if result:
                self.sql_query = result
                self._log("生成SQL查询完成")
                return {"status": True, "message": "SQL query generation completed", "result": result}
            else:
                self._log("生成SQL查询未返回结果")
                return {"status": False, "message": "SQL query generation returned no result"}
                
        except Exception as e:
            self._log(f"生成SQL查询异常: {e}")
            return {"status": False, "message": f"Error generating SQL query: {e}"}

    def _generate_visualization_code_tool(self) -> Dict:
        """生成可视化代码工具
        
        Returns:
            Dict: 操作状态和简要说明
        """
        self._log("调用生成可视化代码工具")
        
        try:
            status, result = self._code_agent.generate_visualization_code(
                self.db_path, 
                self.user_query, 
                self.sql_query, 
                self.reference_path,
                self.existing_code_path
            )
            
            # 无论成功与否，都尝试保存结果
            if result:
                self.visualization_code = result
                self._log("生成可视化代码完成")
                return {"status": True, "message": "Visualization code generation completed", "result": result}
            else:
                self._log("生成可视化代码未返回结果")
                return {"status": False, "message": "Visualization code generation returned no result"}
                
        except Exception as e:
            self._log(f"生成可视化代码异常: {e}")
            return {"status": False, "message": f"Error generating visualization code: {e}"}
    
    def _modify_visualization_code_tool(self) -> Dict:
        """修改可视化代码工具
        
        Returns:
            Dict: 操作状态和简要说明
        """
        self._log("调用修改可视化代码工具")
        
        try:
            # 如果没有具体建议，尝试使用通用改进方法
            if not self.recommendations:
                self._log("无具体修改建议，尝试通用改进")
                recommendations = ["Improve code quality and functionality"]
            else:
                recommendations = self.recommendations
            
            status, result = self._code_agent.modify_visualization_code(
                self.visualization_code,
                recommendations
            )
            
            # 无论成功与否，都尝试保存结果
            if result:
                self.visualization_code = result
                self._log("修改可视化代码完成")
                return {"status": True, "message": "Visualization code modification completed", "result": result}
            else:
                self._log("修改可视化代码未返回结果")
                return {"status": False, "message": "Visualization code modification returned no result"}
                
        except Exception as e:
            self._log(f"修改可视化代码异常: {e}")
            return {"status": False, "message": f"Error modifying visualization code: {e}"}
    
    def _evaluate_visualization_tool(self) -> Dict:
        """验证可视化工具
        
        Returns:
            Dict: 验证结果字典，包含评估是否通过和改进建议。
        """
        self._log("调用验证可视化工具")
        
        try:
            status, result = self._validation_agent.evaluate_visualization(
                self.user_query,
                self.visualization_code,
                reference_path=self.reference_path,
                existing_code_path=self.existing_code_path,
                force_failure=self.force_failure
            )
            
            # 保存评估结果
            self.evaluation_result = result
            self.force_failure = False
            
            # 更新评估详细信息
            self.evaluation_passed = status
            self.recommendations = result.get("recommendations", []) if result else []
            
            # 返回评估结果
            if status:
                return {
                    "evaluation_success": True,
                    "message": "The visualization successfully meets all requirements.",
                    "passed": True,
                    "complete": True
                }
            else:
                recommendations_count = len(self.recommendations)
                return {
                    "evaluation_success": True,
                    "message": f"Evaluation failed with {recommendations_count} issues identified. Consider improvements.",
                    "passed": False,
                    "recommendations": self.recommendations
                }
        except Exception as e:
            self._log(f"验证可视化异常: {e}")
            return {"evaluation_success": False, "message": f"Error evaluating visualization: {e}"}
    
    def process_item(self, item: dict) -> dict:
        """处理数据集中的item
        
        Args:
            item: 数据集中的项目
            
        Returns:
            dict: 处理结果
        """
        user_query = item['NLQ']
        db_path = f"./database/{item['db_id']}.sqlite"
        reference_path = item.get('reference_path', None)
        existing_code_path = item.get('original_code_path', None)

        # 记录任务信息
        self._log(f"处理数据集项：查询={user_query[:50]}...")
        
        # 处理任务
        status, result = self.process_task(
            user_query=user_query, 
            db_path=db_path, 
            reference_path=reference_path,
            existing_code_path=existing_code_path
        )

        # 构建和返回结果项
        result_item = {
            'type': item.get('type', ''),
            'NLQ': user_query,
            'db_id': item['db_id'],
            'chart_category': item.get('chart_category', ''),
            'chart_type': item.get('chart_type', ''),
            'label': item.get('code', ''),
            'prediction': result,
            'status': status
        }

        return result_item
    
    def _reset_state(self):
        """重置智能体状态"""
        self.user_query = None
        self.db_path = None
        self.reference_path = None
        self.existing_code = None
        self.existing_code_path = None
        self.sql_query = None
        self.visualization_code = None
        self.evaluation_result = None
        self.force_failure = False
        
        # 重置评估结果
        self.evaluation_passed = False
        self.sql_recommendations = []
        self.recommendations = []

    def process_task(self, 
                    user_query: str, 
                    db_path: str, 
                    reference_path: str = None,
                    existing_code_path: str = None,
                    max_iterations: int = 10) -> Tuple[bool, str]:
        """处理可视化任务的主流程
        
        Args:
            user_query: 用户查询
            db_path: 数据库路径
            reference_path: 参考图像或代码路径（可选）
            existing_code: 已有的可视化代码（可选）
            existing_code_path: 已有的可视化代码路径（可选）
            max_iterations: 最大迭代次数
            
        Returns:
            Tuple[bool, str]: 状态（成功/失败）和可视化代码
        """
        self._log(f"开始处理可视化任务")
        
        # 重置状态并保存初始参数
        self._reset_state()
        self.user_query = user_query
        self.db_path = db_path
        self.reference_path = reference_path
        self.existing_code_path = existing_code_path

        if existing_code_path:
            try:
                with open(existing_code_path, 'r', encoding='utf-8') as f:
                    self.visualization_code = f.read()
                    self._log(f"成功加载已有代码: {existing_code_path}")

            except Exception as e:
                 self._log(f"加载已有代码失败 {existing_code_path}: {e}. Continuing without pre-loaded code.")
                 self.visualization_code = None # Ensure it's None if loading failed
        
        # 构建初始提示词
        initial_prompt = self._build_task_prompt(max_iterations)
        
        # 启动ReAct处理模式
        self._log(f"开始ReAct处理模式")
        
        # 使用ReAct模式执行任务
        result, used_tool = self.chat_ReAct(
            user_messages=[{"role": "user", "content": initial_prompt}],
            max_iterations=max_iterations,
        )
        
        self._log(f"ReAct模式处理完成，使用工具: {'是' if used_tool else '否'}")
        
        # 返回结果
        if self.visualization_code:
            self._log("任务处理成功")
            return True, self.visualization_code
        else:
            self._log("任务处理失败：未生成可视化代码")
            return False, "Failed to generate visualization code"
    
    def _build_task_prompt(self, max_iterations: int) -> str:
        """构建任务提示词
        
        Args:
            max_iterations: 最大迭代次数
            
        Returns:
            str: 任务提示词
        """
        # 基本信息
        prompt = f"""# Visualization Task

## Task Information
- Query: "{self.user_query}"
- Database: "{self.db_path}"
"""

        # 添加参考信息
        if self.reference_path:
            prompt += f"- Reference: \"{self.reference_path}\"\n"
        
        if self.existing_code and self.existing_code_path:
            prompt += f"""- Existing Code: "{self.existing_code_path}"
```python
{self.existing_code[:500]}... (truncated)
```
"""
        
        # 简化的任务指导
        prompt += f"""
## Task
Create a high-quality data visualization that meets the user's requirements. You have access to various tools to help you accomplish this task. Use them as needed within {max_iterations} iterations.

Available tools:
- generate_sql_from_query: Extract data from database
- generate_visualization_code: Create visualization code
- modify_visualization_code: Improve existing code
- evaluate_visualization: Check if requirements are met

Work efficiently to produce the best possible visualization.
"""
        
        return prompt

    def process(
        self,
        db_name: str,
        nl_query: str,
        ref_code: str = None,
        mod_code: str = None,
        ref_image_path: str = None,
        max_iterations: int = 10
    ) -> dict:
        """
        Web接口专用：统一处理并返回所有可视化相关结果
        """
        from datetime import datetime
        
        # 参考代码和图片都可能是reference_path
        reference_path = ref_image_path or None
        if ref_code:
            # 保存参考代码到临时文件
            reference_path = f"temp_ref_code_{datetime.now().strftime('%Y%m%d%H%M%S')}.py"
            with open(reference_path, "w", encoding="utf-8") as f:
                f.write(ref_code)
        existing_code_path = None
        if mod_code:
            existing_code_path = f"temp_mod_code_{datetime.now().strftime('%Y%m%d%H%M%S')}.py"
            with open(existing_code_path, "w", encoding="utf-8") as f:
                f.write(mod_code)
        if db_name.endswith('.sqlite') or db_name.endswith('.db'):
            db_path = f"./database/{db_name}"
        else:
            db_path = f"./database/{db_name}.sqlite"

        # 调用主流程
        status, vis_code = self.process_task(
            user_query=nl_query,
            db_path=db_path,
            reference_path=reference_path,
            existing_code_path=existing_code_path,
            max_iterations=max_iterations
        )

        # 处理图表（假设可视化代码会生成图片文件，路径保存在self.chart_path）
        chart_img = None
        chart_json = None
        
        self._log(f"检查chart_path: hasattr={hasattr(self, 'chart_path')}, chart_path={getattr(self, 'chart_path', 'None')}")
        if hasattr(self, 'chart_path') and self.chart_path:
            self._log(f"chart_path存在, 路径: {self.chart_path}, 文件存在: {os.path.exists(self.chart_path)}")
            if os.path.exists(self.chart_path):
                chart_img = self.chart_path.replace('\\', '/').lstrip('./')
                # 检查是否有对应的JSON文件
                json_path = self.chart_path.replace('.png', '.vega.json')
                if os.path.exists(json_path):
                    chart_json = json_path.replace('\\', '/').lstrip('./')
                    self._log(f"找到JSON文件: {chart_json}")
                else:
                    self._log(f"未找到JSON文件: {json_path}")
            else:
                self._log(f"图表文件不存在: {self.chart_path}")
        else:
            self._log("chart_path不存在或为空")

        # 构建返回结果
        result = {
            'vis_code': vis_code if status else '',
            'vis_code_iter': getattr(self, 'vis_code_iter', ''),
            'chart_img': chart_img or '',
            'chart_json': chart_json or '',
            'sql': self.sql_query or '',
            'sql_iter': getattr(self, 'sql_iter', ''),
            'eval_result': self._format_evaluation_result() if hasattr(self, 'evaluation_result') and self.evaluation_result else ''
        }

        # 清理临时文件
        try:
            if reference_path and reference_path.startswith('temp_ref_code_'):
                os.remove(reference_path)
                self._log(f"已清理临时参考代码文件: {reference_path}")
        except Exception as e:
            self._log(f"清理临时参考代码文件失败: {e}")
        
        try:
            if existing_code_path and existing_code_path.startswith('temp_mod_code_'):
                os.remove(existing_code_path)
                self._log(f"已清理临时修改代码文件: {existing_code_path}")
        except Exception as e:
            self._log(f"清理临时修改代码文件失败: {e}")

        self._log(f"process方法返回结果: {list(result.keys())}")
        return result

    def _format_evaluation_result(self) -> str:
        """Format evaluation result as readable text
        
        Returns:
            str: Formatted evaluation result
        """
        if not hasattr(self, 'evaluation_result') or not self.evaluation_result:
            return "No evaluation result available"
        
        result = self.evaluation_result
        formatted_text = "=== Visualization Evaluation Results ===\n\n"
        
        # Basic information
        if 'evaluation_summary' in result:
            formatted_text += f"📋 Summary: {result['evaluation_summary']}\n\n"
        elif 'analysis_summary' in result:
            formatted_text += f"📋 Summary: {result['analysis_summary']}\n\n"
        
        # 检查数据格式并显示评估状态
        if 'matches_requirements' in result:
            # 传统格式 - 有完整的评估结果
            matches_req = result.get('matches_requirements', False)
            status_emoji = "✅" if matches_req else "❌"
            formatted_text += f"{status_emoji} Evaluation Status: {'Passed' if matches_req else 'Failed'}\n\n"
        else:
            # Recommendations格式 - 评估失败的情况，使用evaluation_passed属性
            status_emoji = "✅" if getattr(self, 'evaluation_passed', False) else "❌"
            formatted_text += f"{status_emoji} Evaluation Status: {'Passed' if getattr(self, 'evaluation_passed', False) else 'Failed'}\n\n"
        
        # Quality scores
        if 'quality_scores' in result:
            scores = result['quality_scores']
            formatted_text += "📊 Quality Scores:\n"
            if 'visual_clarity' in scores:
                formatted_text += f"  • Visual Clarity: {scores['visual_clarity']}/10\n"
            if 'design_aesthetics' in scores:
                formatted_text += f"  • Design Aesthetics: {scores['design_aesthetics']}/10\n"
            if 'code_quality_impression' in scores:
                formatted_text += f"  • Code Quality: {scores['code_quality_impression']}/10\n"
            formatted_text += "\n"
        
        # Validation checks
        if 'validation_checks' in result:
            checks = result['validation_checks']
            formatted_text += "🔍 Validation Checks:\n"
            for check_name, check_result in checks.items():
                check_emoji = "✅" if check_result is True else "❌" if check_result is False else "⚪"
                check_display = check_name.replace('_', ' ').title()
                formatted_text += f"  {check_emoji} {check_display}: {check_result}\n"
            formatted_text += "\n"
        
        # Explicit requirements analysis
        if 'explicit_requirements_analysis' in result:
            requirements = result['explicit_requirements_analysis']
            if requirements:
                formatted_text += "📝 User Requirements Analysis:\n"
                for req in requirements:
                    req_emoji = "✅" if req.get('is_met', False) else "❌"
                    formatted_text += f"  {req_emoji} \"{req.get('requirement_quote', '')}\"\n"
                    if 'evidence' in req:
                        formatted_text += f"     Evidence: {req['evidence']}\n"
                formatted_text += "\n"
        
        # Improvement recommendations
        if 'recommendations_for_improvement' in result:
            recommendations = result['recommendations_for_improvement']
            if recommendations:
                formatted_text += "💡 Improvement Recommendations:\n"
                for rec in recommendations:
                    priority = rec.get('priority', 'medium')
                    priority_emoji = "🔴" if priority == 'high' else "🟡" if priority == 'medium' else "🟢"
                    formatted_text += f"  {priority_emoji} {rec.get('description', '')}\n"
                formatted_text += "\n"
        
        # Failure reasons (if any)
        matches_req = result.get('matches_requirements', False)
        if not matches_req and 'failure_reasons' in result:
            reasons = result['failure_reasons']
            if reasons:
                formatted_text += "⚠️ Failure Reasons:\n"
                for reason in reasons:
                    formatted_text += f"  • {reason}\n"
        
        # 处理recommendations格式的数据（当评估失败时validation_agent返回的格式）
        if 'recommendations' in result and result['recommendations']:
            formatted_text += "🔧 Code Improvement Recommendations:\n"
            for rec in result['recommendations']:
                priority = rec.get('priority', 'medium')
                priority_emoji = "🔴" if priority == 'critical' else "🟠" if priority == 'high' else "🟡" if priority == 'medium' else "🟢"
                description = rec.get('recommendation_description', rec.get('description', ''))
                component = rec.get('component', '')
                formatted_text += f"  {priority_emoji} [{priority.upper()}] {description}\n"
                if component:
                    formatted_text += f"     Component: {component}\n"
            formatted_text += "\n"
        
        # 显示detailed_analysis信息（如果有）
        if 'detailed_analysis' in result and result['detailed_analysis']:
            formatted_text += "🔍 Detailed Analysis:\n"
            for analysis in result['detailed_analysis']:
                formatted_text += f"  • {analysis}\n"
            formatted_text += "\n"
        
        return formatted_text


if __name__ == "__main__":
    # 测试协调器智能体
    import sys
    import os
    
    # 创建日志目录
    os.makedirs("./logs", exist_ok=True)
    os.makedirs("./test_tmp", exist_ok=True)
    
    # 初始化协调器智能体
    coordinator = CoordinatorAgent(model_type="gemini-2.0-flash@gemini-2.0-flash", agent_id=233, use_log=True)
    
    print("\n===== 测试 CoordinatorAgent =====")
    
    user_query = """Can you create an interactive scatter plot showing the relationship between how many days wrestlers held their titles and how long they lasted in elimination matches? I'd like to see each wrestler represented as a circle, with the x-axis showing days held and the y-axis showing elimination time in seconds. Please color-code the circles based on which team each wrestler belonged to."""
    db_path = "./database/wrestler.sqlite"
    # reference_path = "./DataVis-Bench/code/matplotlib/Advanced Calculations___calculate_residuals.py"
    # existing_code_path = "./DataVis-Bench/vis_modify/Advanced Calculations___calculate_residuals___activity_1.py"

    status, result = coordinator.process_task(user_query, db_path)

    coordinator._log(f"最终可视化代码:\n{result}")
    
    print("\n===== 测试完成 =====") 