# Hybrid Retrieval Weighting Strategy Analysis

## Our Use Case Context

### Query Types in Consultant Assistant
1. **Direct Entity Queries** (30-40% of queries)
   - "get the GenePoint account"
   - "show opportunity 001ABC"
   - Need: High precision for exact matches

2. **Follow-up References** (20-30% of queries)
   - "that account", "the same one"
   - Need: Strong semantic understanding + context

3. **Exploratory Queries** (20-30% of queries)
   - "biotechnology companies"
   - "opportunities closing this month"
   - Need: Semantic understanding of concepts

4. **Natural Language** (10-20% of queries)
   - "what's the status of our biggest deal?"
   - Need: Both semantic and entity matching

## Proposed Weighting Strategy

### 1. **Adaptive Weighting Based on Query Type**

```python
def determine_weights(query_text, has_embeddings):
    # Analyze query characteristics
    has_entity_id = bool(re.search(r'\b[0-9]{3}[A-Za-z0-9]+\b', query_text))
    has_follow_up = any(word in query_text.lower() for word in ['that', 'the same', 'it'])
    word_count = len(query_text.split())
    
    if not has_embeddings:
        # Pure keyword fallback
        return {'keyword': 1.0, 'semantic': 0.0}
    
    if has_entity_id:
        # Direct entity reference - favor keywords
        return {
            'semantic': 0.15,
            'keyword': 0.60,
            'context': 0.15,
            'graph': 0.10
        }
    
    if has_follow_up:
        # Follow-up query - heavily favor semantic + context
        return {
            'semantic': 0.50,
            'keyword': 0.10,
            'context': 0.35,
            'graph': 0.05
        }
    
    if word_count <= 2:
        # Short query - balance both
        return {
            'semantic': 0.35,
            'keyword': 0.35,
            'context': 0.15,
            'graph': 0.15
        }
    
    # Natural language query - favor semantic
    return {
        'semantic': 0.45,
        'keyword': 0.20,
        'context': 0.20,
        'graph': 0.15
    }
```

### 2. **Recommended Implementation**

**Stage 1: Initial Implementation (Current)**
- Fixed weights with conditional logic
- Simple but effective for MVP

**Stage 2: RRF Fusion (Next Step)**
```python
def reciprocal_rank_fusion(results_lists, k=60):
    """
    Combine multiple ranked lists using RRF.
    k=60 is standard, lower k gives more weight to top results
    """
    fused_scores = {}
    for results in results_lists:
        for rank, (node_id, score) in enumerate(results):
            if node_id not in fused_scores:
                fused_scores[node_id] = 0
            fused_scores[node_id] += 1 / (k + rank + 1)
    return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
```

**Stage 3: Learning from Usage (Future)**
- Track which results users actually interact with
- Use implicit feedback to tune weights
- A/B test different strategies

### 3. **Specific Recommendations for Our System**

**For Entity Queries:**
- Keyword: 60%
- Semantic: 15%
- Context: 15%
- Graph: 10%

**For Follow-up Queries:**
- Semantic: 50%
- Context: 35%
- Keyword: 10%
- Graph: 5%

**For Exploratory Queries:**
- Semantic: 45%
- Keyword: 20%
- Context: 20%
- Graph: 15%

### 4. **Additional Considerations**

**Boosting Factors:**
- **Exact name match**: 2x boost
- **Recent access**: 1.5x boost (last 5 minutes)
- **High PageRank**: 1.2x boost
- **User's frequent entities**: 1.3x boost

**Penalties:**
- **Generic-only query**: 0.5x penalty
- **Stale nodes**: Progressive penalty based on decay

## Performance Optimization

### Current Approach Benefits
1. **Low Latency**: No reranking stage needed for small datasets
2. **Interpretable**: Clear why results were returned
3. **Flexible**: Easy to adjust weights based on feedback

### Future Optimizations
1. **Query Expansion**: Use embeddings to expand queries with synonyms
2. **Personalization**: Track user's common entities and queries
3. **Caching**: Cache embeddings for frequently accessed nodes
4. **Batch Processing**: Process similar queries together

## Testing Strategy

1. **Create Query Test Set**:
   - 20 direct entity queries
   - 20 follow-up references
   - 20 exploratory queries
   - 20 natural language queries

2. **Metrics to Track**:
   - Precision@1 (is the top result correct?)
   - Recall@5 (are all relevant results in top 5?)
   - Response time
   - User interaction (which results clicked)

3. **A/B Testing**:
   - Current weights vs proposed weights
   - Fixed weights vs adaptive weights
   - With/without RRF fusion

## Conclusion

Based on research and our specific use case:

1. **Keep the hybrid approach** - it's industry best practice
2. **Implement adaptive weighting** based on query type
3. **Start with proposed weights**, then tune based on usage
4. **Consider RRF fusion** as next evolution
5. **Track metrics** to validate improvements

The key insight: Different query types need different strategies, and our system should adapt accordingly.