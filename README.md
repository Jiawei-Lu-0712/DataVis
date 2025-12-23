## DataVis:A Data Visualization Framework with Multi-Agent and Logic Rules

DataVis-Agent is a multi-agent framework with explicit logic rules for **reliable, comprehensive cross-modal data visualization**, supporting inputs such as natural language, code, and images. This repository also provides **DataVis-Bench**, a benchmark for text-to-vis and visualization modification tasks, and an automatic **metric suite** for visualization quality.

## Repository Overview

- **`DataVis-Agent/`**: Core multi-agent system (coordinator, tool manager, config, database/query and validation agents).
- **`DataVis-Bench/`**: Benchmark datasets and reference implementations for text-to-vis and vis-modify tasks.
- **`metric/`**: Visualization evaluation metrics used in the paper.
- **`run_system.py`**: Example entry script to run the multi-agent visualization system on a sample.
- **`run_metric.py`**: Script to compute metrics over saved results.

## Installation

- **Set up environment**

```bash
git clone https://github.com/Jiawei-Lu-0712/DataVis.git
cd DataVis-main
pip install -r requirements.txt
```

- **Configure LLM APIs**

Edit `DataVis-Bench/utils/Config.py` and replace the placeholder `"xxx"` values in `MODEL_CONFIGS` with your own API keys and endpoints.（Gemini performs well, therefore the `run_metric.py` script calls Gemini's API by default.）

## Quick Start

- **Run a sample visualization generation case**

```bash
python run_system.py
```

The script creates log and temporary folders and runs a sample item through the `CoordinatorAgent`, logging intermediate steps and final visualization code.

- **Evaluate generated results**

Organize your results under `./results/{method_type}/{model_type}/{data_type}/results.json` following the structure in `run_metric.py`, then run:

```bash
python run_metric.py
```

This produces `metric.json`, `wrong_results.json`, and `correct_results.json` for each data type.

## Benchmark Data

DataVis-Bench provides benchmark files:

- **`Basic_Generation.json`**, **`Iterative_Refinement.json`**, **`Basic_Generation_with_img.json`**, **`Basic_Generation_with_code.json`** under `DataVis-Bench/`.
- **`database/`** and **`img/`** subdirectories with databases and images used in benchmark tasks.
- For the databases in `DataVis-Bench/database/`, download the Spider dataset from [Google Drive](https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view) and extract **all database files** into the `DataVis-Bench/database/` directory.


