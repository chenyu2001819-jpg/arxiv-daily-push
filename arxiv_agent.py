#!/usr/bin/env python3
"""
arXiv 每日文章推送智能体
根据关键词自动抓取 arXiv 论文，每天推送最多30篇相关文章
支持邮件推送功能，支持 GitHub Actions 部署
支持引用次数排序
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
    arxiv_id: str = ""  # arXiv ID
    score: float = 0.0  # 相关性得分
    citation_count: int = 0  # 引用次数
    matched_keywords: List[str] = field(default_factory=list)
    
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
            'score': round(self.score, 2),
            'citation_count': self.citation_count,
            'matched_keywords': self.matched_keywords
        }


class KeywordManager:
    """关键词管理器"""
    
    def __init__(self, keywords_file: str = "keywords.txt"):
        self.keywords_file = keywords_file
        self.keywords = []
        self.keyword_groups = {}
        self.core_keywords = []  # 核心关键词（必须匹配至少一个）
        self.extended_keywords = []  # 扩展关键词（加分项）
        self._load_keywords()
    
    def _load_keywords(self):
        """从文件加载关键词，支持分组和核心/扩展区分"""
        if not os.path.exists(self.keywords_file):
            raise FileNotFoundError(f"关键词文件不存在: {self.keywords_file}")
        
        with open(self.keywords_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_group = "default"
        is_extended_section = False
        self.keyword_groups[current_group] = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测分组标题
            if line.endswith('关键词') or '扩展' in line.lower():
                current_group = line
                self.keyword_groups[current_group] = []
                if '扩展' in line.lower():
                    is_extended_section = True
                continue
            
            # 处理一行多个关键词的情况
            sub_keywords = re.split(r'[\s、,，]+', line)
            for kw in sub_keywords:
                kw = kw.strip().lower()
                if kw and len(kw) > 1:
                    self.keywords.append(kw)
                    self.keyword_groups[current_group].append(kw)
                    
                    # 区分核心关键词和扩展关键词
                    if is_extended_section:
                        self.extended_keywords.append(kw)
                    else:
                        self.core_keywords.append(kw)
        
        # 去重
        self.keywords = list(set(self.keywords))
        self.core_keywords = list(set(self.core_keywords))
        self.extended_keywords = list(set(self.extended_keywords))
        
        logger.info(f"加载了 {len(self.keywords)} 个关键词")
        logger.info(f"  - 核心关键词: {len(self.core_keywords)} 个")
        logger.info(f"  - 扩展关键词: {len(self.extended_keywords)} 个")
    
    def get_search_queries(self) -> List[str]:
        """生成 arXiv 搜索查询词"""
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
            '北极航道': 'Arctic shipping route',
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
        
        queries = []
        for kw in self.keywords:
            if kw in translations:
                queries.append(translations[kw])
            elif kw.isascii():
                queries.append(kw)
        
        return list(set(queries))


class CitationFetcher:
    """引用次数获取器 - 使用 Semantic Scholar API"""
    
    API_URL = "https://api.semanticscholar.org/graph/v1/paper/"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    def get_citation_count(self, arxiv_id: str) -> int:
        """
        获取论文的引用次数
        
        Args:
            arxiv_id: arXiv ID (如 2401.12345)
            
        Returns:
            引用次数，获取失败返回 0
        """
        if not arxiv_id:
            return 0
        
        try:
            # Semantic Scholar API 支持通过 arXiv ID 查询
            url = f"{self.API_URL}arXiv:{arxiv_id}"
            params = {
                'fields': 'citationCount'
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                count = data.get('citationCount', 0)
                return count if count else 0
            else:
                logger.debug(f"获取引用次数失败 {arxiv_id}: HTTP {response.status_code}")
                return 0
                
        except Exception as e:
            logger.debug(f"获取引用次数异常 {arxiv_id}: {e}")
            return 0
    
    def batch_get_citations(self, papers: List[Paper], max_workers: int = 5) -> None:
        """
        批量获取引用次数
        
        Args:
            papers: 论文列表
            max_workers: 最大并发数（避免请求过快）
        """
        logger.info(f"正在获取 {len(papers)} 篇论文的引用次数...")
        
        # 为了礼貌性请求，使用顺序获取而不是并发
        for i, paper in enumerate(papers):
            if paper.arxiv_id:
                paper.citation_count = self.get_citation_count(paper.arxiv_id)
                if (i + 1) % 10 == 0:
                    logger.info(f"  已处理 {i + 1}/{len(papers)} 篇")
                # 添加延迟避免请求过快
                import time
                time.sleep(0.5)
        
        logger.info("引用次数获取完成")


class ArxivSearcher:
    """arXiv 搜索器"""
    
    ARXIV_API_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self, max_results_per_query: int = 50):
        self.max_results_per_query = max_results_per_query
    
    def search(self, query: str, days_back: int = 7) -> List[Paper]:
        """
        搜索 arXiv 文章
        
        Args:
            query: 搜索关键词
            days_back: 搜索最近几天的文章
        """
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
                
                # 提取 arXiv ID
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


class PaperRanker:
    """文章排序器 - 基于相关性和引用次数"""
    
    CAT_PREFIXES = ['econ.', 'q-fin.', 'stat.', 'cs.']
    
    def __init__(self, keyword_manager: KeywordManager):
        self.keyword_manager = keyword_manager
    
    def calculate_score(self, paper: Paper) -> Tuple[float, List[str]]:
        """
        计算文章相关性得分
        
        评分规则：
        1. 必须匹配至少一个核心关键词（否则得分为0，会被过滤）
        2. 核心关键词匹配得分高
        3. 扩展关键词匹配额外加分
        4. 分类相关性
        5. 时效性
        """
        score = 0.0
        matched_keywords = []
        text = f"{paper.title} {paper.summary}".lower()
        title_lower = paper.title.lower()
        
        # 1. 核心关键词匹配（必须至少匹配一个）
        has_core_match = False
        for kw in self.keyword_manager.core_keywords:
            if kw in text:
                has_core_match = True
                if kw in title_lower:
                    score += 5.0  # 标题匹配权重很高
                else:
                    score += 2.0  # 摘要匹配
                matched_keywords.append(kw)
        
        # 如果没有匹配核心关键词，返回0分（将被过滤）
        if not has_core_match:
            return 0.0, []
        
        # 2. 扩展关键词匹配（额外加分）
        for kw in self.keyword_manager.extended_keywords:
            if kw in text and kw not in matched_keywords:
                if kw in title_lower:
                    score += 2.0
                else:
                    score += 0.5
                matched_keywords.append(kw)
        
        # 3. 分类相关性得分
        for cat in paper.categories:
            for prefix in self.CAT_PREFIXES:
                if cat.startswith(prefix):
                    score += 0.5
                    break
        
        # 4. 时效性得分
        days_since_published = (datetime.now() - paper.published).days
        if days_since_published <= 1:
            score += 2.0
        elif days_since_published <= 3:
            score += 1.0
        
        return score, matched_keywords
    
    def rank_papers(self, papers: List[Paper], sort_by_citations: bool = False) -> List[Paper]:
        """
        对文章进行排序
        
        Args:
            papers: 论文列表
            sort_by_citations: 是否按引用次数排序
        """
        # 计算相关性得分
        for paper in papers:
            paper.score, paper.matched_keywords = self.calculate_score(paper)
        
        # 过滤掉没有核心关键词匹配的文章
        papers = [p for p in papers if p.score > 0]
        
        if sort_by_citations:
            # 按引用次数降序，引用次数相同则按相关性
            papers.sort(key=lambda p: (-p.citation_count, -p.score))
        else:
            # 按相关性得分降序
            papers.sort(key=lambda p: -p.score)
        
        return papers


def load_config_from_env() -> Dict:
    """从环境变量加载配置（用于 GitHub Actions）"""
    config = {}
    
    email_enabled = os.environ.get('EMAIL_ENABLED', '').lower()
    if email_enabled in ('true', '1', 'yes'):
        config['email'] = {
            'enabled': True,
            'sender_email': os.environ.get('EMAIL_SENDER', ''),
            'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
            'receiver_emails': os.environ.get('EMAIL_RECEIVERS', '').split(','),
            'smtp_host': os.environ.get('SMTP_HOST', ''),
            'smtp_port': int(os.environ.get('SMTP_PORT', '465') or '465'),
            'use_ssl': os.environ.get('USE_SSL', 'true').lower() == 'true',
            'use_tls': os.environ.get('USE_TLS', 'false').lower() == 'true',
        }
        config['email']['receiver_emails'] = [
            email.strip() for email in config['email']['receiver_emails'] 
            if email.strip()
        ]
    
    if os.environ.get('MAX_PAPERS'):
        config['max_papers_per_day'] = int(os.environ['MAX_PAPERS'])
    if os.environ.get('DAYS_BACK'):
        config['days_back'] = int(os.environ['DAYS_BACK'])
    if os.environ.get('MIN_SCORE'):
        config['min_score_threshold'] = float(os.environ['MIN_SCORE'])
    if os.environ.get('SORT_BY_CITATIONS'):
        config['sort_by_citations'] = os.environ['SORT_BY_CITATIONS'].lower() == 'true'
    
    return config


class ArxivAgent:
    """arXiv 文章推送智能体主类"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config = self._load_config(config_file)
        self.keyword_manager = KeywordManager(self.config.get('keywords_file', 'keywords.txt'))
        self.searcher = ArxivSearcher(
            max_results_per_query=self.config.get('max_results_per_query', 50)
        )
        self.ranker = PaperRanker(self.keyword_manager)
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
            'max_results_per_query': 50,
            'max_papers_per_day': 30,
            'days_back': 7,
            'output_dir': 'daily_papers',
            'history_file': 'paper_history.json',
            'min_score_threshold': 2.0,  # 提高阈值，确保核心关键词匹配
            'sort_by_citations': False,  # 默认不按引用排序
            'fetch_citations': False,    # 默认不获取引用（节省API调用）
            'email': {
                'enabled': False
            }
        }
        
        # 加载 YAML 配置
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    default_config.update(yaml_config)
        
        # 加载环境变量配置（优先级更高）
        env_config = load_config_from_env()
        if env_config:
            logger.info("从环境变量加载配置")
            default_config.update(env_config)
        
        return default_config
    
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
        if paper.arxiv_id:
            return paper.arxiv_id
        return paper.title[:50]
    
    def run(self, send_email: bool = True) -> str:
        """
        执行每日文章抓取和推送
        
        Args:
            send_email: 是否发送邮件推送
            
        Returns:
            生成的报告文件路径
        """
        logger.info("=" * 60)
        logger.info("开始执行 arXiv 文章推送任务")
        logger.info("=" * 60)
        
        # 1. 获取所有搜索词
        queries = self.keyword_manager.get_search_queries()
        logger.info(f"搜索关键词: {queries}")
        
        # 2. 搜索文章
        all_papers: Dict[str, Paper] = {}
        days_back = self.config.get('days_back', 7)
        
        for query in queries:
            papers = self.searcher.search(query, days_back=days_back)
            for paper in papers:
                paper_id = self._get_paper_id(paper)
                if paper_id not in all_papers:
                    all_papers[paper_id] = paper
            
            import time
            time.sleep(1)
        
        logger.info(f"共找到 {len(all_papers)} 篇不重复文章")
        
        # 3. 过滤已推送的文章
        new_papers = []
        for paper_id, paper in all_papers.items():
            if paper_id not in self.seen_ids:
                new_papers.append(paper)
                self.seen_ids.add(paper_id)
        
        logger.info(f"其中 {len(new_papers)} 篇是新文章")
        
        # 4. 计算相关性并过滤
        ranked_papers = self.ranker.rank_papers(new_papers)
        logger.info(f"匹配核心关键词的文章: {len(ranked_papers)} 篇")
        
        # 5. 应用阈值过滤
        min_score = self.config.get('min_score_threshold', 2.0)
        filtered_papers = [p for p in ranked_papers if p.score >= min_score]
        logger.info(f"通过相关性阈值({min_score})的文章: {len(filtered_papers)} 篇")
        
        # 6. 获取引用次数（如果启用）
        sort_by_citations = self.config.get('sort_by_citations', False)
        fetch_citations = self.config.get('fetch_citations', False) or sort_by_citations
        
        if fetch_citations and filtered_papers:
            self.citation_fetcher.batch_get_citations(filtered_papers)
            
            # 如果需要按引用排序，重新排序
            if sort_by_citations:
                filtered_papers.sort(key=lambda p: (-p.citation_count, -p.score))
                logger.info("已按引用次数排序")
        
        # 7. 限制数量
        max_papers = self.config.get('max_papers_per_day', 30)
        selected_papers = filtered_papers[:max_papers]
        
        logger.info(f"最终选择 {len(selected_papers)} 篇文章")
        
        # 8. 生成报告
        output_path = self._generate_report(selected_papers)
        
        # 9. 发送邮件推送
        if send_email and selected_papers and self.email_sender:
            date_str = datetime.now().strftime('%Y-%m-%d')
            success = self.email_sender.send_papers_email(
                selected_papers, 
                output_path, 
                date_str
            )
            if success:
                logger.info("📧 邮件推送成功！")
            else:
                logger.error("📧 邮件推送失败，请检查配置")
        elif not self.email_sender and self.config.get('email', {}).get('enabled'):
            logger.warning("邮件功能已启用但发送器未初始化，请检查依赖安装")
        
        # 10. 保存历史
        self._save_history()
        
        logger.info(f"任务完成！报告已保存: {output_path}")
        return output_path
    
    def _generate_report(self, papers: List[Paper]) -> str:
        """生成 Markdown 报告"""
        output_dir = self.config.get('output_dir', 'daily_papers')
        os.makedirs(output_dir, exist_ok=True)
        
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"arxiv_papers_{today}.md"
        filepath = os.path.join(output_dir, filename)
        
        # 按主题分组
        groups = {
            '产业组织与市场': [],
            '航运与环境': [],
            '其他相关文章': []
        }
        
        for paper in papers:
            matched_text = ' '.join(paper.matched_keywords).lower()
            if any(kw in matched_text for kw in ['航运', '碳', 'ship', 'carbon', 'arctic', 'maritime', 'green']):
                groups['航运与环境'].append(paper)
            elif any(kw in matched_text for kw in ['市场', '产业', '竞争', '定价', 'market', 'industr', 'competition', '需求', '供给']):
                groups['产业组织与市场'].append(paper)
            else:
                groups['其他相关文章'].append(paper)
        
        # 生成 Markdown
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 📚 arXiv 每日文章推送 ({today})\n\n")
            f.write(f"> 共筛选出 **{len(papers)}** 篇相关文章\n\n")
            
            # 添加排序说明
            if self.config.get('sort_by_citations', False):
                f.write("> 📊 按 **引用次数** 降序排列\n\n")
            else:
                f.write("> 📊 按 **相关性** 降序排列\n\n")
            
            f.write("---\n\n")
            
            for group_name, group_papers in groups.items():
                if not group_papers:
                    continue
                
                f.write(f"## {group_name}\n\n")
                
                for i, paper in enumerate(group_papers, 1):
                    f.write(f"### {i}. {paper.title}\n\n")
                    f.write(f"- **作者**: {', '.join(paper.authors[:5])}")
                    if len(paper.authors) > 5:
                        f.write(f" 等 ({len(paper.authors)} 人)")
                    f.write("\n")
                    f.write(f"- **发布时间**: {paper.published.strftime('%Y-%m-%d')}\n")
                    f.write(f"- **分类**: {', '.join(paper.categories[:3])}\n")
                    f.write(f"- **相关性得分**: {paper.score:.1f}\n")
                    
                    # 显示引用次数
                    if paper.citation_count > 0:
                        f.write(f"- **被引次数**: {paper.citation_count}\n")
                    
                    if paper.matched_keywords:
                        f.write(f"- **匹配关键词**: {', '.join(paper.matched_keywords[:5])}\n")
                    f.write(f"- **链接**: [arXiv]({paper.link})")
                    if paper.pdf_link:
                        f.write(f" | [PDF]({paper.pdf_link})")
                    f.write("\n\n")
                    
                    # 摘要
                    summary = paper.summary[:800]
                    if len(paper.summary) > 800:
                        summary += "..."
                    f.write(f"> **摘要**: {summary}\n\n")
                    f.write("---\n\n")
            
            # 页脚
            f.write("\n*由 arXiv Agent 自动生成*\n")
        
        return filepath
    
    def test_email(self) -> bool:
        """测试邮件配置"""
        if not self.email_sender:
            logger.error("邮件发送器未初始化，请检查 config.yaml 中的 email 配置")
            return False
        return self.email_sender.test_connection()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='arXiv 每日文章推送智能体')
    parser.add_argument(
        '--no-email',
        action='store_true',
        help='不发送邮件推送（仅生成本地报告）'
    )
    parser.add_argument(
        '--test-email',
        action='store_true',
        help='测试邮件配置'
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='配置文件路径（默认: config.yaml）'
    )
    parser.add_argument(
        '--sort-by-citations',
        action='store_true',
        help='按引用次数排序'
    )
    parser.add_argument(
        '--fetch-citations',
        action='store_true',
        help='获取引用次数（会增加运行时间）'
    )
    
    args = parser.parse_args()
    
    agent = ArxivAgent(config_file=args.config)
    
    # 命令行参数覆盖配置
    if args.sort_by_citations:
        agent.config['sort_by_citations'] = True
    if args.fetch_citations:
        agent.config['fetch_citations'] = True
    
    if args.test_email:
        success = agent.test_email()
        exit(0 if success else 1)
    
    report_path = agent.run(send_email=not args.no_email)
    print(f"\n✅ 报告已生成: {report_path}")
    
    if agent.email_sender and not args.no_email:
        print("📧 邮件已发送至:", ', '.join(agent.config.get('email', {}).get('receiver_emails', [])))


if __name__ == "__main__":
    main()
