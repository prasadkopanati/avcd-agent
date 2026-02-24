#!/usr/bin/env python3
"""
Test script for web search providers.
This script tests each search provider to ensure they work correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_provider(name, search_func, query="python programming"):
    """Test a search provider function."""
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"{'='*60}")
    
    try:
        results = search_func(query)
        
        if not results:
            print(f"❌ {name}: No results returned")
            return False
            
        print(f"✅ {name}: Success! Found {len(results)} results")
        print(f"\nFirst result:")
        
        if isinstance(results[0], dict):
            first = results[0]
            print(f"  Title: {first.get('title', 'N/A')}")
            print(f"  URL: {first.get('url', 'N/A')}")
            print(f"  Content preview: {first.get('content', 'N/A')[:100]}...")
        else:
            print(f"  {results[0]}")
            
        return True
        
    except ImportError as e:
        print(f"⚠️  {name}: Import error - {e}")
        print(f"  Install with: pip install {str(e).split(' ')[-1] if ' ' in str(e) else 'package'}")
        return False
        
    except Exception as e:
        print(f"❌ {name}: Error - {str(e)[:100]}")
        return False

def main():
    """Run tests on all search providers."""
    print("Web Search Provider Test Suite")
    print("="*60)
    
    # Import the agent module
    try:
        from cado.agent import (
            exa_search_tool,
            firecrawl_search_tool,
            tavily_search_tool,
            brave_search_tool,
            openserp_search_tool,
            google_custom_search_tool
        )
    except ImportError as e:
        print(f"Failed to import search functions: {e}")
        print("Make sure you have installed the required packages:")
        print("pip install exa-py firecrawl")
        return
    
    results = {}
    
    # Test each provider
    results['Exa'] = test_provider(
        "Exa",
        exa_search_tool,
        "python programming language"
    )
    
    results['Firecrawl'] = test_provider(
        "Firecrawl",
        firecrawl_search_tool,
        "python web scraping"
    )
    
    results['Tavily'] = test_provider(
        "Tavily",
        tavily_search_tool,
        "python ai agents"
    )
    
    results['Brave'] = test_provider(
        "Brave",
        brave_search_tool,
        "python programming"
    )
    
    results['OpenSerp'] = test_provider(
        "OpenSerp",
        openserp_search_tool,
        "python programming"
    )
    
    results['Google Custom Search'] = test_provider(
        "Google Custom Search",
        google_custom_search_tool,
        "python programming"
    )
    
    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    
    for provider, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {provider}")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All providers working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} provider(s) not configured or not working")
        print("Check your API keys in the .env file")
        return 1

if __name__ == "__main__":
    sys.exit(main())