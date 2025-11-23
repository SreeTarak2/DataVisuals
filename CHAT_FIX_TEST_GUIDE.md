# 🧪 Chat Fix Test Guide

**Date:** November 23, 2025  
**Fixes Applied:**
1. ✅ Prompt engineering for non-empty responses
2. ✅ Chart generation instructions
3. ✅ Robust response extraction logic

---

## 🔄 STEP 1: Restart Backend

Your backend MUST be restarted to load the fixes!

```bash
# Kill current backend process
pkill -f "uvicorn main:app"

# Navigate to backend directory
cd /home/vamsi/nothing/datasage/version2/backend

# Restart with reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Wait for:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 🧪 STEP 2: Test Cases

### Test Case 1: Simple Question (No Chart)

**Query:** "What columns are in this dataset?"

**Expected Response:**
```json
{
  "response": "The dataset contains 6 columns: batsman, total_runs, out, numberofballs, average, and strikerate. These columns capture cricket batting statistics.",
  "chart_config": null,
  "conversation_id": "..."
}
```

**Check Logs:**
```bash
tail -f backend.log | grep -A 5 "Extracted ai_text"
```

Should show:
```
Extracted ai_text (XXX chars): The dataset contains 6 columns...
```

**❌ If you see:**
- `Extracted ai_text (0 chars): EMPTY` → Backend not restarted!

---

### Test Case 2: Chart Request (CRITICAL)

**Query:** "Show me a bar chart of total runs by batsman"

**Expected Response:**
```json
{
  "response": "Here's a bar chart showing total runs by each batsman...",
  "chart_config": {
    "type": "bar",
    "x": "batsman",
    "y": "total_runs",
    "title": "Total Runs by Batsman",
    "xaxis": {"title": "Batsman"},
    "yaxis": {"title": "Total Runs"}
  },
  "conversation_id": "..."
}
```

**Check Logs:**
```bash
tail -f backend.log | grep "Chart config"
```

Should show:
```
Chart config received: {"type":"bar","x":"batsman","y":"total_runs"...}
```

**❌ If chart_config is null:**
1. Check if query uses chart keywords: "show", "draw", "plot", "visualize", "create chart"
2. Verify prompt loaded correctly (check token count in logs)
3. LLM may need more explicit request

---

### Test Case 3: Multiple Chart Types

Try these queries:

| Query | Expected Chart Type |
|-------|-------------------|
| "Plot average vs strike rate" | scatter |
| "Show distribution of total runs" | histogram |
| "Create a pie chart of batsmen" | pie |
| "Line chart of runs over time" | line |

---

## 📊 STEP 3: Check Logs

### Successful Response Pattern:

```
2025-11-23 XX:XX:XX - core.prompts - INFO - Built prompt ~334 tokens for task=conversational
2025-11-23 XX:XX:XX - httpx - INFO - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2025-11-23 XX:XX:XX - services.llm_router - INFO - Successfully parsed JSON from OpenRouter
2025-11-23 XX:XX:XX - services.ai.ai_service - INFO - LLM Response structure: {
  "response_text": "Here's the analysis...",
  "chart_config": {...},
  "confidence": "High"
}
2025-11-23 XX:XX:XX - services.ai.ai_service - INFO - Extracted ai_text (123 chars): Here's the analysis...
2025-11-23 XX:XX:XX - services.ai.ai_service - INFO - Chart config received: {"type":"bar"...}
```

### ❌ Error Patterns:

**Empty Response Error:**
```
ERROR - Empty response from LLM
```
→ **Solution:** Check if prompt format changed

**JSON Parse Error:**
```
ERROR - JSON parse failed. Raw content: ...
```
→ **Solution:** LLM not following format. Check prompt clarity.

**No Chart When Expected:**
```
INFO - Extracted ai_text (XXX chars): ...
# No "Chart config received" line
```
→ **Solution:** Query needs chart keywords or prompt needs enhancement

---

## 🔍 STEP 4: Debug Commands

### Check Backend Status
```bash
ps aux | grep uvicorn | grep -v grep
```

### Monitor Live Logs
```bash
cd /home/vamsi/nothing/datasage/version2/backend
tail -f backend.log
```

### Filter Specific Events
```bash
# Chart related
tail -f backend.log | grep -E "chart|Chart"

# Response extraction
tail -f backend.log | grep -E "Extracted|response_text"

# Errors only
tail -f backend.log | grep ERROR
```

### Test API Directly (Bypass Frontend)
```bash
# Get auth token from browser DevTools (localStorage)
TOKEN="your_jwt_token_here"
DATASET_ID="0ac6ebf0-1669-42b6-a74f-944add492e31"

curl -X POST "http://localhost:8000/api/datasets/${DATASET_ID}/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "message": "Show me a bar chart of total runs",
    "conversation_id": null
  }' | jq
```

---

## ✅ SUCCESS CRITERIA

### Must Have:
- [x] Backend restarts without errors
- [x] Simple questions return non-empty responses
- [x] Chart requests include `chart_config` object
- [x] Logs show "Extracted ai_text (XXX chars)" with XXX > 0
- [x] No "EMPTY" in extraction logs

### Nice to Have:
- [x] Chart appears in frontend UI
- [x] Chart uses correct data columns
- [x] Multiple chart types work

---

## 🐛 TROUBLESHOOTING

### Issue: "Empty response from LLM"

**Cause:** Prompt format incorrect or LLM not following instructions

**Fix:**
1. Check prompt token count in logs (should be ~330-400 tokens)
2. Verify prompt includes example format
3. Manually test with simple query

### Issue: Chart never generated

**Cause:** LLM not recognizing chart keywords

**Fix:**
1. Use explicit keywords: "Show", "Draw", "Plot", "Create chart"
2. Check DATASET_CONTEXT has valid columns
3. Verify chart_config example in prompt is valid JSON

### Issue: Frontend not showing chart

**Cause:** Frontend parsing or rendering issue (separate from backend)

**Fix:**
1. Check browser console for errors
2. Verify PlotlyChart component exists
3. Check chart_config structure matches frontend expectations

---

## 🚀 NEXT STEPS

Once all tests pass:

1. **Install tiktoken** (for production LLM router):
   ```bash
   pip install tiktoken==0.5.2
   ```

2. **Implement streaming** (see CHAT_ENHANCEMENT_COMPLETE_GUIDE.md)

3. **Add monitoring** (track token usage, costs, latency)

4. **Production deployment** with proper error handling

---

## 📝 Test Results Template

Fill this out after testing:

```
Date: ___________
Tester: ___________

✅ Backend restarted successfully
✅ Simple query returns content: YES / NO
✅ Chart query returns chart_config: YES / NO
✅ Logs show extraction: YES / NO
✅ Frontend displays response: YES / NO
✅ Frontend displays chart: YES / NO

Issues Found:
1. ___________
2. ___________

Notes:
___________
```

---

**Run the tests and report back!** 🎯
