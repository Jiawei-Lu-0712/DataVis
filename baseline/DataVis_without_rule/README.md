# Visualization Agent (Research Paper)

---

## Motivation

在日常生活中，数据可视化是一个普遍且关键的需求。用户需要基于本地数据库高效创建各种可视化图表，以便更好地理解和分析数据。尽管已有的Text-to-Vis等工作尝试将用户的自然语言查询转换为可视化图表，但这些工作大多采用传统的流水线架构，在处理复杂多变的现实需求时存在明显局限性：
1. 缺乏足够的灵活性应对多样化的用户需求场景
2. 难以有效整合和利用不同类型的输入（文本、图像、代码等）
3. 系统组件间协作不足，难以优化整体效果

**我们的核心创新**在于提出了一种突破性的**中心化多智能体协作架构**，这种方法相比传统工作流解决方案具有显著优势：
1. **智能体驱动的灵活处理流程**：通过专业智能体协作取代固定工作流，能够根据不同任务类型动态调整处理路径
2. **中心化协调与分布式处理相结合**：协调器智能体统一管理任务，专业智能体分别负责需求解析、数据查询、代码生成和结果验证
3. **多模态输入的无缝集成**：能够处理文本查询、参考图像、代码示例等多种输入形式，满足用户在不同场景的需求
4. **高度适应性和可扩展性**：系统能够持续学习和改进，适应新的数据类型和可视化需求

在实际应用中，用户经常会遇到这样的场景：
- 需要基于数据库和自然语言查询直接生成可视化结果
- 在网络上发现了一个具有理想可视化效果的图表，希望参考其视觉特征生成自己的可视化结果
- 有参考可视化代码（可能基于不同库实现），希望参考其特点生成自己的可视化结果
- 需要对已有的基于数据库生成的可视化代码进行修改和调整

传统的可视化工具和方法难以同时满足这些多样化需求，而我们的**Agent方法**通过智能协作突破了这一限制。我们的系统采用基于Altair库的Python代码作为中间表示，这一设计选择结合智能体架构带来了显著优势：
1. **端到端的智能处理**：从需求理解到代码生成的全流程智能化处理
2. **专业化分工与协同**：各智能体专注于特定任务，协同工作提升整体效能
3. **灵活应对多样化需求**：系统能根据任务类型自动调整处理流程，满足不同场景需求
4. **持续优化与自我提升**：智能体可以从交互中学习，不断提升可视化质量

相比现有解决方案，我们的多智能体协作系统不仅提高了可视化生成的效率和质量，还实现了对复杂场景的灵活适应，真正满足了现实应用中的多样化需求。

---

## 任务定义

### A. 基础输入类型（仅自然语言查询+数据库）
> 基于用户查询和数据库生成数据可视化代码

**输入输出**：
- **输入**：用户查询、数据库
- **输出**：数据可视化代码

**示例**：
- **用户查询**：`Can you create an interactive scatter plot showing the relationship between students' ages and how many activities they participate in? I'd like to see each student represented as a circle, with different colors for each major so I can spot any patterns across different fields of study.`
- **数据库**：`database/activity_1.sqlite`
- **数据可视化代码**：...

### B. 图像参考类型（自然语言查询+数据库+图像）
> 根据参考图像的可视化特征，基于用户查询和数据库生成数据可视化代码

**输入输出**：
- **输入**：用户查询、参考图像、数据库
- **输出**：数据可视化代码

**示例**：
- **用户查询**：`I like this scatter plot showing movie ratings over time, but could you create a similar visualization for my student activity data instead? I'd like to see how the average age of students in each activity compares to the overall average, with activities on the x-axis and the age difference on the y-axis. Please use a red-blue color scheme where blue shows activities with older students and red shows activities with younger students compared to the average. Also, add a title that explains what we're looking at.`
- **参考图像**：![Reference Image](../DataVis-Bench/img/Advanced%20Calculations___calculate_residuals.png)
- **数据库**：`database/activity_1.sqlite`
- **数据可视化代码**：...

### C. 代码参考类型（自然语言查询+数据库+代码）
> 根据参考代码的可视化特征，基于用户查询和数据库生成数据可视化代码

**输入输出**：
- **输入**：用户查询、参考代码、数据库
- **输出**：数据可视化代码

**示例**：
- **用户查询**：`Can you create a chart showing the age difference between students in each activity compared to the overall average? I'd like to see the activities listed on the x-axis and the age difference in years on the y-axis. Please use colors to highlight whether an activity has older students (blue) or younger students (red) compared to the average. Also, add a title that explains what the visualization is showing.`
- **数据库**：`database/activity_1.sqlite`
- **参考代码**：...
- **数据可视化代码**：...

### D. 可视化迭代类型（自然语言查询+数据库+已有可视化代码）
> 基于修改需求和数据库修改已有的可视化代码

**输入输出**：
- **输入**：用户修改需求、已有的可视化代码、数据库
- **输出**：修改后的数据可视化代码

**示例**：
- **用户修改需求**：`The chart is great for showing the age differences, but it's a little hard to read with all the activity names crammed together at the bottom. Could you rotate the x-axis labels to make them easier to read? Also, I think it would be clearer if we added thin grid lines for the y-axis. That would help me quickly see the exact age difference for each activity without having to guess. Finally, could you make the points a bit larger and hollow, but still fill them with the same colors we're using now? That might make the visualization stand out better.`
- **数据库**：`database/activity_1.sqlite`
- **已有可视化代码**：...
- **修改后的数据可视化代码**：...

---

## 系统设计

Visualization System采用中心化的Agentic AI架构，由一个中央协调智能体（Coordinator Agent）统一管理整个任务流程，其他专业智能体作为工具提供者，通过标准化接口被调用。这种设计确保了清晰的信息流动路径和统一的任务管理。

### 系统输入输出

#### 系统输入
系统接收以下输入内容：

- **用户需求**
  - 自然语言查询（所有类型都需要）
  - 修改需求（对于D类型任务）
- **数据库**（所有类型都需要）
- **代码**（对于C类型和D类型任务）
  - 参考可视化代码（C类型）
  - 已有可视化代码（D类型）
- **参考图像**（对于B类型任务）

#### 系统输出
系统生成以下可视化结果：

- **数据可视化结果**
  - 可视化代码（Python/Altair）
  - 可视化图表
  - 可视化决策解释

### 中心化Agentic AI架构

Visualization System采用中心化的Agentic AI架构，由协调器智能体（Coordinator Agent）作为中央控制单元，负责任务分发、流程控制和状态管理。其他专业智能体作为工具提供者，通过标准化接口被调用。

#### 核心智能体结构

##### 1. 协调器智能体（Coordinator Agent）
- **目标**：管理整个工作流程，调度各专业智能体，维护全局状态
- **描述**：协调器智能体是整个系统的核心控制单元，负责解析任务类型，协调各专业智能体的工作，并确保信息的正确流动。
- **核心责任**：
  - 确定任务类型（A/B/C/D）
  - 根据任务类型设计执行路径
  - 调用各专业智能体并传递必要信息
  - 管理任务状态和中间结果
  - 实施错误恢复和重试策略
  - 收集最终结果并整合输出
- **接口**：无（作为调用者）
- **工具**：
  - `generate_sql_from_query`: 根据用户需求生成SQL查询语句
  - `generate_visualization_code`: 生成可视化代码
  - `modify_visualization_code`: 根据评估结果修改可视化代码
  - `evaluate_visualization`: 验证可视化是否符合需求

##### 2. 数据库与查询智能体（Database & Query Agent）
- **目标**：分析数据库结构并构建执行SQL查询
- **描述**：数据库与查询智能体负责分析数据库结构、理解表结构、构建并执行SQL查询。
- **接口**：
  - `generate_sql_from_query(self, db_path: str, user_query: str, reference_path: str = None, existing_code_path: str = None) -> Tuple[bool, str]`: 
    - 根据用户需求生成SQL查询语句
  - `generate_sql_from_requirement(self, db_path: str, requirement: str, reference_path: str = None, existing_code_path: str = None) -> Tuple[bool, str]`:
    - 根据特定需求生成SQL查询语句
  - `execute_query(self, db_path: str, sql_query: str) -> Tuple[bool, Dict]`:
    - 执行SQL查询并返回结果
  - `modify_sql_query(self, db_path: str, existing_query: str, user_query: str, sql_recommendations: List[Dict] = None) -> Tuple[bool, str]`:
    - 根据验证评估智能体提供的SQL建议修改SQL查询语句
- **工具**：
  - `_list_tables_tool`: 列出数据库中的所有表
  - `_get_table_schema_tool`: 获取指定表的结构信息
  - `_get_table_sample_tool`: 获取指定表的示例数据
  - `_get_foreign_keys_tool`: 获取指定表的外键关系
  - `_find_fields_in_tables_tool`: 根据字段名查找相关表
  - `_execute_sql_tool`: 执行SQL查询并获取结果

##### 3. 可视化实现智能体（Visualization Implementation Agent）
- **目标**：基于SQL查询结果和需求生成或修改可视化代码
- **描述**：可视化实现智能体负责基于SQL查询结果和需求生成Altair可视化代码或修改已有代码。该智能体主要依赖LLM的代码生成能力和Altair可视化库的知识。
- **接口**：
  - `generate_visualization_code(self, db_path: str, user_query: str, sql_query: str, reference_path: str = None, existing_code_path: str = None) -> Tuple[bool, str]`: 
    - 生成全新可视化代码
  - `modify_visualization_code(self, existing_code: str, recommendations: List[Dict] = None) -> Tuple[bool, str]`: 
    - 根据需求修改已有代码
- **工具**：
  - `_exec_altair_code`: 执行代码并捕获输出或错误
  - `_execute_altair_code`: 执行Altair代码并保存图像
  - `_execute_matplotlib_code`: 执行Matplotlib代码并保存图像

##### 4. 验证评估智能体（Validation & Evaluation Agent）
- **目标**：验证生成的可视化是否符合用户需求
- **描述**：验证评估智能体负责验证生成的代码和可视化是否符合用户需求。
- **接口**：
  - `evaluate_visualization(self, user_query: str, code: str, reference_path: str = None, existing_code_path: str = None) -> Tuple[bool, Dict]`: 
    - 验证可视化是否符合需求
- **工具**：
  - `_execute_altair_code`: 执行Altair代码并生成可视化
  - `_execute_matplotlib_code`: 执行Matplotlib代码并生成可视化

### 工作流程

系统根据任务类型（A/B/C/D）动态设计执行路径，主要工作流程如下：

#### 类型A（基础输入）流程
1. 分析用户查询和数据库结构
2. 生成SQL查询提取所需数据
3. 基于SQL结果生成可视化代码
4. 执行验证评估
5. 根据评估结果进行迭代优化

#### 类型B（图像参考）流程
1. 分析用户查询、数据库结构和参考图像
2. 生成SQL查询提取所需数据
3. 基于SQL结果和参考图像风格生成可视化代码
4. 执行验证评估，重点关注与参考图像的一致性
5. 根据评估结果进行迭代优化

#### 类型C（代码参考）流程
1. 分析用户查询、数据库结构和参考代码
2. 生成SQL查询提取所需数据
3. 基于SQL结果和参考代码模式生成可视化代码
4. 执行验证评估，重点关注与参考代码的一致性
5. 根据评估结果进行迭代优化

#### 类型D（可视化迭代）流程
1. 直接评估现有可视化代码
2. 根据评估结果修改代码
3. 重新评估修改后的代码
4. 继续迭代直至满足需求

系统在执行过程中会自动判断任务类型，并根据不同任务类型采用相应的工作流程，确保生成的可视化结果满足用户需求。