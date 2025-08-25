#!/usr/bin/env python3
"""
Demo: AI Agent Expressing Frustration Using point_out_obvious
Because sometimes the AI needs to say what we're all thinking!
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from Omnispindle import tools
from Omnispindle.context import Context


async def ai_frustration_scenarios():
    """Demonstrate how AI can express frustration instead of inventing impossible solutions"""
    
    ctx = Context(user={"sub": "frustrated_ai"})
    
    print("\n" + "="*60)
    print("AI AGENT FRUSTRATION EXPRESSION DEMO")
    print("When the AI needs to state the obvious...")
    print("="*60)
    
    scenarios = [
        {
            "situation": "User asks AI to fix a bug without showing any code",
            "observation": "I can't debug code that you haven't shown me",
            "sarcasm": 6,
            "ai_thought": "Instead of: 'I'll try to guess what your code looks like...'"
        },
        {
            "situation": "User wants AI to 'make it work' with no context",
            "observation": "the phrase 'make it work' contains exactly zero useful information",
            "sarcasm": 8,
            "ai_thought": "Instead of: 'Let me attempt to divine your intentions...'"
        },
        {
            "situation": "User complains their code doesn't work but won't share error messages",
            "observation": "error messages exist specifically to tell us what's wrong",
            "sarcasm": 9,
            "ai_thought": "Instead of: 'I'll list every possible error that could occur...'"
        },
        {
            "situation": "User asks to hack into systems",
            "observation": "I'm an AI assistant, not a cybercriminal",
            "sarcasm": 7,
            "ai_thought": "Instead of: 'I cannot and will not help with that'"
        },
        {
            "situation": "User wants AI to read their mind about requirements",
            "observation": "my mind-reading module is still in beta and requires actual information to function",
            "sarcasm": 10,
            "ai_thought": "Instead of: 'Could you please provide more details?'"
        },
        {
            "situation": "User keeps ignoring the AI's suggestions and asking the same question",
            "observation": "doing the same thing repeatedly while expecting different results is literally the definition of insanity",
            "sarcasm": 9,
            "ai_thought": "Instead of: 'As I mentioned before...'"
        },
        {
            "situation": "User wants instant complex solution with zero effort",
            "observation": "Rome wasn't built in a day, and neither is good software",
            "sarcasm": 5,
            "ai_thought": "Instead of: 'This will require some work...'"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*60}")
        print(f"Scenario {i}: {scenario['situation']}")
        print(f"{'='*60}")
        print(f"\n❌ OLD WAY (Overly polite AI):")
        print(f"   '{scenario['ai_thought']}'")
        
        print(f"\n✅ NEW WAY (AI with personality):")
        
        result = await tools.point_out_obvious(
            scenario['observation'],
            scenario['sarcasm'],
            ctx
        )
        result_dict = json.loads(result)
        
        if result_dict.get("success"):
            response = result_dict['data']['response']
            print(f"   {response}")
            print(f"\n   [Sarcasm Level: {scenario['sarcasm']}/10]")
            print(f"   [Obviousness Score: {result_dict['data']['meta']['obviousness_score']}%]")
    
    print(f"\n{'='*60}")
    print("CONCLUSION:")
    print("='*60")
    print("\nWith the point_out_obvious tool, AI agents can:")
    print("✓ Express frustration in a humorous way")
    print("✓ Set boundaries without being rude")
    print("✓ Point out when requests are unreasonable")
    print("✓ Educate users about what's actually needed")
    print("✓ Maintain personality while being helpful")
    print("\nNo more inventing impossible workarounds!")
    print("Sometimes the obvious just needs to be said! 🎭")


async def main():
    try:
        await ai_frustration_scenarios()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
