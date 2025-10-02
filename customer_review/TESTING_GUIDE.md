# Testing Guide - New Features

## 🚀 Quick Start

### 1. Restart Flask Server
```bash
python app.py
```

### 2. Login to Application
- User login: `http://localhost:5000/login`
- Make sure you have some reviews with timestamps in your database

---

## ✅ Feature Testing Checklist

### Feature 1: Sentiment Trends Over Time

#### Test Steps:
1. **Navigate to Sentiment Trends**
   - Click "Sentiment Trends" in the sidebar
   - URL: `http://localhost:5000/sentiment-trends`

2. **Verify Chart Display**
   - [ ] Line chart appears with multiple colored lines
   - [ ] X-axis shows dates
   - [ ] Y-axis shows sentiment scores (-1 to +1)
   - [ ] Legend shows aspect names
   - [ ] Hover shows tooltip with exact values

3. **Test Date Filtering**
   - [ ] Set start date (e.g., last week)
   - [ ] Set end date (e.g., today)
   - [ ] Click "Apply Filter"
   - [ ] Chart updates with filtered data
   - [ ] Click "Reset" - returns to all data

4. **Edge Cases**
   - [ ] No data in date range → Shows "No Trend Data Available"
   - [ ] Single day data → Shows single point
   - [ ] Multiple aspects → All show on same chart

---

### Feature 2: Date Range Filtering

#### Test on Aspect Analysis Page:

1. **Navigate to Aspect Analysis**
   - Click "Aspect Analysis" in sidebar
   - URL: `http://localhost:5000/aspect-analysis`

2. **Test Filter Form**
   - [ ] Date filter form appears at top
   - [ ] Start date picker works
   - [ ] End date picker works
   - [ ] "Apply Filter" button works
   - [ ] "Reset" button clears filters

3. **Verify Data Filtering**
   - [ ] Set date range
   - [ ] Tables update with filtered data
   - [ ] Chart updates accordingly
   - [ ] URL contains `?start_date=...&end_date=...`

4. **Test Filter Persistence**
   - [ ] Apply filter
   - [ ] Click export button
   - [ ] Exported file contains only filtered data

---

### Feature 3: Export Functionality

#### CSV Export:

1. **Basic Export**
   - [ ] Click "Export CSV" button (green)
   - [ ] File downloads automatically
   - [ ] Filename format: `aspect_analysis_YYYYMMDD_HHMMSS.csv`

2. **Verify CSV Content**
   - [ ] Open downloaded CSV
   - [ ] Headers present: Aspect, Positive, Negative, Neutral, Total, Percentages, etc.
   - [ ] Categorized aspects section exists
   - [ ] Uncategorized aspects section exists
   - [ ] Data matches what's displayed on page

3. **Test with Filters**
   - [ ] Apply date filter
   - [ ] Export CSV
   - [ ] Verify only filtered data is exported

#### PDF Export:

1. **Basic Export**
   - [ ] Click "Export PDF" button (red)
   - [ ] PDF downloads automatically
   - [ ] Filename format: `aspect_analysis_YYYYMMDD_HHMMSS.pdf`

2. **Verify PDF Content**
   - [ ] Open downloaded PDF
   - [ ] Title: "Customer Review Insight AI"
   - [ ] Subtitle: "Aspect Sentiment Analysis Report"
   - [ ] Metadata shows: User, Generated date, Date range (if filtered)
   - [ ] Categorized aspects table (blue header)
   - [ ] Uncategorized aspects table (red header)
   - [ ] Tables are properly formatted

3. **Test with Filters**
   - [ ] Apply date filter
   - [ ] Export PDF
   - [ ] PDF shows date range in metadata
   - [ ] Only filtered data appears

---

## 🔍 Detailed Test Scenarios

### Scenario 1: New User with No Data
**Expected Behavior:**
- Sentiment Trends: "No Trend Data Available" message
- Aspect Analysis: Works normally (shows empty state)
- Export: Creates empty/minimal report

### Scenario 2: User with Reviews on Same Day
**Expected Behavior:**
- Sentiment Trends: Shows single data point per aspect
- Date filter: Can filter by that specific day
- Export: Contains that day's data

### Scenario 3: User with Reviews Across Multiple Days
**Expected Behavior:**
- Sentiment Trends: Shows line chart with trends
- Each aspect has its own colored line
- Trends show sentiment evolution over time

### Scenario 4: Date Range with No Data
**Expected Behavior:**
- Filter applied successfully
- "No data in selected range" message
- Export creates report noting date range but no data

---

## 🐛 Common Issues & Solutions

### Issue 1: Chart Not Displaying
**Possible Causes:**
- No reviews with timestamps
- JavaScript errors in console
- Chart.js not loaded

**Solution:**
- Check browser console for errors
- Verify Chart.js CDN is accessible
- Ensure reviews have valid timestamps

### Issue 2: PDF Export Fails
**Possible Causes:**
- reportlab not installed
- Import errors

**Solution:**
```bash
pip install reportlab
```

### Issue 3: Date Filter Not Working
**Possible Causes:**
- Date format mismatch
- Timezone issues

**Solution:**
- Use YYYY-MM-DD format
- Check server logs for errors

### Issue 4: Export Shows Wrong Data
**Possible Causes:**
- Filter not applied to export route
- Session/cache issues

**Solution:**
- Clear browser cache
- Check URL parameters are passed to export routes

---

## 📊 Sample Test Data

If you need to create test data:

```python
# In Flask shell or script
from datetime import datetime, timedelta
from models import db, RawText, AspectSentiment, Aspect

# Create reviews with different dates
for i in range(7):
    date = datetime.now() - timedelta(days=i)
    review = RawText(
        content=f"Test review {i}",
        user_id=1,
        timestamp=date,
        sentiment="POSITIVE",
        score=0.8
    )
    db.session.add(review)

db.session.commit()
```

---

## ✅ Final Verification

Before considering testing complete:

1. **All Routes Work**
   - [ ] `/sentiment-trends` loads
   - [ ] `/aspect-analysis` loads with filters
   - [ ] `/export-csv` downloads file
   - [ ] `/export-pdf` downloads file

2. **UI/UX Check**
   - [ ] Navigation link appears
   - [ ] Buttons are styled correctly
   - [ ] Forms are responsive
   - [ ] Charts are readable

3. **Data Accuracy**
   - [ ] Trends match actual data
   - [ ] Filters work correctly
   - [ ] Exports contain accurate data

4. **Error Handling**
   - [ ] No console errors
   - [ ] Graceful handling of empty data
   - [ ] Proper error messages

---

## 📝 Test Results Template

```
Date: ___________
Tester: ___________

Feature 1: Sentiment Trends
- Chart Display: ✅ / ❌
- Date Filtering: ✅ / ❌
- Edge Cases: ✅ / ❌
Notes: _______________________

Feature 2: Date Range Filtering
- Filter Form: ✅ / ❌
- Data Updates: ✅ / ❌
- Persistence: ✅ / ❌
Notes: _______________________

Feature 3: Export
- CSV Export: ✅ / ❌
- PDF Export: ✅ / ❌
- Filtered Export: ✅ / ❌
Notes: _______________________

Overall Status: PASS / FAIL
```

---

## 🎯 Success Criteria

All features are considered successfully implemented when:

1. ✅ Sentiment trends chart displays correctly with real data
2. ✅ Date filtering works on both pages
3. ✅ CSV export downloads with accurate data
4. ✅ PDF export generates professional report
5. ✅ All exports respect date filters
6. ✅ No critical errors in console or logs
7. ✅ UI is consistent with existing design
8. ✅ Features work across different browsers

---

## 📞 Support

If you encounter issues:
1. Check browser console for JavaScript errors
2. Check Flask server logs for Python errors
3. Verify all dependencies are installed
4. Review `FEATURES_IMPLEMENTED.md` for technical details
