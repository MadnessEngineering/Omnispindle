# Gateway Statistics Dashboard Enhancements

This document outlines the planned enhancements and fixes for the Multi-Gateway Statistics Dashboard to support date-based collections and cross-date comparisons.

## High Priority Tasks

### 1. Fix Process Gateway Stats Function
- [x] Fix regex pattern for date validation (remove double escaping)
- [x] Remove duplicate date sorting code
- [x] Ensure proper handling of date information in MQTT topics

### 2. Complete Gateway Details UI
- [ ] Implement full date-based filtering in Gateway Details view
- [ ] Add comparison visualization between dates
- [ ] Add visual indicators for metrics changes (increase/decrease)
- [ ] Complete gateway selection and filtering UI

### 3. Enhance mongo_tasks.py
- [ ] Optimize MongoDB queries across date collections
- [ ] Add support for querying multiple date collections
- [ ] Standardize date handling between MongoDB and MQTT
- [ ] Include metadata to support date-based comparisons

## Medium Priority Tasks

### 4. Additional Dashboard Features
- [ ] Add date range selection for trend analysis
- [ ] Implement gateway grouping by characteristics
- [ ] Add data export capabilities
- [ ] Create dashboard metrics summary across dates

### 5. Visualization Improvements
- [ ] Add trend charts showing metrics over time
- [ ] Implement heatmaps for gateway activity patterns
- [ ] Add color-coded performance indicators

## Low Priority Tasks

### 6. Documentation and Usability
- [ ] Add tooltips explaining dashboard metrics
- [ ] Create user documentation
- [ ] Implement responsive design improvements for mobile
- [ ] Add configuration options for default views

## Technical Implementation Details

### MongoDB Query Optimization
```python
# Example of optimized MongoDB query for date-based collections
def query_collection_by_date(self, collection_date, gateway=None):
    self.collection = self.db[collection_date]
    query = {"gateway": gateway} if gateway else {}
    return self.collection.find(query)
```

### MQTT Topic Structure
```
projects/em-beta/subscriptions/gateway-stats/YYYY-MM-DD
```

### Date Handling in Node-RED
```javascript
// Extract date from topic
const topicParts = msg.topic.split('/');
if (topicParts.length > 3) {
    const possibleDate = topicParts[topicParts.length - 1];
    if (/^\d{4}-\d{2}-\d{2}$/.test(possibleDate)) {
        collectionDate = possibleDate;
    }
}
``` 
