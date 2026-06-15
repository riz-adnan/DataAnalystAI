# DataAnalyst AI

An AI-powered multi-CSV analytics platform that allows users to upload datasets, ask natural language questions, automatically discover relationships between files, generate insights, and visualize results through charts.

---

# Live Demo

Frontend: `https://dataanalystai.netlify.app/`

Backend API: `https://dataanalystai.onrender.com/`

---

# Video pitch

Video - `https://youtu.be/El8V6z37ggQ`

---

# Local Setup

Setup .env from .env.example

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

# Tool Layer

The AI model never directly manipulates datasets.

Instead, it interacts with a deterministic tool layer responsible for performing all data operations.

This approach provides:

- Reproducibility
- Explainability
- Security
- Lower hallucination risk
- Easier debugging

---

## Available Tools

### Join CSV Tool

Responsible for joining multiple CSV datasets using the relationship graph discovered by the Relationship Agent.

Example:

```text
orders.customer_id
    ↕
customers.customer_id
```

Supported join types:

- inner
- left
- right
- outer

---

### Filter Tool

Filters data based on conditions.

Examples:

```text
Revenue > 10000

Order Date between Jan and June

Category = Electronics
```

Supported operators:

- equals
- not_equals
- greater_than
- less_than
- contains
- between
- date_between

---

### Aggregate Tool

Performs statistical and business aggregations.

Supported operations:

- sum
- mean
- median
- count
- min
- max
- unique count

Example:

```text
Revenue by Category

Average Order Value

Total Sales by Region
```

---

### Derived Column Tool

Creates calculated fields.

Examples:

```text
Revenue = Quantity × Price

Profit = Revenue - Cost

Discount Percentage
```

This tool only supports safe predefined operations and never executes arbitrary code.

---

### Chart Generation Tool

Creates frontend-ready chart JSON.

Supported chart types:

- Bar Chart
- Line Chart
- Pie Chart
- Scatter Plot

The tool returns:

```json
{
  "chart_type": "bar",
  "title": "Revenue by Category",
  "x_key": "category",
  "y_keys": ["revenue"],
  "data": [...]
}
```

No chart images are generated on the backend.

Charts are rendered by the frontend.

---

### Summary Tool

Generates:

- Dataset preview
- Row count
- Column list
- Statistical summary

Useful for exploratory analysis.

---

# Query Processing Lifecycle

Every user question follows the same lifecycle.

```text
User Question
        │
        ▼
Relationship Agent (if needed)
        │
        ▼
Planner Agent
        │
        ▼
Simple Plan OR Complex Plan
        │
        ▼
Tool Execution
        │
        ▼
Final Response Agent
        │
        ▼
Frontend Response
```

---

# Simple Query Flow

Simple queries are questions that can be solved using a straightforward sequence of tool calls.

Example:

```text
Show top 10 products by revenue.
```

Execution:

```text
Planner Agent
        │
        ▼
Join Tool
        │
        ▼
Derived Column Tool
        │
        ▼
Aggregate Tool
        │
        ▼
Chart Tool
        │
        ▼
Final Response Agent
```

The planner returns a fixed execution plan and tools execute sequentially.

No additional reasoning loops are required.

---

# Complex Query Flow

Complex queries require intermediate reasoning and may involve multiple analytical stages.

Example:

```text
Compare revenue generated by repeat customers versus first-time customers across different regions and identify unusual patterns.
```

Execution:

```text
Planner Agent
        │
        ▼
Plan Creation
        │
        ▼
Tool Execution
        │
        ▼
LLM Analysis
        │
        ▼
Additional Tool Request
        │
        ▼
Tool Execution
        │
        ▼
Further Analysis
        │
        ▼
Final Response
```

This workflow is implemented using a Plan-and-Execute architecture.

---

# Plan and Execute Architecture

The planner does not attempt to solve the entire problem directly.

Instead, it generates a structured plan.

Example:

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
      "llm_call": "Identify anomalies"
    }
  ]
}
```

The execution engine then performs each step sequentially.

For LLM steps:

1. Previous outputs are provided.
2. Current objective is provided.
3. Relevant schemas are provided.
4. The model decides what must happen next.

This architecture improves:

- Reliability
- Observability
- Tool utilization
- Cost efficiency

---

# Trace System

Every LLM call and tool execution generates a trace.

Example:

```json
{
  "agent": "planner_agent",
  "step_type": "llm_call",
  "status": "success"
}
```

## Why Traces Matter

### Explainability

Every answer can be traced back to:

- Which tools were called
- Which datasets were used
- Which joins occurred
- Which calculations were performed

### Debugging

If a query fails:

```text
Missing Column
Invalid Join
Incorrect Aggregation
```

The exact failing step can be identified.

### Auditing

The complete reasoning chain is preserved.

This enables reproducibility and future evaluation.

---

# Multi-Turn Memory

The platform supports conversational analytics.

Each interaction is stored in MongoDB.

Example:

```text
User:
Show revenue by category.

User:
Break it down by month.

User:
Which category grew fastest?

User:
Why do you think that happened?
```

The Planner Agent receives:

- Current question
- Recent chat history
- Previous responses
- Existing traces

This enables contextual follow-up questions.

---

# Deployment Architecture

## Frontend

Hosted on Netlify

Frontend URL:

https://dataanalystai.netlify.app/

## Backend

Hosted on Render

Backend URL:

https://dataanalystai.onrender.com

API Documentation:

https://dataanalystai.onrender.com/docs

## Database

MongoDB Atlas

Stores:

- Project Metadata
- Chat History
- Traces
- Relationships
- Schema Previews

## File Storage

Supabase Storage

Stores:

- Original CSVs
- Cleaned CSVs

---

# Future Improvements

## Data Layer

- DuckDB Integration
- SQL Query Generation
- Streaming CSV Processing

## AI Layer

- Self-Reflection Agent
- Query Validation Agent
- Retrieval-Augmented Schema Search

## Visualization Layer

- Interactive Dashboards
- Multi-Chart Responses
- Drill-down Analytics

## Infrastructure

- Docker Deployment
- Kubernetes Scaling
- Background Job Processing

---

# Design Philosophy

The core philosophy of DataAnalyst AI is:

> Use LLMs for reasoning and planning, and deterministic tools for computation.

By separating reasoning from execution, the platform achieves:

- Better reliability
- Lower hallucination rates
- Transparent execution
- Easier debugging
- Scalable analytics workflows

This architecture mirrors modern production-grade AI agents where LLMs decide **what** to do and tools decide **how** to do it.

---