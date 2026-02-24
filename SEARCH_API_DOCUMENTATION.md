# Web Search Tool Improvements Documentation

## Overview

This document describes the improvements made to the web search functionality in the agent.py file, including multiple provider support, better error handling, and flexible configuration.

## Key Improvements

### 1. Multiple Search Provider Support

The agent now supports **6 different search providers**:

| Provider | Type | Cost | Self-Hosted | Best For |
|----------|------|------|-------------|----------|
| **Exa** | Commercial | $49/8,000 credits | No | Semantic discovery, research |
| **Firecrawl** | Commercial | $16/1,000 credits | Yes | LLM-ready extraction, RAG |
| **Tavily** | Commercial | $0.008/credit | Yes | RAG, AI agents, fast search |
| **Brave** | Commercial | $5-9/1,000 requests | No | Privacy-focused, independent index |
| **OpenSerp** | Open Source | Free | Yes | Free, self-hosted, multi-engine |
| **Google Custom Search** | Google | 100 free/day | No | Custom site search |

### 2. Configuration Options

#### Environment Variables

Set `SEARCH_PROVIDER` to choose your search engine:

```bash
SEARCH_PROVIDER=firecrawl  # or exa, tavily, brave, openserp, google_custom
```

#### Required API Keys by Provider

**Exa:**
- `EXA_API_KEY`

**Firecrawl:**
- `FIRECRAWL_API_KEY`
- `FIRECRAWL_BASE_URL` (optional, defaults to `https://api.firecrawl.dev`)

**Tavily:**
- `TAVILY_API_KEY`
- `TAVILY_API_BASE_URL` (optional, defaults to `https://api.tavily.com`)

**Brave:**
- `BRAVE_API_KEY`

**OpenSerp (self-hosted):**
- `OPENSERP_BASE_URL` (optional, defaults to `http://localhost:7000`)
- `OPENSERP_ENGINES` (optional, defaults to `google,bing,duckduckgo`)

**Google Custom Search:**
- `GOOGLE_API_KEY`
- `GOOGLE_CSE_ID`

### 3. Unified Search Interface

The `web_search()` function provides a unified interface that automatically routes to the configured provider:

```python
def web_search(query: str) -> List[Dict[str, Any]]:
    """
    Main web search function that routes to the configured search provider.
    This is the function that should be used by the agent.
    """
    search_func = select_search_provider()
    return search_func(query)
```

### 4. Improved Error Handling

Each search provider has comprehensive error handling:

- **ImportError**: Tells you which library to install
- **API errors**: Returns detailed error messages
- **Missing configuration**: Validates required environment variables
- **Network errors**: Proper timeout handling

### 5. Better Search Results Formatting

All search providers return a consistent format:

```python
[
    {
        "title": "Result Title",
        "url": "https://example.com",
        "content": "Result content or summary",
        "score": 0.95,  # Optional relevance score
        # Provider-specific additional fields
    }
]
```

## Provider Comparison

### Exa (Current Default)
- **Pros**: Best semantic understanding, high accuracy (94.9%), independent index
- **Cons**: More expensive at scale, closed source
- **Use when**: You need the best semantic search quality and don't mind paying

### Firecrawl (Recommended Alternative)
- **Pros**: Open source, self-hostable, combines search + extraction, 77.2% coverage vs Exa's 69.2%
- **Cons**: Requires API key, less mature semantic search than Exa
- **Use when**: You want cost-effective extraction with good search quality

### Tavily (Fast & Cheap)
- **Pros**: Fastest response times (~1.8s), cheapest at scale, RAG-optimized
- **Cons**: Search quality not as sophisticated as Exa
- **Use when**: You need fast, cheap search for RAG applications

### Brave (Privacy-Focused)
- **Pros**: Independent index (30B+ pages), no user tracking, SOC 2 certified
- **Cons**: Returns raw JSON SERPs, less AI-optimized
- **Use when**: Privacy is critical or you need an independent search index

### OpenSerp (Free & Open Source)
- **Pros**: Completely free, self-hosted, supports multiple engines (Google, Bing, DuckDuckGo, etc.)
- **Cons**: Requires self-hosting infrastructure, less polished than commercial options
- **Use when**: You need a completely free, open-source solution

### Google Custom Search (Limited but Official)
- **Pros**: Official Google integration, 100 free queries/day
- **Cons**: Limited to custom search indexes, not full Google web
- **Use when**: You need Google results and have a custom search engine set up

## Migration Guide

### From Exa Only to Multi-Provider

1. **Update your `.env` file**:

```bash
# Add your preferred provider's API key
SEARCH_PROVIDER=firecrawl
FIRECRAWL_API_KEY=your_api_key
```

2. **Install the new dependency** (if using Firecrawl):

```bash
pip install firecrawl
```

3. **No code changes needed** - the `web_search()` function works the same way

### Adding Custom Search Providers

To add a new search provider, implement a function following this pattern:

```python
def new_provider_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Search using the new provider.
    Returns a list of search results with content.
    """
    try:
        # Your implementation here
        results = perform_search(query)
        
        # Format results consistently
        return [
            {
                "title": result.title,
                "url": result.url,
                "content": result.content,
                # Add provider-specific fields
            }
            for result in results
        ]
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="new_provider_search_tool",
                error_type=type(e).__name__,
                message=f"Provider search failed: {str(e)}",
                attempted_input={"query": query},
            ).model_dump_json()
        )
```

Then add it to the provider map in `select_search_provider()`:

```python
provider_map = {
    "exa": exa_search_tool,
    "firecrawl": firecrawl_search_tool,
    # ... add your new provider
    "new_provider": new_provider_search_tool,
}
```

## Performance Comparison

Based on independent benchmarks and user reports:

| Provider | Avg Response Time | Cost (100K searches) | Open Source |
|----------|------------------|---------------------|-------------|
| Firecrawl | ~2.5s | $83 | Yes |
| Tavily | ~1.8s | $800 | Yes |
| Brave | ~2.0s | $500-900 | No |
| Exa | ~3.0s | $1,000+ | No |
| OpenSerp | ~2.2s | $0 (self-hosted) | Yes |
| Google Custom | ~2.5s | $150 (beyond free tier) | No |

## Testing Different Providers

To test different providers, simply change the `SEARCH_PROVIDER` environment variable:

```bash
# Test Firecrawl
export SEARCH_PROVIDER=firecrawl
export FIRECRAWL_API_KEY=your_key

# Test Tavily
export SEARCH_PROVIDER=tavily
export TAVILY_API_KEY=your_key

# Test OpenSerp (self-hosted)
export SEARCH_PROVIDER=openserp
docker run -p 127.0.0.1:7000:7000 karust/openserp serve
```

## Troubleshooting

### Provider Not Found Error

If you see "Unknown search provider", check:
1. The `SEARCH_PROVIDER` environment variable is set correctly
2. The provider name matches exactly (case-sensitive)

### Missing API Key Error

If you see "Missing required environment variables", ensure:
1. The API key is set in your `.env` file
2. The `.env` file is in the correct directory
3. You've reloaded your environment after changes

### Search Results Empty

If search returns no results:
1. Check your API credits/balance
2. Verify the query is valid
3. Try a different provider
4. Check network connectivity (for self-hosted providers)

## Future Improvements

Potential enhancements to consider:

1. **Caching layer**: Add Redis caching for repeated queries
2. **Load balancing**: Rotate between multiple providers
3. **Fallback chain**: Try primary provider, fall back to secondary
4. **Analytics**: Track usage and costs per provider
5. **Rate limiting**: Implement provider-specific rate limiting
6. **Custom ranking**: Add provider-specific result ranking logic

## References

- [Exa Documentation](https://docs.exa.ai)
- [Firecrawl Documentation](https://docs.firecrawl.dev)
- [Tavily Documentation](https://docs.tavily.com)
- [Brave Search API](https://brave.com/search/api/)
- [OpenSerp GitHub](https://github.com/karust/openserp)
- [Google Custom Search API](https://developers.google.com/custom-search/v1/overview)