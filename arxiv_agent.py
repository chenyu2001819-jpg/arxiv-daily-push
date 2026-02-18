#!/usr/bin/env python3
"""
arXiv 每日文章推送智能体
分块筛选策略：
- 两大主题（产业组织、航运环境）
- 每主题分核心关键词（引用前N篇）和扩展关键词（引用前M篇）
- 数量可配置
"""

import os
import re
import yaml
import json
import logging
import feedparser
import requests
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

# 导入邮件发送模块
try:
    from email_sender import EmailSender
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """论文数据结构"""
    title: str
    authors: List[str]
    summary: str
    link: str
    pdf_link: str
    published: datetime
    categories: List[str]
    primary_category: str
    arxiv_id: str = ""
    citation_count: int = 0
    matched_keywords: List[str] = field(default_factory=list)
    source_block: str = ""  # 来源主题块
    keyword_type: str = ""  # core 或 extended
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'authors': self.authors,
            'summary': self.summary[:500] + '...' if len(self.summary) > 500 else self.summary,
            'link': self.link,
            'pdf_link': self.pdf_link,
            'published': self.published.strftime('%Y-%m-%d'),
            'categories': self.categories,
            'primary_category': self.primary_category,
            'arxiv_id': self.arxiv_id,
            'citation_count': self.citation_count,
            'matched_keywords': self.matched_keywords,
            'source_block': self.source_block,
            'keyword_type': self.keyword_type
        }


class KeywordBlock:
    """关键词块 - 代表一个主题领域"""
    
    def __init__(self, name: str, core_keywords: List[str], extended_keywords: List[str]):
        self.name = name
        self.core_keywords = core_keywords
        self.extended_keywords = extended_keywords
        self.all_keywords = core_keywords + extended_keywords
        
        # 生成搜索查询
        self.search_queries = self._generate_queries()
    
    def _generate_queries(self) -> List[str]:
        """生成英文搜索查询"""
        translations = {
            # 产业组织
            '空调市场': 'air conditioner market',
            '电动汽车市场': 'electric vehicle market',
            '电车市场': 'EV market',
            '耐用消费品': 'durable goods',
            '实证产业组织': 'empirical industrial organization',
            '实证 io': 'empirical IO',
            '实证产业组织学': 'empirical industrial organization',
            '市场结构': 'market structure',
            '产品差异化': 'product differentiation',
            '需求估计': 'demand estimation',
            '需求估计模型': 'demand estimation',
            '供给行为': 'supply behavior',
            '定价策略': 'pricing strategy',
            '市场势力': 'market power',
            '福利分析': 'welfare analysis',
            '家电市场': 'appliance market',
            '家用电器市场': 'home appliance market',
            '新能源汽车市场': 'new energy vehicle market',
            '离散选择模型': 'discrete choice model',
            'blp 模型': 'BLP model',
            'blp': 'BLP',
            '结构估计': 'structural estimation',
            '结构式估计': 'structural estimation',
            '寡头竞争': 'oligopoly competition',
            '寡头垄断': 'oligopoly',
            '纵向关系': 'vertical relationship',
            '技术创新': 'technological innovation',
            '技术变革': 'technological change',
            '政策评估': 'policy evaluation',
            '政策评价': 'policy evaluation',
            '消费行为': 'consumer behavior',
            '消费者行为': 'consumer behavior',
            # 航运相关
            '北极航道': 'Arctic shipping',
            '北极航线': 'Arctic shipping route',
            '北极航运': 'Arctic shipping',
            '全球航运贸易': 'global shipping trade',
            '全球海运贸易': 'global maritime trade',
            '海运碳排放': 'maritime carbon emission',
            '海洋碳排放': 'maritime carbon emission',
            '航运减排': 'shipping emission reduction',
            '船舶碳排放': 'vessel carbon emission',
            '船舶排放': 'vessel emission',
            '碳减排政策': 'carbon reduction policy',
            '碳排放政策': 'carbon emission policy',
            '航运碳足迹': 'shipping carbon footprint',
            '绿色航运': 'green shipping',
            '气候影响': 'climate impact',
            '气候变化影响': 'climate impact',
            '国际海运': 'international shipping',
            '国际航运': 'international shipping',
            '海运贸易格局': 'maritime trade pattern',
            '航运贸易': 'shipping trade',
            '碳税': 'carbon tax',
            '碳市场': 'carbon market',
            '碳交易市场': 'carbon market',
            '船舶能效': 'ship energy efficiency',
            '船舶能源效率': 'ship energy efficiency',
            '低碳航运': 'low carbon shipping',
            '低碳海运': 'low carbon shipping',
            '北极环境影响': 'Arctic environmental impact',
            '贸易路线优化': 'trade route optimization',
            '航线优化': 'route optimization',
            '可持续航运': 'sustainable shipping',
            '可持续海运': 'sustainable maritime',
        }
        
        queries = set()
        for kw in self.all_keywords:
            kw_lower = kw.lower()
            if kw_lower.isascii():
                queries.add(kw_lower)
            elif kw in translations:
                queries.add(translations[kw])
        
        return list(queries) if queries else ['industrial organization', 'market structure']


class KeywordManager:
    """关键词管理器 - 管理多个主题块"""
    
    def __init__(self, keywords_file: str = "keywords.txt"):
        self.keywords_file = keywords_file
        self.blocks: List[KeywordBlock] = []
        self._load_keywords()
    
    def _load_keywords(self):
        """从文件加载关键词，分成多个块"""
        if not os.path.exists(self.keywords_file):
            raise FileNotFoundError(f"关键词文件不存在: {self.keywords_file}")
        
        with open(self.keywords_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分割成块（用空行分隔）
        raw_blocks = re.split(r'\n\s*\n', content.strip())
        
        for raw_block in raw_blocks:
            lines = [line.strip() for line in raw_block.strip().split('\n') if line.strip()]
            if not lines:
                continue
            
            # 第一行是块名称（如果不是关键词行）
            block_name = lines[0]
            if '关键词' in block_name or '扩展' in block_name:
                block_name = f"主题块{len(self.blocks) + 1}"
                keyword_lines = lines
            else:
                keyword_lines = lines[1:]
            
            # 分离核心关键词和扩展关键词
            core_keywords = []
            extended_keywords = []
            is_extended = False
            
            for line in keyword_lines:
                if '关键词' in line.lower() or line.endswith('关键词'):
                    continue
                if '扩展' in line.lower():
                    is_extended = True
                    continue
                
                # 分割一行中的多个关键词
                sub_keywords = re.split(r'[\s、,，]+', line)
                for kw in sub_keywords:
                    kw = kw.strip().lower()
                    if kw and len(kw) > 1:
                        if is_extended:
                            extended_keywords.append(kw)
                        else:
                            core_keywords.append(kw)
            
            if core_keywords or extended_keywords:
                block = KeywordBlock(block_name, core_keywords, extended_keywords)
                self.blocks.append(block)
                logger.info(f"加载主题块 '{block_name}': {len(core_keywords)} 核心, {len(extended_keywords)} 扩展")
                logger.info(f"  搜索查询: {block.search_queries}")
        
        if not self.blocks:
            # 默认创建两个块
            logger.warning("未找到关键词块，创建默认块")
            self.blocks = [
                KeywordBlock("产业组织", ['market structure', 'industrial organization'], ['pricing']),
                KeywordBlock("航运环境", ['shipping', 'carbon emission'], ['maritime'])
            ]


class CitationFetcher:
    """引用次数获取器"""
    
    API_URL = "https://api.semanticscholar.org/graph/v1/paper/"
    
    def get_citation_count(self, arxiv_id: str) -> int:
        """获取论文的引用次数"""
        if not arxiv_id:
            return 0
        
        try:
            url = f"{self.API_URL}arXiv:{arxiv_id}"
            params = {'fields': 'citationCount'}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('citationCount', 0) or 0
            return 0
                
        except Exception:
            return 0
    
    def batch_get_citations(self, papers: List[Paper]) -> None:
        """批量获取引用次数"""
        logger.info(f"正在获取 {len(papers)} 篇论文的引用次数...")
        
        for i, paper in enumerate(papers):
            if paper.arxiv_id:
                paper.citation_count = self.get_citation_count(paper.arxiv_id)
                if (i + 1) % 10 == 0:
                    logger.info(f"  已处理 {i + 1}/{len(papers)} 篇")
                import time
                time.sleep(0.3)
        
        logger.info("引用次数获取完成")


class ArxivSearcher:
    """arXiv 搜索器"""
    
    ARXIV_API_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self, max_results_per_query: int = 100):
        self.max_results_per_query = max_results_per_query
    
    def search(self, query: str, days_back: int = 30) -> List[Paper]:
        """搜索 arXiv 文章"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'search_query': f'all:{query}',
            'start': 0,
            'max_results': self.max_results_per_query,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        try:
            logger.info(f"搜索 arXiv: {query}")
            response = requests.get(
                self.ARXIV_API_URL, 
                params=params, 
                timeout=30
            )
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            papers = []
            
            for entry in feed.entries:
                published = datetime.strptime(
                    entry.published, 
                    '%Y-%m-%dT%H:%M:%SZ'
                )
                
                if published < start_date:
                    continue
                
                pdf_link = ""
                for link in entry.links:
                    if link.get('type') == 'application/pdf':
                        pdf_link = link.href
                        break
                
                authors = [author.name for author in entry.get('authors', [])]
                categories = [tag.term for tag in entry.get('tags', [])]
                primary_cat = entry.get('arxiv_primary_category', {}).get('term', '')
                
                arxiv_id = ""
                if '/abs/' in entry.link:
                    arxiv_id = entry.link.split('/abs/')[-1].split('v')[0]
                
                paper = Paper(
                    title=entry.title.replace('\n', ' ').strip(),
                    authors=authors,
                    summary=entry.summary.replace('\n', ' ').strip(),
                    link=entry.link,
                    pdf_link=pdf_link,
                    published=published,
                    categories=categories,
                    primary_category=primary_cat,
                    arxiv_id=arxiv_id
                )
                papers.append(paper)
            
            logger.info(f"  找到 {len(papers)} 篇文章")
            return papers
            
        except Exception as e:
            logger.error(f"搜索失败 '{query}': {e}")
            return []


class ArxivAgent:
    """arXiv 文章推送智能体主类"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config = self._load_config(config_file)
        self.keyword_manager = KeywordManager(self.config.get('keywords_file', 'keywords.txt'))
        self.searcher = ArxivSearcher(
            max_results_per_query=self.config.get('max_results_per_query', 100)
        )
        self.citation_fetcher = CitationFetcher()
        
        # 邮件发送器
        self.email_sender: Optional[EmailSender] = None
        if EMAIL_AVAILABLE and self.config.get('email', {}).get('enabled', False):
            try:
                self.email_sender = EmailSender(self.config['email'])
                logger.info("✅ 邮件发送功能已启用")
            except Exception as e:
                logger.error(f"邮件发送器初始化失败: {e}")
        
        # 去重存储
        self.seen_ids: Set[str] = set()
        self.history_file = self.config.get('history_file', 'paper_history.json')
        self._load_history()
    
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        default_config = {
            'keywords_file': 'keywords.txt',
            'max_results_per_query': 100,
            'days_back': 30,  # 搜索最近30天的文章
            'output_dir': 'daily_papers',
            'history_file': 'paper_history.json',
            'email': {'enabled': False},
            # 分块筛选配置
            'block_config': {
                'core_limit': 30,      # 每块核心关键词取前30篇
                'extended_limit': 10,  # 每块扩展关键词取前10篇
            }
        }
        
        # 加载 YAML 配置
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    default_config.update(yaml_config)
        
        # 加载环境变量配置
        env_config = self._load_config_from_env()
        if env_config:
            default_config.update(env_config)
        
        return default_config
    
    def _load_config_from_env(self) -> Dict:
        """从环境变量加载配置"""
        config = {}
        
        email_enabled = os.environ.get('EMAIL_ENABLED', '').lower()
        if email_enabled in ('true', '1', 'yes'):
            config['email'] = {
                'enabled': True,
                'sender_email': os.environ.get('EMAIL_SENDER', ''),
                'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
                'receiver_emails': [
                    e.strip() for e in os.environ.get('EMAIL_RECEIVERS', '').split(',')
                    if e.strip()
                ],
            }
        
        if os.environ.get('DAYS_BACK'):
            config['days_back'] = int(os.environ['DAYS_BACK'])
        
        # 分块配置
        block_config = {}
        if os.environ.get('CORE_LIMIT'):
            block_config['core_limit'] = int(os.environ['CORE_LIMIT'])
        if os.environ.get('EXTENDED_LIMIT'):
            block_config['extended_limit'] = int(os.environ['EXTENDED_LIMIT'])
        if block_config:
            config['block_config'] = block_config
        
        return config
    
    def _load_history(self):
        """加载已推送文章历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    self.seen_ids = set(history.get('paper_ids', []))
                    logger.info(f"加载历史记录: {len(self.seen_ids)} 篇文章")
            except Exception as e:
                logger.warning(f"加载历史记录失败: {e}")
    
    def _save_history(self):
        """保存已推送文章历史"""
        history = {
            'paper_ids': list(self.seen_ids),
            'last_update': datetime.now().isoformat()
        }
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def _get_paper_id(self, paper: Paper) -> str:
        """生成文章唯一ID"""
        return paper.arxiv_id if paper.arxiv_id else paper.title[:50]
    
    def _keyword_match_score(self, text: str, keywords: List[str]) -> float:
        """计算文本与关键词的匹配分数"""
        text_lower = text.lower()
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in text_lower:
                # 标题匹配权重更高
                score += 2 if text_lower.startswith(kw_lower) else 1
        return score
    
    def run(self, send_email: bool = True) -> str:
        """执行每日文章抓取和推送"""
        logger.info("=" * 60)
        logger.info("开始执行 arXiv 文章推送任务")
        logger.info("=" * 60)
        
        block_config = self.config.get('block_config', {})
        core_limit = block_config.get('core_limit', 30)
        extended_limit = block_config.get('extended_limit', 10)
        days_back = self.config.get('days_back', 30)
        
        logger.info(f"配置：核心关键词前{core_limit}篇，扩展关键词前{extended_limit}篇")
        
        all_selected_papers: List[Paper] = []
        
        # 对每个主题块进行处理
        for block in self.keyword_manager.blocks:
            logger.info(f"\n处理主题块: {block.name}")
            logger.info(f"  核心关键词: {block.core_keywords}")
            logger.info(f"  扩展关键词: {block.extended_keywords}")
            
            block_papers: List[Paper] = []
            
            # 搜索该主题的所有关键词
            for query in block.search_queries:
                papers = self.searcher.search(query, days_back=days_back)
                for paper in papers:
                    paper_id = self._get_paper_id(paper)
                    if paper_id not in self.seen_ids:
                        paper.source_block = block.name
                        block_papers.append(paper)
                        self.seen_ids.add(paper_id)
                import time
                time.sleep(1)
            
            logger.info(f"  找到 {len(block_papers)} 篇新文章")
            
            if not block_papers:
                continue
            
            # 获取引用次数
            self.citation_fetcher.batch_get_citations(block_papers)
            
            # 按引用次数排序
            block_papers.sort(key=lambda p: -p.citation_count)
            
            # 分类：核心关键词匹配 vs 扩展关键词匹配
            core_papers = []
            extended_papers = []
            
            for paper in block_papers:
                title_summary = paper.title + " " + paper.summary
                
                # 检查是否匹配核心关键词
                core_score = self._keyword_match_score(title_summary, block.core_keywords)
                if core_score > 0:
                    paper.matched_keywords = [kw for kw in block.core_keywords 
                                              if kw.lower() in title_summary.lower()]
                    paper.keyword_type = "core"
                    core_papers.append(paper)
                    continue
                
                # 检查是否匹配扩展关键词
                ext_score = self._keyword_match_score(title_summary, block.extended_keywords)
                if ext_score > 0:
                    paper.matched_keywords = [kw for kw in block.extended_keywords 
                                              if kw.lower() in title_summary.lower()]
                    paper.keyword_type = "extended"
                    extended_papers.append(paper)
            
            logger.info(f"  核心关键词匹配: {len(core_papers)} 篇")
            logger.info(f"  扩展关键词匹配: {len(extended_papers)} 篇")
            
            # 选取前N篇
            selected_core = core_papers[:core_limit]
            selected_extended = extended_papers[:extended_limit]
            
            logger.info(f"  选取核心文章: {len(selected_core)} 篇")
            logger.info(f"  选取扩展文章: {len(selected_extended)} 篇")
            
            # 合并该主题的文章
            block_selected = selected_core + selected_extended
            all_selected_papers.extend(block_selected)
        
        logger.info(f"\n总共选取 {len(all_selected_papers)} 篇文章")
        
        if not all_selected_papers:
            logger.warning("没有找到任何文章")
            return ""
        
        # 按主题和引用次数排序
        all_selected_papers.sort(key=lambda p: (p.source_block, -p.citation_count))
        
        # 打印选中的文章
        for i, paper in enumerate(all_selected_papers, 1):
            logger.info(f"  {i}. [{paper.source_block}/{paper.keyword_type}] "
                       f"{paper.title[:50]}... (引用: {paper.citation_count})")
        
        # 生成报告
        output_path = self._generate_report(all_selected_papers)
        
        # 发送邮件
        if send_email and all_selected_papers and self.email_sender:
            date_str = datetime.now().strftime('%Y-%m-%d')
            success = self.email_sender.send_papers_email(
                all_selected_papers, output_path, date_str
            )
            if success:
                logger.info("📧 邮件推送成功！")
            else:
                logger.error("📧 邮件推送失败")
        
        # 保存历史
        self._save_history()
        
        if output_path:
            logger.info(f"任务完成！报告已保存: {output_path}")
        return output_path
    
    def _generate_report(self, papers: List[Paper]) -> str:
        """生成 Markdown 报告"""
        if not papers:
            return ""
        
        output_dir = self.config.get('output_dir', 'daily_papers')
        os.makedirs(output_dir, exist_ok=True)
        
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"arxiv_papers_{today}.md"
        filepath = os.path.join(output_dir, filename)
        
        # 按主题块分组
        block_groups = defaultdict(list)
        for paper in papers:
            block_groups[paper.source_block].append(paper)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 📚 arXiv 每日文章推送 ({today})\n\n")
            f.write(f"> 共筛选出 **{len(papers)}** 篇相关文章\n\n")
            f.write("> 📊 按 **引用次数** 降序排列\n\n")
            f.write("---\n\n")
            
            # 汇总统计
            f.write("## 📊 统计概览\n\n")
            for block_name, block_papers in block_groups.items():
                core_count = sum(1 for p in block_papers if p.keyword_type == 'core')
                ext_count = sum(1 for p in block_papers if p.keyword_type == 'extended')
                f.write(f"- **{block_name}**: {len(block_papers)} 篇")
                f.write(f" (核心: {core_count}, 扩展: {ext_count})\n")
            f.write("\n---\n\n")
            
            # 详细列表
            for block_name, block_papers in block_groups.items():
                f.write(f"## {block_name}\n\n")
                
                # 再按核心/扩展分组
                core_papers = [p for p in block_papers if p.keyword_type == 'core']
                ext_papers = [p for p in block_papers if p.keyword_type == 'extended']
                
                if core_papers:
                    f.write(f"### 核心关键词匹配 ({len(core_papers)}篇)\n\n")
                    self._write_paper_list(f, core_papers)
                
                if ext_papers:
                    f.write(f"### 扩展关键词匹配 ({len(ext_papers)}篇)\n\n")
                    self._write_paper_list(f, ext_papers)
            
            f.write("\n*由 arXiv Agent 自动生成*\n")
        
        return filepath
    
    def _write_paper_list(self, f, papers: List[Paper]):
        """写入论文列表"""
        for i, paper in enumerate(papers, 1):
            f.write(f"#### {i}. {paper.title}\n\n")
            f.write(f"- **作者**: {', '.join(paper.authors[:5])}")
            if len(paper.authors) > 5:
                f.write(f" 等 ({len(paper.authors)} 人)")
            f.write("\n")
            f.write(f"- **发布时间**: {paper.published.strftime('%Y-%m-%d')}\n")
            f.write(f"- **分类**: {paper.primary_category}\n")
            f.write(f"- **被引次数**: {paper.citation_count}\n")
            if paper.matched_keywords:
                f.write(f"- **匹配关键词**: {', '.join(paper.matched_keywords[:5])}\n")
            f.write(f"- **链接**: [arXiv]({paper.link})")
            if paper.pdf_link:
                f.write(f" | [PDF]({paper.pdf_link})")
            f.write("\n\n")
            
            summary = paper.summary[:600]
            if len(paper.summary) > 600:
                summary += "..."
            f.write(f"> **摘要**: {summary}\n\n")
            f.write("---\n\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='arXiv 每日文章推送智能体')
    parser.add_argument('--no-email', action='store_true', help='不发送邮件')
    parser.add_argument('--test-email', action='store_true', help='测试邮件配置')
    parser.add_argument('--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--core-limit', type=int, default=30, help='核心关键词选取数量')
    parser.add_argument('--extended-limit', type=int, default=10, help='扩展关键词选取数量')
    
    args = parser.parse_args()
    
    agent = ArxivAgent(config_file=args.config)
    
    # 命令行参数覆盖配置
    if args.core_limit:
        agent.config.setdefault('block_config', {})['core_limit'] = args.core_limit
    if args.extended_limit:
        agent.config.setdefault('block_config', {})['extended_limit'] = args.extended_limit
    
    report_path = agent.run(send_email=not args.no_email)
    
    if report_path:
        print(f"\n✅ 报告已生成: {report_path}")
    else:
        print("\n⚠️ 未生成报告")


if __name__ == "__main__":
    main()
