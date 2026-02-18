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
        self.core_keywords = []  # 核心关键词
        self.extended_keywords = []  # 扩展关键词
        self.search_queries = []  # 搜索查询词
        self._load_keywords()
    
    def _load_keywords(self):
        """从文件加载关键词"""
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
            if '关键词' in line or '扩展' in line.lower():
                current_group = line
                self.keyword_groups[current_group] = []
                if '扩展' in line.lower():
                    is_extended_section = True
                continue
            
            # 处理一行多个关键词的情况
            sub_keywords = re.split(r'[\s、,，]+', line)
            for kw in sub_keywords:
                kw = kw.strip()
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
        
        # 生成搜索查询
        self._generate_search_queries()
        
        logger.info(f"加载了 {len(self.keywords)} 个关键词")
        logger.info(f"  - 核心关键词: {len(self.core_keywords)} 个")
        logger.info(f"  - 扩展关键词: {len(self.extended_keywords)} 个")
        logger.info(f"  - 搜索查询: {len(self.search_queries)} 个")
    
    def _generate_search_queries(self):
        """生成 arXiv 搜索查询词"""
        # 关键词翻译映射
        translations = {
            # 产业组织
            '空调市场': 'air conditioner market',
            'air conditioner market': 'air conditioner market',
            '电动汽车市场': 'electric vehicle market',
            '电车市场': 'EV market',
            '耐用消费品': 'durable goods',
            '实证产业组织': 'empirical industrial organization',
            '实证 io': 'empirical IO',
            '市场结构': 'market structure',
            '产品差异化': 'product differentiation',
            '需求估计': 'demand estimation',
            '供给行为': 'supply behavior',
            '定价策略': 'pricing strategy',
            '市场势力': 'market power',
            '福利分析': 'welfare analysis',
            '家电市场': 'appliance market',
            '新能源汽车市场': 'new energy vehicle market',
            '离散选择模型': 'discrete choice model',
            'blp 模型': 'BLP model',
            '结构估计': 'structural estimation',
            '寡头竞争': 'oligopoly competition',
            '纵向关系': 'vertical relationship',
            '技术创新': 'technological innovation',
            '政策评估': 'policy evaluation',
            '消费行为': 'consumer behavior',
            # 航运相关
            '北极航道': 'Arctic shipping',
            '北极航运': 'Arctic shipping',
            '全球航运贸易': 'global shipping trade',
            '海运碳排放': 'maritime carbon emission',
            '航运减排': 'shipping emission reduction',
            '船舶碳排放': 'vessel carbon emission',
            '碳减排政策': 'carbon reduction policy',
            '航运碳足迹': 'shipping carbon footprint',
            '绿色航运': 'green shipping',
            '气候影响': 'climate impact',
            '国际海运': 'international shipping',
            '海运贸易格局': 'maritime trade pattern',
            '碳税': 'carbon tax',
            '碳市场': 'carbon market',
            '船舶能效': 'ship energy efficiency',
            '低碳航运': 'low carbon shipping',
            '北极环境影响': 'Arctic environmental impact',
            '贸易路线优化': 'trade route optimization',
            '可持续航运': 'sustainable shipping',
        }
        
        queries = set()
        all_keywords = self.core_keywords + self.extended_keywords
        
        for kw in all_keywords:
            kw_lower = kw.lower()
            # 直接使用英文关键词
            if kw_lower.isascii():
                queries.add(kw_lower)
            # 使用翻译后的英文
            elif kw in translations:
                queries.add(translations[kw])
        
        self.search_queries = list(queries)
        
        # 如果没有有效的搜索词，使用默认搜索
        if not self.search_queries:
            logger.warning("没有找到有效的英文搜索词，使用默认搜索")
            self.search_queries = [
                'industrial organization',
                'market structure',
                'shipping',
                'carbon emission'
            ]
    
    def get_search_queries(self) -> List[str]:
        """获取搜索查询词"""
        return self.search_queries
    
    def calculate_match_score(self, title: str, summary: str) -> Tuple[float, List[str]]:
        """
        计算文章与关键词的匹配得分
        
        返回: (得分, 匹配的关键词列表)
        """
        text = (title + " " + summary).lower()
        title_lower = title.lower()
        score = 0.0
        matched = []
        
        # 核心关键词匹配（权重更高）
        for kw in self.core_keywords:
            kw_lower = kw.lower()
            # 检查英文形式
            if kw_lower in text:
                matched.append(kw)
                if kw_lower in title_lower:
                    score += 5.0
                else:
                    score += 2.0
            # 检查是否为英文单词（更宽松的匹配）
            elif kw_lower.replace(' ', '') in text.replace(' ', ''):
                matched.append(kw)
                score += 1.0
        
        # 扩展关键词匹配
        for kw in self.extended_keywords:
            kw_lower = kw.lower()
            if kw_lower in text and kw not in matched:
                matched.append(kw)
                if kw_lower in title_lower:
                    score += 2.0
                else:
                    score += 0.5
        
        return score, matched


class CitationFetcher:
    """引用次数获取器 - 使用 Semantic Scholar API"""
    
    API_URL = "https://api.semanticscholar.org/graph/v1/paper/"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    def get_citation_count(self, arxiv_id: str) -> int:
        """获取论文的引用次数"""
        if not arxiv_id:
            return 0
        
        try:
            url = f"{self.API_URL}arXiv:{arxiv_id}"
            params = {'fields': 'citationCount'}
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                count = data.get('citationCount', 0)
                return count if count else 0
            else:
                return 0
                
        except Exception as e:
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
                time.sleep(0.5)
        
        logger.info("引用次数获取完成")


class ArxivSearcher:
    """arXiv 搜索器"""
    
    ARXIV_API_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self, max_results_per_query: int = 50):
        self.max_results_per_query = max_results_per_query
    
    def search(self, query: str, days_back: int = 7) -> List[Paper]:
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
    """文章排序器"""
    
    CAT_PREFIXES = ['econ.', 'q-fin.', 'stat.', 'cs.']
    
    def __init__(self, keyword_manager: KeywordManager):
        self.keyword_manager = keyword_manager
    
    def rank_papers(self, papers: List[Paper], sort_by_citations: bool = False) -> List[Paper]:
        """
        对文章进行排序
        
        Args:
            papers: 论文列表
            sort_by_citations: 是否按引用次数排序
        """
        # 计算相关性得分
        for paper in papers:
            score, matched = self.keyword_manager.calculate_match_score(
                paper.title, paper.summary
            )
            paper.score = score
            paper.matched_keywords = matched
            
            # 分类相关性加分
            for cat in paper.categories:
                for prefix in self.CAT_PREFIXES:
                    if cat.startswith(prefix):
                        paper.score += 0.5
                        break
            
            # 时效性加分
            days_since = (datetime.now() - paper.published).days
            if days_since <= 1:
                paper.score += 2.0
            elif days_since <= 3:
                paper.score += 1.0
        
        # 排序
        if sort_by_citations:
            papers.sort(key=lambda p: (-p.citation_count, -p.score))
        else:
            papers.sort(key=lambda p: -p.score)
        
        return papers


def load_config_from_env() -> Dict:
    """从环境变量加载配置"""
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
            'min_score_threshold': 1.0,  # 默认阈值较低，确保有文章
            'sort_by_citations': False,
            'fetch_citations': False,
            'email': {'enabled': False}
        }
        
        # 加载 YAML 配置
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    default_config.update(yaml_config)
        
        # 加载环境变量配置
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
        """执行每日文章抓取和推送"""
        logger.info("=" * 60)
        logger.info("开始执行 arXiv 文章推送任务")
        logger.info("=" * 60)
        
        # 1. 获取所有搜索词
        queries = self.keyword_manager.get_search_queries()
        logger.info(f"搜索查询: {queries}")
        
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
        
        if not all_papers:
            logger.warning("没有找到任何文章，请检查关键词配置")
            return ""
        
        # 3. 过滤已推送的文章
        new_papers = []
        for paper_id, paper in all_papers.items():
            if paper_id not in self.seen_ids:
                new_papers.append(paper)
                self.seen_ids.add(paper_id)
        
        logger.info(f"其中 {len(new_papers)} 篇是新文章")
        
        if not new_papers:
            logger.info("没有新文章需要推送")
            return ""
        
        # 4. 排序
        sort_by_citations = self.config.get('sort_by_citations', False)
        ranked_papers = self.ranker.rank_papers(new_papers, sort_by_citations)
        
        # 5. 应用阈值过滤
        min_score = self.config.get('min_score_threshold', 1.0)
        filtered_papers = [p for p in ranked_papers if p.score >= min_score]
        
        logger.info(f"匹配关键词的文章: {len(ranked_papers)} 篇")
        logger.info(f"通过阈值({min_score})的文章: {len(filtered_papers)} 篇")
        
        if not filtered_papers:
            logger.warning(f"没有文章通过相关性阈值({min_score})，尝试显示得分最高的几篇")
            # 如果没有通过阈值的文章，显示得分最高的前5篇
            filtered_papers = ranked_papers[:5]
        
        # 6. 获取引用次数
        fetch_citations = self.config.get('fetch_citations', False) or sort_by_citations
        if fetch_citations and filtered_papers:
            self.citation_fetcher.batch_get_citations(filtered_papers)
            
            if sort_by_citations:
                filtered_papers.sort(key=lambda p: (-p.citation_count, -p.score))
        
        # 7. 限制数量
        max_papers = self.config.get('max_papers_per_day', 30)
        selected_papers = filtered_papers[:max_papers]
        
        logger.info(f"最终选择 {len(selected_papers)} 篇文章")
        
        # 打印选中的文章
        for i, paper in enumerate(selected_papers, 1):
            logger.info(f"  {i}. {paper.title[:60]}... (得分: {paper.score:.1f})")
        
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
            logger.warning("邮件功能已启用但发送器未初始化")
        elif not selected_papers:
            logger.warning("没有选中的文章，跳过邮件发送")
        
        # 10. 保存历史
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
        
        # 按主题分组
        groups = {
            '产业组织与市场': [],
            '航运与环境': [],
            '其他相关文章': []
        }
        
        for paper in papers:
            matched_text = ' '.join(paper.matched_keywords).lower()
            if any(kw in matched_text for kw in ['航运', '碳', 'ship', 'carbon', 'arctic', 'maritime']):
                groups['航运与环境'].append(paper)
            elif any(kw in matched_text for kw in ['市场', '产业', '定价', 'market', 'industr']):
                groups['产业组织与市场'].append(paper)
            else:
                groups['其他相关文章'].append(paper)
        
        # 生成 Markdown
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 📚 arXiv 每日文章推送 ({today})\n\n")
            f.write(f"> 共筛选出 **{len(papers)}** 篇相关文章\n\n")
            
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
                    
                    if paper.citation_count > 0:
                        f.write(f"- **被引次数**: {paper.citation_count}\n")
                    
                    if paper.matched_keywords:
                        f.write(f"- **匹配关键词**: {', '.join(paper.matched_keywords[:5])}\n")
                    
                    f.write(f"- **链接**: [arXiv]({paper.link})")
                    if paper.pdf_link:
                        f.write(f" | [PDF]({paper.pdf_link})")
                    f.write("\n\n")
                    
                    summary = paper.summary[:800]
                    if len(paper.summary) > 800:
                        summary += "..."
                    f.write(f"> **摘要**: {summary}\n\n")
                    f.write("---\n\n")
            
            f.write("\n*由 arXiv Agent 自动生成*\n")
        
        return filepath
    
    def test_email(self) -> bool:
        """测试邮件配置"""
        if not self.email_sender:
            logger.error("邮件发送器未初始化")
            return False
        return self.email_sender.test_connection()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='arXiv 每日文章推送智能体')
    parser.add_argument('--no-email', action='store_true', help='不发送邮件')
    parser.add_argument('--test-email', action='store_true', help='测试邮件配置')
    parser.add_argument('--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--sort-by-citations', action='store_true', help='按引用排序')
    parser.add_argument('--fetch-citations', action='store_true', help='获取引用次数')
    
    args = parser.parse_args()
    
    agent = ArxivAgent(config_file=args.config)
    
    if args.sort_by_citations:
        agent.config['sort_by_citations'] = True
    if args.fetch_citations:
        agent.config['fetch_citations'] = True
    
    if args.test_email:
        success = agent.test_email()
        exit(0 if success else 1)
    
    report_path = agent.run(send_email=not args.no_email)
    
    if report_path:
        print(f"\n✅ 报告已生成: {report_path}")
    else:
        print("\n⚠️ 未生成报告")
    
    if agent.email_sender and not args.no_email:
        receivers = agent.config.get('email', {}).get('receiver_emails', [])
        print(f"📧 收件人: {', '.join(receivers)}")


if __name__ == "__main__":
    main()
