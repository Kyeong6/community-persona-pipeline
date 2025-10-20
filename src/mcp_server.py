import asyncio
import json
import sys
from mcp.server import Server
from mcp.types import Tool, TextContent
from src.crawlers.mamibebe_crawler import MamibebeCrawler
from src.crawlers.ppomppu_crawler import PpomppuCrawler
from src.crawlers.fmkorea_crawler import FmkoreaCrawler
import os
from dotenv import load_dotenv

load_dotenv()

# MCP 서버 인스턴스 생성
server = Server("community-crawler")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="crawl_mamibebe",
            description="맘이베베 인기글 크롤링",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_posts": {"type": "integer", "default": 20, "description": "크롤링할 최대 게시글 수"}
                }
            }
        ),
        Tool(
            name="crawl_ppomppu", 
            description="뽐뿌 인기글 크롤링",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_posts": {"type": "integer", "default": 20, "description": "크롤링할 최대 게시글 수"}
                }
            }
        ),
        Tool(
            name="crawl_fmkorea",
            description="에펨코리아 인기글 크롤링", 
            inputSchema={
                "type": "object",
                "properties": {
                    "max_posts": {"type": "integer", "default": 20, "description": "크롤링할 최대 게시글 수"}
                }
            }
        ),
        Tool(
            name="crawl_all",
            description="모든 커뮤니티 인기글 크롤링",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_posts": {"type": "integer", "default": 20, "description": "각 커뮤니티별 크롤링할 최대 게시글 수"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    max_posts = arguments.get("max_posts", 20)
    
    try:
        if name == "crawl_mamibebe":
            async with MamibebeCrawler() as crawler:
                result = await crawler.crawl(max_posts)
                return [TextContent(type="text", text=json.dumps([post.dict() for post in result], ensure_ascii=False, indent=2))]
        
        elif name == "crawl_ppomppu":
            async with PpomppuCrawler() as crawler:
                result = await crawler.crawl(max_posts)
                return [TextContent(type="text", text=json.dumps([post.dict() for post in result], ensure_ascii=False, indent=2))]
        
        elif name == "crawl_fmkorea":
            async with FmkoreaCrawler() as crawler:
                result = await crawler.crawl(max_posts)
                return [TextContent(type="text", text=json.dumps([post.dict() for post in result], ensure_ascii=False, indent=2))]
        
        elif name == "crawl_all":
            all_results = {}
            
            # 맘이베베 크롤링
            try:
                async with MamibebeCrawler() as crawler:
                    mamibebe_result = await crawler.crawl(max_posts)
                    all_results["mamibebe"] = [post.dict() for post in mamibebe_result]
            except Exception as e:
                all_results["mamibebe"] = {"error": str(e)}
            
            # 뽐뿌 크롤링
            try:
                async with PpomppuCrawler() as crawler:
                    ppomppu_result = await crawler.crawl(max_posts)
                    all_results["ppomppu"] = [post.dict() for post in ppomppu_result]
            except Exception as e:
                all_results["ppomppu"] = {"error": str(e)}
            
            # 에펨코리아 크롤링
            try:
                async with FmkoreaCrawler() as crawler:
                    fmkorea_result = await crawler.crawl(max_posts)
                    all_results["fmkorea"] = [post.dict() for post in fmkorea_result]
            except Exception as e:
                all_results["fmkorea"] = {"error": str(e)}
            
            return [TextContent(type="text", text=json.dumps(all_results, ensure_ascii=False, indent=2))]
        
        else:
            return [TextContent(type="text", text="Unknown tool")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"크롤링 중 오류 발생: {str(e)}")]

async def main():
    """MCP 서버 실행"""
    print("커뮤니티 크롤링 MCP 서버를 시작합니다...")
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

def run_server():
    """Poetry 스크립트용 진입점"""
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
