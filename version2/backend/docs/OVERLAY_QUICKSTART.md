"""
Overlay Renderer - Quick Start Guide
=====================================
Getting started with the Overlay Renderer in 5 minutes.
"""

# Example 1: Minimal Usage via API

## Request
```
POST /api/v1/charts/overlay
Content-Type: application/json

{
  "title": "Revenue vs Cost",
  "data": {
    "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
    "Revenue": [1000, 1200, 1100],
    "Cost": [400, 450, 480]
  },
  "x_column": "Date",
  "y_columns": ["Revenue", "Cost"]
}
```

## Response
```json
{
  "success": true,
  "chart": {
    "data": [
      {
        "x": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "y": [1000, 1200, 1100],
        "name": "Revenue",
        "mode": "lines+markers",
        ...
      },
      {
        "x": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "y": [400, 450, 480],
        "name": "Cost",
        "mode": "lines+markers",
        ...
      }
    ],
    "layout": {...},
    "metadata": {...}
  }
}
```

---

# Example 2: Using Python Client

```python
import requests
import json

# Initialize
url = "http://localhost:8000/api/v1/charts/overlay"

# Prepare data
payload = {
    "title": "Q4 Financial Performance",
    "data": {
        "Month": ["Oct", "Nov", "Dec"],
        "Revenue": [50000, 65000, 72000],
        "Cost": [20000, 25000, 28000],
        "Profit": [30000, 40000, 44000]
    },
    "x_column": "Month",
    "y_columns": ["Revenue", "Cost", "Profit"],
    "analysis_intent": "comparison",
    "unit_handling": {
        "Revenue": "USD",
        "Cost": "USD",
        "Profit": "USD"
    }
}

# Make request
response = requests.post(url, json=payload)
chart = response.json()["chart"]

# Display (e.g., in Jupyter)
import plotly.io as pio
pio.show(chart)

# Or save as HTML
with open("chart.html", "w") as f:
    f.write(pio.to_html(chart))
```

---

# Example 3: From DataFrame

```python
import pandas as pd
import requests

# Load your data
df = pd.read_csv("sales_data.csv")

# Prepare payload
payload = {
    "title": "Sales Analysis",
    "data": df.to_dict(orient="list"),
    "x_column": "Date",
    "y_columns": ["ProductA_Sales", "ProductB_Sales"],
    "analysis_intent": "comparison"
}

# Generate chart
response = requests.post("http://localhost:8000/api/v1/charts/overlay", json=payload)
chart = response.json()["chart"]

# Use chart
print(f"Chart generated with {len(chart['data'])} series")
```

---

# Example 4: Complete Integration Example

```python
from fastapi import FastAPI
import requests
import json

app = FastAPI()

@app.get("/sales/comparison")
async def get_sales_comparison():
    """Generate comparison chart via Overlay Renderer."""
    
    data = {
        "Week": ["W1", "W2", "W3", "W4", "W5"],
        "East": [100, 120, 115, 140, 130],
        "West": [80, 90, 95, 110, 105],
        "North": [120, 100, 110, 125, 135]
    }
    
    payload = {
        "title": "Regional Sales Comparison",
        "data": data,
        "x_column": "Week",
        "y_columns": ["East", "West", "North"],
        "analysis_intent": "comparison"
    }
    
    # Call Overlay Renderer
    response = requests.post(
        "http://localhost:8000/api/v1/charts/overlay",
        json=payload
    )
    
    return response.json()
```

---

# Example 5: Error Handling

```python
import requests

def generate_overlay_chart(payload: dict):
    """Generate chart with error handling."""
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/charts/overlay",
            json=payload,
            timeout=30
        )
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            if result["success"]:
                print("✓ Chart generated successfully")
                warnings = result.get("warnings", [])
                if warnings:
                    print(f"⚠ Warnings: {warnings}")
                return result["chart"]
            else:
                print(f"✗ Error: {result['error']}")
                return None
        else:
            print(f"✗ HTTP {response.status_code}: {response.text}")
            return None
            
    except requests.Timeout:
        print("✗ Request timeout (>30s)")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None
```

---

# Example 6: Testing Locally

```bash
# Start the server
cd backend
python -m uvicorn main:app --reload

# In another terminal, test the endpoint
curl -X POST http://localhost:8000/api/v1/charts/overlay \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Chart",
    "data": {
      "X": [1, 2, 3],
      "Y1": [10, 20, 15],
      "Y2": [5, 8, 10]
    },
    "x_column": "X",
    "y_columns": ["Y1", "Y2"]
  }' | python -m json.tool

# Check health
curl http://localhost:8000/api/v1/charts/overlay/health | python -m json.tool
```

---

# Example 7: Frontend Integration (React)

```javascript
import React, { useState } from 'react';
import Plot from 'react-plotly.js';

function ChartComponent() {
  const [chart, setChart] = useState(null);

  const generateChart = async () => {
    const payload = {
      title: "Revenue vs Cost",
      data: {
        Date: ["2025-01-01", "2025-01-02", "2025-01-03"],
        Revenue: [1000, 1200, 1100],
        Cost: [400, 450, 480]
      },
      x_column: "Date",
      y_columns: ["Revenue", "Cost"]
    };

    try {
      const response = await fetch('/api/v1/charts/overlay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await response.json();
      
      if (result.success) {
        setChart(result.chart);
      }
    } catch (error) {
      console.error('Error generating chart:', error);
    }
  };

  return (
    <div>
      <button onClick={generateChart}>Generate Chart</button>
      {chart && (
        <Plot
          data={chart.data}
          layout={chart.layout}
          config={{ responsive: true }}
        />
      )}
    </div>
  );
}

export default ChartComponent;
```

---

# Key Decision Points

## When to Use Overlay
✅ DO USE if:
- Comparing metrics with same units
- Comparing metrics with compatible scales
- Need direct value comparison
- 2-7 metrics
- Linear or non-linear trends

## When NOT to Use Overlay
❌ DON'T USE if:
- Metrics have vastly different scales (→ use Dual-Axis)
- Many series (>7) (→ use Small Multiples/Facet)
- Need composition analysis (→ use Stacked)
- Need ranking view (→ use Bar chart)

---

# Common Payloads

### Template 1: Time Series
```json
{
  "title": "Your Title",
  "data": {
    "Date": ["2025-01-01", "2025-01-02"],
    "Metric1": [value1, value2],
    "Metric2": [value1, value2]
  },
  "x_column": "Date",
  "y_columns": ["Metric1", "Metric2"],
  "analysis_intent": "trend"
}
```

### Template 2: Categorical Comparison
```json
{
  "title": "Your Title",
  "data": {
    "Category": ["A", "B", "C"],
    "SeriesOne": [10, 20, 15],
    "SeriesTwo": [15, 18, 22]
  },
  "x_column": "Category",
  "y_columns": ["SeriesOne", "SeriesTwo"],
  "analysis_intent": "comparison"
}
```

### Template 3: With Units
```json
{
  "title": "Your Title",
  "data": {...},
  "x_column": "Date",
  "y_columns": ["Revenue", "Expense", "Profit"],
  "unit_handling": {
    "Revenue": "USD",
    "Expense": "USD",
    "Profit": "USD"
  }
}
```

---

# Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| Only 1 series | Add at least 2 to y_columns |
| Column not found | Check spelling: case-sensitive |
| "High series" warning | Consider Facet visualization |
| Slow render | Reduce to <5000 data points |
| Connection refused | Start server first |

---

# Next Steps

1. **Test locally:** Use Example 6 to verify setup
2. **Integrate:** Use Example 3-4 in your application
3. **Customize:** Adjust `analysis_intent`, `unit_handling`
4. **Monitor:** Check /api/v1/charts/overlay/health
5. **Deploy:** Follow deployment guide in docs

---

**Need Help?** See full documentation: [OVERLAY_RENDERER.md](OVERLAY_RENDERER.md)
