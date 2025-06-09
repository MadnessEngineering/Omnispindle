import asyncio
import sys
sys.path.append('src')

from Omnispindle import add_todo_tool

async def main():
    result = await add_todo_tool(
        description='Create TODO about project name normalization comments',
        project='Omnispindle',
        priority='Medium',
        metadata={
            'notes': 'Implement project name normalization, regex matching, and AI inference for project names'
        }
    )
    print(result)

if __name__ == '__main__':
    asyncio.run(main()) 
