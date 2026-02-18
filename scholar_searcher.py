#!/usr/bin/env python3
"""
多源学术搜索器
支持 Semantic Scholar、OpenAlex 等学术搜索引擎
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """统一的论文数据结构"""
    title: str
    authors: List[str]
    summary: str
    link: str
    pdf_link: str = ""
    published: datetime = None
    categories: List[str] = field(default_factory=list)
    primary_category: str = ""
    external_id: str = ""  # 各平台的 ID
    citation_count: int = 0
    source: str = ""  # 来源平台
    matched_keywords: List[str] = field(default_factory=list)


class SemanticScholarSearcher:
    """Semantic Scholar 搜索器
    
    优势：
    - 免费 API，无需 API Key（有 Key 可提高限制）
    - 支持相关性排序
    - 包含 citation count
    - 支持多字段搜索
    - Rate limit: 100 requests/5 minutes (无 Key), 1,000/5min (有 Key)
    """
    
    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'x-api-key': api_key})
    
    def search(self, query: str, days_back: int = 7, max_results: int = 50) -> List[Paper]:
        """
        搜索 Semantic Scholar
        
        Args:
            query: 搜索关键词
            days_back: 搜索最近几天的文章
            max_results: 最大结果数
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Semantic Scholar 支持 publicationDateOrYear 过滤
        params = {
            'query': query,
            'fields': 'title,authors,year,abstract,citationCount,externalIds,url,openAccessPdf',
            'limit': min(max_results, 100),  # 最大 100
            'sort': 'relevance',  # relevance 或 citationCount
        }
        
        try:
            logger.info(f"搜索 Semantic Scholar: {query}")
            response = self.session.get(self.API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for item in data.get('data', []):
                # 检查日期（Semantic Scholar 的日期精度是年，需要进一步过滤）
                year = item.get('year', 0)
                if year < start_date.year:
                    continue
                
                # 获取 PDF 链接
                pdf_link = ""
                oa = item.get('openAccessPdf')
                if oa and isinstance(oa, dict):
                    pdf_link = oa.get('url', '')
                
                # 获取作者
                authors = []
                for author in item.get('authors', []):
                    if isinstance(author, dict):
                        authors.append(author.get('name', ''))
                    else:
                        authors.append(str(author))
                
                # 获取外部 ID
                external_ids = item.get('externalIds', {})
                paper_id = external_ids.get('ArXiv', '') or external_ids.get('DOI', '') or item.get('paperId', '')
                
                paper = Paper(
                    title=item.get('title', ''),
                    authors=authors,
                    summary=item.get('abstract', ''),
                    link=item.get('url', ''),
                    pdf_link=pdf_link,
                    published=datetime(year, 1, 1) if year else datetime.now(),
                    external_id=paper_id,
                    citation_count=item.get('citationCount', 0),
                    source='semantic_scholar'
                )
                papers.append(paper)
            
            logger.info(f"  找到 {len(papers)} 篇文章")
            return papers
            
        except Exception as e:
            logger.error(f"Semantic Scholar 搜索失败: {e}")
            return []


class OpenAlexSearcher:
    """OpenAlex 搜索器
    
    优势：
    - 完全免费开源
    - 无 Rate Limit（请礼貌使用）
    - 数据覆盖广（包括 arXiv、DOI 等）
    - 支持复杂查询语法
    - 包含 citation count
    """
    
    API_URL = "https://api.openalex.org/works"
    
    def __init__(self, email: Optional[str] = None):
        """
        Args:
            email: 你的邮箱（OpenAlex 建议提供，会被添加到 User-Agent）
        """
        self.email = email
        self.session = requests.Session()
        if email:
            self.session.headers.update({
                'User-Agent': f'mailto:{email}'
            })
    
    def search(self, query: str, days_back: int = 7, max_results: int = 50) -> List[Paper]:
        """
        搜索 OpenAlex
        
        Args:
            query: 搜索关键词
            days_back: 搜索最近几天的文章
            max_results: 最大结果数
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # OpenAlex 使用 filter 语法
        # from_publication_date 格式: YYYY-MM-DD
        from_date = start_date.strftime('%Y-%m-%d')
        
        params = {
            'search': query,
            'filter': f'from_publication_date:{from_date}',
            'sort': 'relevance_score:desc',
            'per-page': min(max_results, 200),  # 最大 200
        }
        
        try:
            logger.info(f"搜索 OpenAlex: {query}")
            response = self.session.get(self.API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for item in data.get('results', []):
                # 获取日期
                pub_date = item.get('publication_date', '')
                if pub_date:
                    try:
                        published = datetime.strptime(pub_date, '%Y-%m-%d')
                    except:
                        published = datetime.now()
                else:
                    published = datetime.now()
                
                # 获取作者
                authors = []
                for authorship in item.get('authorships', []):
                    author = authorship.get('author', {})
                    if isinstance(author, dict):
                        authors.append(author.get('display_name', ''))
                
                # 获取 PDF 链接
                pdf_link = ""
                oa_info = item.get('open_access', {})
                if oa_info and oa_info.get('is_oa'):
                    pdf_link = oa_info.get('oa_url', '')
                
                # 获取引用次数
                cited_by_count = item.get('cited_by_count', 0)
                
                # 获取概念/分类
                concepts = [c.get('display_name', '') for c in item.get('concepts', [])]
                
                paper = Paper(
                    title=item.get('display_name', ''),
                    authors=authors,
                    summary=item.get('abstract', '') or '',
                    link=item.get('id', ''),
                    pdf_link=pdf_link,
                    published=published,
                    categories=concepts[:5],  # 前5个概念
                    external_id=item.get('id', '').split('/')[-1],
                    citation_count=cited_by_count,
                    source='openalex'
                )
                papers.append(paper)
            
            logger.info(f"  找到 {len(papers)} 篇文章")
            return papers
            
        except Exception as e:
            logger.error(f"OpenAlex 搜索失败: {e}")
            return []


class MultiSourceSearcher:
    """多源搜索器 - 整合多个学术搜索引擎"""
    
    def __init__(self, 
                 semantic_scholar_key: Optional[str] = None,
                 openalex_email: Optional[str] = None):
        self.searchers = {}
        
        # 初始化 Semantic Scholar
        self.searchers['semantic_scholar'] = SemanticScholarSearcher(semantic_scholar_key)
        
        # 初始化 OpenAlex
        self.searchers['openalex'] = OpenAlexSearcher(openalex_email)
    
    def search_all(self, query: str, days_back: int = 7, max_per_source: int = 50) -> Dict[str, List[Paper]]:
        """
        在所有源中搜索
        
        Returns:
            Dict[source_name, papers]
        """
        results = {}
        
        for name, searcher in self.searchers.items():
            try:
                papers = searcher.search(query, days_back, max_per_source)
                results[name] = papers
            except Exception as e:
                logger.error(f"{name} 搜索失败: {e}")
                results[name] = []
        
        return results
    
    def search_and_merge(self, query: str, days_back: int = 7, max_per_source: int = 50) -> List[Paper]:
        """
        在所有源中搜索并合并结果，去重
        """
        all_results = self.search_all(query, days_back, max_per_source)
        
        # 合并所有结果
        seen_ids = set()
        merged_papers = []
        
        for source, papers in all_results.items():
            for paper in papers:
                # 使用标题前50字符作为去重键
                paper_key = paper.title[:50].lower()
                if paper_key not in seen_ids:
                    seen_ids.add(paper_key)
                    merged_papers.append(paper)
        
        logger.info(f"多源搜索完成，共找到 {len(merged_papers)} 篇不重复文章")
        return merged_papers


if __name__ == "__main__":
    # 测试代码
    import time
    
    print("测试多源学术搜索器...")
    
    # 创建搜索器
    searcher = MultiSourceSearcher(
        semantic_scholar_key=None,  # 可以不提供 API Key
        openalex_email="your@email.com"  # 建议提供邮箱
    )
    
    # 测试搜索
    query = "market structure industrial organization"
    
    print(f"\n搜索: {query}")
    results = searcher.search_all(query, days_back=30, max_per_source=10)
    
    for source, papers in results.items():
        print(f"\n{source}: {len(papers)} 篇")
        for i, paper in enumerate(papers[:3], 1):
            print(f"  {i}. {paper.title[:60]}... (引用: {paper.citation_count})")
    
    # 测试合并
    print("\n\n合并结果:")
    merged = searcher.search_and_merge(query, days_back=30, max_per_source=10)
    print(f"共 {len(merged)} 篇不重复文章")
