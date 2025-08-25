#!/usr/bin/env python3
"""
Demo script showing how to use the new Omnispindle tools:
- point_out_obvious: For highlighting obvious things with humor
- bring_your_own: For creating custom tools on the fly
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from Omnispindle import tools
from Omnispindle.context import Context


async def demo_point_out_obvious():
    """Demonstrate the point_out_obvious tool"""
    print("\n" + "="*60)
    print("DEMO: Point Out Obvious Tool")
    print("="*60)
    print("\nThis tool helps AI agents highlight obvious things to humans")
    print("with varying levels of sarcasm and humor.\n")
    
    ctx = Context(user={"sub": "demo_user"})
    
    examples = [
        {
            "observation": "You need to save a file before the changes take effect",
            "sarcasm": 2,
            "context": "When user forgets to save"
        },
        {
            "observation": "The error message literally tells you what's wrong",
            "sarcasm": 7,
            "context": "When user ignores error messages"
        },
        {
            "observation": "Deleting system files might break your system",
            "sarcasm": 10,
            "context": "When user is about to do something dangerous"
        }
    ]
    
    for example in examples:
        print(f"\nContext: {example['context']}")
        print(f"Sarcasm Level: {example['sarcasm']}/10")
        
        result = await tools.point_out_obvious(
            example['observation'], 
            example['sarcasm'], 
            ctx
        )
        result_dict = json.loads(result)
        
        if result_dict.get("success"):
            print(f"AI Response: {result_dict['data']['response']}")
        print("-" * 40)


async def demo_bring_your_own():
    """Demonstrate the bring_your_own tool"""
    print("\n" + "="*60)
    print("DEMO: Bring Your Own Tool")
    print("="*60)
    print("\nThis tool allows AI models to create and execute")
    print("custom tools on the fly!\n")
    
    ctx = Context(user={"sub": "admin_demo"})
    
    # Example 1: Create a tool that generates ASCII art
    print("Example 1: ASCII Art Generator")
    print("-" * 40)
    
    ascii_art_code = """
async def main(text="HELLO", style="banner"):
    if style == "banner":
        lines = []
        lines.append("+" + "-" * (len(text) + 2) + "+")
        lines.append("| " + text + " |")
        lines.append("+" + "-" * (len(text) + 2) + "+")
        return "\\n".join(lines)
    elif style == "wave":
        return "~" * 3 + " " + text + " " + "~" * 3
    else:
        return text
"""
    
    result = await tools.bring_your_own(
        tool_name="ascii_art",
        code=ascii_art_code,
        runtime="python",
        timeout=5,
        args={"text": "OMNISPINDLE", "style": "banner"},
        persist=False,
        ctx=ctx
    )
    
    result_dict = json.loads(result)
    if result_dict.get("success"):
        print("Generated ASCII Art:")
        print(result_dict['data']['result'])
    
    # Example 2: Create a tool that analyzes text
    print("\n\nExample 2: Text Analyzer")
    print("-" * 40)
    
    text_analyzer_code = """
async def main(text=""):
    import re
    
    words = text.split()
    chars = len(text)
    sentences = len(re.findall(r'[.!?]+', text))
    
    return {
        "character_count": chars,
        "word_count": len(words),
        "sentence_count": sentences,
        "average_word_length": sum(len(w) for w in words) / len(words) if words else 0,
        "longest_word": max(words, key=len) if words else "",
        "has_numbers": bool(re.search(r'\\d', text)),
        "has_urls": bool(re.search(r'https?://', text))
    }
"""
    
    sample_text = "The Omnispindle MCP server is amazing! It has 20+ tools. Check it out at https://example.com"
    
    result = await tools.bring_your_own(
        tool_name="text_analyzer",
        code=text_analyzer_code,
        runtime="python",
        timeout=5,
        args={"text": sample_text},
        persist=True,  # Save this tool for later use!
        ctx=ctx
    )
    
    result_dict = json.loads(result)
    if result_dict.get("success"):
        print(f"Analyzing: '{sample_text}'")
        print("\nAnalysis Results:")
        analysis = result_dict['data']['result']
        for key, value in analysis.items():
            print(f"  {key}: {value}")
        print(f"\nTool persisted: {result_dict['data']['persisted']}")
    
    # Example 3: Create a bash tool to check system resources
    print("\n\nExample 3: System Resource Checker")
    print("-" * 40)
    
    system_check_code = """
echo "=== Quick System Check ==="
echo "Date: $(date)"
echo "Uptime: $(uptime | awk -F'up' '{print $2}' | awk -F',' '{print $1}')"
echo "Load Average: $(uptime | awk -F'load average:' '{print $2}')"
echo "Disk Usage:"
df -h / | tail -1 | awk '{print "  Root: " $5 " used"}'
echo "Memory:"
if command -v free &> /dev/null; then
    free -h | grep Mem | awk '{print "  Total: " $2 ", Used: " $3}'
else
    echo "  (memory info not available)"
fi
"""
    
    result = await tools.bring_your_own(
        tool_name="system_check",
        code=system_check_code,
        runtime="bash",
        timeout=5,
        args=None,
        persist=False,
        ctx=ctx
    )
    
    result_dict = json.loads(result)
    if result_dict.get("success"):
        print("System Check Output:")
        print(result_dict['data']['result'])


async def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("Omnispindle New Tools Demo")
    print("="*60)
    
    try:
        # Run the demos
        await demo_point_out_obvious()
        await demo_bring_your_own()
        
        print("\n" + "="*60)
        print("Demo completed successfully!")
        print("="*60)
        print("\nThese tools add creative capabilities to the MCP server:")
        print("1. point_out_obvious: Add personality and humor to AI responses")
        print("2. bring_your_own: Let AI models create custom tools dynamically")
        print("\nUse them wisely! 🚀")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 
