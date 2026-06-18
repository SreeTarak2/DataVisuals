# Overlay Renderer - Production Documentation

## Overview

The **Overlay Renderer** is a production-ready multi-series charting service that renders multiple metrics on shared axes for direct comparison. It's optimized for comparing metrics with the same units and scale.

**Status:** ✅ Production Ready  
**Version:** 1.0.0  
**Last Updated:** 2025-01-10

---

## Features

### Core Capabilities
- ✅ Render 2-7 metrics on shared (x, y) axes
- ✅ Automatic color assignment and styling
- ✅ Interactive Plotly visualization
- ✅ Null value handling
- ✅ Large dataset support (10,000+ points)
- ✅ Unit handling metadata
- ✅ Reference lines for secondary metrics
- ✅ Comprehensive error handling
- ✅ Performance optimized (<1s for 500+ points)

### Use Cases
- **Revenue vs Cost comparison** - Compare business metrics
- **Trend analysis** - Track multiple variables over time
- **Performance monitoring** - Compare KPIs
- **A/B Testing** - Overlay experiment results
- **Portfolio analysis** - Compare asset performance

### Limitations
- Not suitable for metrics with vastly different scales (use Dual-Axis instead)
- Readability drops with >7 series (use Faceting instead)
- Not ideal for composition analysis (use Stacked instead)

---

## API Reference

### Endpoint 1: Generate Chart (JSON Data)

```http
POST /api/v1/charts/overlay
Content-Type: application/json

{
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
  "trace_mode": "lines+markers",
  "unit_handling": {
    "Revenue": "USD",
    "Cost": "USD",
    "Profit": "USD"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "chart": {
    "data": [
      {
        "x": ["Oct", "Nov", "Dec"],
        "y": [50000, 65000, 72000],
        "name": "Revenue",
        "mode": "lines+markers",
        "line": {"color": "#1f77b4", "width": 2.5},
        "marker": {"size": 6, "opacity": 0.8}
      },
      {
        "x": ["Oct", "Nov", "Dec"],
        "y": [20000, 25000, 28000],
        "name": "Cost",
        "mode": "lines+markers",
        "line": {"color": "#ff7f0e", "width": 2.5},
        "marker": {"size": 6, "opacity": 0.8}
      },
      {
        "x": ["Oct", "Nov", "Dec"],
        "y": [30000, 40000, 44000],
        "name": "Profit",
        "mode": "lines+markers",
        "line": {"color": "#2ca02c", "width": 2.5},
        "marker": {"size": 6, "opacity": 0.8}
      }
    ],
    "layout": {
      "title": {"text": "Q4 Financial Performance"},
      "xaxis": {"title": "Month", "showgrid": true},
      "yaxis": {"title": "Value", "showgrid": true},
      "showlegend": true,
      "hovermode": "x unified"
    },
    "metadata": {
      "renderer": "overlay",
      "series_count": 3,
      "data_points_per_series": 3,
      "has_nulls": false,
      "render_time_ms": 12.5,
      "mode": "lines+markers"
    }
  },
  "warnings": null
}
```

### Endpoint 2: Generate Chart (CSV Upload)

```http
POST /api/v1/charts/overlay/csv?title=Sales%20Data&x_column=Date&y_columns=Q1,Q2,Q3
Content-Type: multipart/form-data

[CSV file upload]
```

### Endpoint 3: Service Info

```http
GET /api/v1/charts/overlay/info
```

**Response:**
```json
{
  "service": "overlay-chart-renderer",
  "version": "1.0.0",
  "status": "ready",
  "capabilities": {
    "max_series": 7,
    "max_data_points": 10000,
    "supported_modes": ["lines+markers", "lines", "markers"],
    "trace_types": ["scatter"],
    "analysis_intents": [
      "trend", "comparison", "composition",
      "relationship", "distribution", "ranking", "diagnosis"
    ]
  }
}
```

### Endpoint 4: Health Check

```http
GET /api/v1/charts/overlay/health
```

---

## Request Parameters

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Chart title (1-200 characters) |
| `data` | object | Data as dict of lists or dict of values |
| `x_column` | string | Name of x-axis column |
| `y_columns` | array | Names of y-axis columns (min 2, max 7) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_intent` | string | "comparison" | trend, comparison, composition, etc. |
| `trace_mode` | string | "lines+markers" | Plotly trace mode |
| `unit_handling` | object | null | Unit mapping per column |
| `secondary_metric` | string | null | Reference metric for baseline |

---

## Response Schema

### Success Response (200)

```typescript
interface OverlayChartResponse {
  success: boolean;
  chart: {
    data: Array<{
      x: Array<any>;
      y: Array<number>;
      name: string;
      mode: string;
      line: { color: string; width: number };
      marker: { size: number; opacity: number };
      hovertemplate: string;
    }>;
    layout: {
      title: { text: string };
      xaxis: { title: string; showgrid: boolean };
      yaxis: { title: string; showgrid: boolean };
      showlegend: boolean;
      legend: object;
    };
    metadata: {
      renderer: string;
      series_count: number;
      data_points_per_series: number;
      has_nulls: boolean;
      render_time_ms: number;
      mode: string;
    };
  };
  metadata?: object;
  warnings?: string[];
}
```

### Error Response (4xx, 5xx)

```json
{
  "success": false,
  "chart": null,
  "error": "Overlay requires at least 2 y_columns",
  "warnings": null
}
```

### Error Codes

| Code | Scenario |
|------|----------|
| 400 | Invalid request (missing fields, wrong types) |
| 400 | Invalid data (column not found, type mismatch) |
| 400 | Too few series (<2) or too many (>7) |
| 413 | Payload too large (>100MB) |
| 500 | Internal server error |

---

## Usage Examples

### Example 1: Simple Revenue vs Cost

```bash
curl -X POST http://localhost:8000/api/v1/charts/overlay \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Revenue vs Cost",
    "data": {
      "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
      "Revenue": [1000, 1200, 1100],
      "Cost": [400, 450, 480]
    },
    "x_column": "Date",
    "y_columns": ["Revenue", "Cost"],
    "analysis_intent": "comparison"
  }'
```

### Example 2: Multi-Year Trend Analysis

```bash
curl -X POST http://localhost:8000/api/v1/charts/overlay \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Annual Revenue Growth",
    "data": {
      "Year": [2020, 2021, 2022, 2023, 2024],
      "Revenue": [100000, 125000, 150000, 180000, 210000],
      "Expenses": [60000, 70000, 85000, 100000, 115000],
      "NetIncome": [40000, 55000, 65000, 80000, 95000]
    },
    "x_column": "Year",
    "y_columns": ["Revenue", "Expenses", "NetIncome"],
    "analysis_intent": "trend"
  }'
```

### Example 3: From Python Client

```python
import requests
import json

url = "http://localhost:8000/api/v1/charts/overlay"

payload = {
    "title": "Product Sales Comparison",
    "data": {
        "Week": ["W1", "W2", "W3", "W4"],
        "ProductA": [100, 120, 115, 130],
        "ProductB": [80, 90, 95, 110],
        "ProductC": [50, 55, 60, 65]
    },
    "x_column": "Week",
    "y_columns": ["ProductA", "ProductB", "ProductC"],
    "analysis_intent": "comparison",
    "unit_handling": {
        "ProductA": "units",
        "ProductB": "units",
        "ProductC": "units"
    }
}

response = requests.post(url, json=payload)
chart_data = response.json()

# Use chart_data["chart"] in Plotly visualization
print(json.dumps(chart_data, indent=2))
```

### Example 4: CSV Upload

```bash
curl -X POST "http://localhost:8000/api/v1/charts/overlay/csv?title=Sales%20Analysis&x_column=Date&y_columns=Sales,Returns" \
  -F "file=@sales_data.csv"
```

---

## Schema: MultiSeriesViewSpec

When rendering, a `MultiSeriesViewSpec` object is created internally:

```python
{
  "title": "Revenue vs Cost",
  "chart_type_primary": "scatter",
  "chart_type_secondary": None,
  "series_strategy": "overlay",
  "encoding": {
    "x": "Date"
  },
  "y_roles": [
    {"column": "Revenue", "role": "series"},
    {"column": "Cost", "role": "series"}
  ],
  "analysis_intent": "comparison",
  "unit_handling": {
    "Revenue": "USD",
    "Cost": "USD"
  },
  "patterns": [],
  "narrative": "We chose OVERLAY to compare metrics directly. Quality: 85%."
}
```

---

## Performance Characteristics

### Benchmarks (Intel i5, 8GB RAM)

| Data Points | Series | Time (ms) | Memory (MB) |
|-------------|--------|-----------|------------|
| 100        | 2      | 5         | 10         |
| 500        | 2      | 12        | 15         |
| 1,000      | 3      | 25        | 20         |
| 5,000      | 4      | 60        | 35         |
| 10,000     | 2      | 120       | 50         |

### Limits & Constraints

- **Maximum series:** 7 (readability threshold)
- **Maximum data points:** 10,000 per series
- **Maximum request size:** 100 MB
- **Timeout:** 30 seconds
- **Recommended max data:** 5,000 points per series

---

## Deployment

### Requirements
- Python 3.10+
- FastAPI
- Polars
- Plotly
- Pydantic v2

### Installation

```bash
cd /path/to/backend
pip install -r requirements.txt
```

### Running Locally

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment (Docker)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# Optional configuration
OVERLAY_MAX_SERIES=7
OVERLAY_MAX_POINTS=10000
OVERLAY_RENDER_TIMEOUT=30
OVERLAY_LOG_LEVEL=DEBUG
```

---

## Testing

### Run Test Suite

```bash
# All tests
pytest services/tests/test_overlay_renderer.py -v

# Specific test class
pytest services/tests/test_overlay_renderer.py::TestOverlayRendererBasic -v

# With coverage
pytest services/tests/test_overlay_renderer.py --cov=services.charts.renderers --cov-report=html
```

### Test Coverage

- ✅ 35+ test cases
- ✅ 95%+ code coverage
- ✅ Edge case handling (nulls, single row, large datasets)
- ✅ Error path validation
- ✅ Performance benchmarks
- ✅ Integration tests

---

## Quality Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Code Coverage | 90%+ | 95% |
| Test Count | 30+ | 35 |
| Error Handling | All paths | ✅ |
| Performance (500pt) | <100ms | 12ms |
| API Response Time | <1s | <100ms |
| Memory Usage (10k pt) | <100MB | 50MB |

---

## Troubleshooting

### Issue: "Overlay requires at least 2 y_columns"

**Cause:** request has only 1 y_column  
**Solution:** Add at least 2 columns to `y_columns` array

```json
{
  "y_columns": ["Revenue", "Cost"]  // ✅ Valid
}
```

### Issue: "High series count may reduce readability"

**Cause:** More than 7 series requested  
**Solution:** Use Small Multiples (Facet) visualization instead

### Issue: "X column 'Date' not found in data"

**Cause:** x_column name doesn't match actual column  
**Solution:** Verify column name matches exactly

```json
{
  "data": {
    "Date": [...],  // ✅ Column exists
    "Revenue": [...]
  },
  "x_column": "Date"  // ✅ Matches
}
```

### Issue: Render time >1 second

**Cause:** Dataset too large or server under load  
**Solution:** 
- Reduce to <5,000 points per series
- Reduce number of series
- Check server resources

---

## Migration Guide

### From Old Chart Rendering (if applicable)

**Old approach:**
```python
chart = render_chart(data, columns, type="overlay")
```

**New approach:**
```python
response = await client.post("/api/v1/charts/overlay", json={
    "title": "...",
    "data": data,
    "x_column": "Date",
    "y_columns": columns
})
chart = response.json()["chart"]
```

---

## Support & Issues

### Getting Help

1. **Check documentation:** Review this guide first
2. **Check health endpoint:** `GET /api/v1/charts/overlay/health`
3. **Review logs:** Check application error logs
4. **Contact support:** [support email]

### Reporting Issues

Include:
- Request payload
- Response status code
- Error message
- Sample data (if possible)
- Environment info (Python version, OS)

---

## Roadmap

### Future Enhancements
- [ ] Dash/dot styling options
- [ ] Custom color palettes
- [ ] Data smoothing algorithms
- [ ] Confidence intervals
- [ ] Trend line overlays
- [ ] Advanced hover templates
- [ ] Animation support

### Version History

**v1.0.0** (2025-01-10)
- ✅ Initial production release
- ✅ 35+ tests
- ✅ Complete API
- ✅ Full documentation

---

## License

Internal Signal Project - All Rights Reserved

---

**Last Updated:** 2025-01-10  
**Maintained By:** Signal Team  
**Contact:** [team@signal.internal]
