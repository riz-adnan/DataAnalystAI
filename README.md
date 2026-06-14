# DataAnalyst AI

An AI-powered multi-CSV analytics platform that allows users to upload datasets, ask natural language questions, automatically discover relationships between files, generate insights, and visualize results through charts.

---

# Live Demo

Frontend: `<ADD_FRONTEND_URL_HERE>`

Backend API: `<ADD_BACKEND_URL_HERE>`

---

# Local Setup

docker compose up --build

Frontend: `http://localhost:3000`

Backend API: `<http://localhost:8000>`

API Docs `<http://localhost:8000/docs>`

---

# Overview

DataAnalyst AI is designed to function as an AI Data Analyst capable of understanding multiple related CSV files and answering business questions conversationally.

Unlike traditional CSV chat applications that treat each file independently, DataAnalyst AI performs:

- Multi-file relationship discovery
- Cross-dataset analysis
- Intelligent query planning
- Tool-driven execution
- Automatic chart generation
- Multi-turn conversational analytics

The system combines deterministic data processing using Pandas with LLM-powered reasoning and planning.

---

# Key Features

## Multi-CSV Analysis

Upload multiple datasets such as:

```text
orders.csv
customers.csv
products.csv
order_items.csv
payments.csv
```

The system automatically identifies relationships and enables cross-file analysis.

---

## Natural Language Analytics

Examples:

```text
What is the total revenue?

Show top 10 products by revenue.

Compare revenue by category.

Which customers generate the most revenue?

Show monthly sales trend.
```

---

## Automatic Relationship Discovery

The platform automatically discovers joins such as:

```text
orders.customer_id
    ↕
customers.customer_id

orders.order_id
    ↕
order_items.order_id

order_items.product_id
    ↕
products.product_id
```

Relationships are inferred once and stored for future queries.

---

## Intelligent Query Planning

The system determines:

- Required datasets
- Required joins
- Required calculations
- Whether charts are needed
- Whether a simple execution flow is sufficient
- Whether a complex plan-and-execute workflow is required

---

## Automatic Chart Generation

Supported chart types:

- Bar Charts
- Line Charts
- Pie Charts
- Scatter Plots

Charts are generated automatically whenever visualizations improve comprehension.

---

# System Architecture

## High-Level Architecture

```text
Frontend (Next.js)
        │
        ▼
FastAPI Backend
        │
        ▼
Agent Orchestrator
        │
        ├── Relationship Agent
        ├── Planner Agent
        ├── Step Executor Agent
        └── Final Response Agent
        │
        ▼
Tool Layer
        │
        ├── Join Tool
        ├── Filter Tool
        ├── Aggregate Tool
        ├── Derived Column Tool
        ├── Chart Tool
        └── Summary Tool
        │
        ▼
Pandas Execution Engine
        │
        ▼
MongoDB + Supabase Storage
```

---

# Technology Stack

## Frontend

- Next.js
- React
- Tailwind CSS

## Backend

- FastAPI
- Python

## Data Processing

- Pandas
- NumPy

## AI Layer

- Google Gemini

## Database

- MongoDB Atlas

Stores:

- Project metadata
- Schema previews
- Relationship graph
- Traces
- Chat history

## File Storage

- Supabase Storage

Stores:

- Original CSVs
- Cleaned CSVs

---

# Data Processing Pipeline

## 1. CSV Upload

Users can upload one or multiple CSV files into a project.

Example:

```text
orders.csv
products.csv
customers.csv
order_items.csv
```

---

## 2. Preprocessing Pipeline

Each uploaded CSV is automatically cleaned and analyzed before becoming available to the AI system.

### Missing Values

Numeric columns:

```text
Filled using median values
```

Categorical columns:

```text
Filled using "Unknown"
```

### Datatype Detection

The system automatically detects:

- Numeric columns
- Date columns
- Text columns
- Categorical columns

### Date Conversion

Date-like columns are converted using:

```python
pd.to_datetime()
```

### Outlier Detection

Outliers are identified using:

```text
Interquartile Range (IQR)
```

and capped appropriately.

### Duplicate Removal

Duplicate records are automatically removed.

### Schema Preview Generation

For every CSV the following metadata is stored:

```json
{
  "csv_name": "orders.csv",
  "columns": ["order_id", "customer_id", "order_date"],
  "sample_rows": [
    {...},
    {...}
  ]
}
```

Only the first two rows are retained for LLM context.

---

# Agent Architecture

The system follows a multi-agent architecture.

## Relationship Agent

### Purpose

Runs only once per project.

### Trigger

Executed when:

```text
known_relationships is empty
```

### Inputs

- User Question
- CSV Schemas
- First Two Rows of Every CSV

### Responsibilities

- Discover join relationships
- Infer foreign keys
- Build relationship graph
- Save graph to MongoDB

### Example Output

```json
{
  "relationships": [
    {
      "left_csv": "orders.csv",
      "left_column": "customer_id",
      "right_csv": "customers.csv",
      "right_column": "customer_id"
    }
  ]
}
```

---

## Planner Agent

Runs for every user query.

Responsibilities:

- Understand user intent
- Determine complexity
- Select tools
- Build execution plan
- Decide chart requirements

### Simple Query Example

Question:

```text
Show top 10 products by revenue
```

Generated Plan:

```json
{
  "complexity": "simple",
  "steps": [
    {
      "tool": "join_csv"
    },
    {
      "tool": "create_derived_column"
    },
    {
      "tool": "aggregate"
    },
    {
      "tool": "generate_chart"
    }
  ]
}
```

### Complex Query Example

Question:

```text
Compare repeat customers versus new customers by region and explain anomalies.
```

Generated Plan:

```json
{
  "complexity": "complex",
  "steps": [
    {
      "tool": "join_csv"
    },
    {
      "tool": "aggregate"
    },
    {
      "llm_call": "Analyze anomalies"
    }
  ]
}
```

---

# Plan and Execute Workflow

Complex queries cannot always be solved through a fixed tool chain.

For such cases, the system uses a Plan-and-Execute architecture.

```text
Planner Agent
      │
      ▼
Execution Step
      │
      ▼
Tool Result
      │
      ▼
Step Executor Agent
      │
      ▼
Needs More Work?
      │
     Yes
      │
      ▼
Additional Tool Call
      │
      ▼
Continue Execution
```

The execution loop stops when:

- The objective is achieved
- Final answer is available
- Maximum iterations are reached

This architecture allows the system to solve multi-stage analytical problems while remaining interpretable and traceable.

---