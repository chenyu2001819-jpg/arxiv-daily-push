#!/usr/bin/env python3
"""
大模型筛选模块
使用 LLM 判断论文与关键词的相关性
"""

import os
import json
import logging
import requests
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str
    model: str
    api_url: str
    temperature: float = 0.3
    max_tokens: int = 1000


class LLMFilter:
    """大模型论文筛选器"""
    
    # 预设的 API 地址
    DEFAULT_APIS = {
        'openai': 'https://api.openai.com/v1/chat/completions',
        'deepseek': 'https://api.deepseek.com/v1/chat/completions',
        'moonshot': 'https://api.moonshot.cn/v1/chat/completions',
        'zhipu': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'gemini': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'claude': 'https://api.anthropic.com/v1/messages',
        'minimax': 'https://api.minimaxi.com/anthropic',
    }
    
    def __init__(self, config: LLMConfig, delay: float = 2.0, max_retries: int = 3):
        self.config = config
        self.delay = delay  # 请求之间的延迟（秒）
        self.max_retries = max_retries  # 最大重试次数
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json'
        })
    
    def _get_api_url(self) -> str:
        """获取 API 地址"""
        url = self.config.api_url
        # 如果是预设的简称，转换为完整 URL
        if url.lower() in self.DEFAULT_APIS:
            url = self.DEFAULT_APIS[url.lower()]
        # 替换 URL 中的 {model} 占位符
        if '{model}' in url:
            url = url.replace('{model}', self.config.model)
        return url
    
    def _call_llm(self, prompt: str) -> str:
        """调用大模型 API"""
        try:
            url = self._get_api_url()
            
            # 判断 API 类型，构建对应的 payload 和 headers
            if 'generativelanguage.googleapis.com' in url:
                # Gemini API 格式
                return self._call_gemini(url, prompt)
            elif 'anthropic.com' in url:
                # Claude API 格式
                return self._call_claude(url, prompt)
            elif 'minimax.chat' in url:
                # MiniMax API 格式
                return self._call_minimax(url, prompt)
            else:
                # OpenAI 兼容格式
                return self._call_openai_compatible(url, prompt)
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"LLM API HTTP 错误: {e}")
            if e.response is not None:
                logger.error(f"响应状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text[:500]}")
            return ''
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ''
    
    def _call_openai_compatible(self, url: str, prompt: str) -> str:
        """调用 OpenAI 兼容格式的 API"""
        payload = {
            'model': self.config.model,
            'messages': [
                {'role': 'system', 'content': '你是一个学术论文分析专家，擅长判断论文与特定研究领域的相关性。'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': self.config.temperature,
            'max_tokens': self.config.max_tokens
        }
        
        response = self.session.post(url, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        # 适配不同 API 的返回格式
        if result.get('choices') and len(result['choices']) > 0:
            choice = result['choices'][0]
            if choice and 'message' in choice:
                return choice['message'].get('content', '')
            elif choice and 'text' in choice:
                return choice['text']
        
        # 检查是否有错误信息
        if 'error' in result:
            logger.error(f"LLM API 返回错误: {result['error']}")
        
        logger.warning(f"无法解析 LLM 响应: {result}")
        return ''
    
    def _call_gemini(self, url: str, prompt: str) -> str:
        """调用 Gemini API"""
        # Gemini 使用 API Key 作为查询参数
        api_key = self.config.api_key
        url = f"{url}?key={api_key}"
        
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': '你是一个学术论文分析专家，擅长判断论文与特定研究领域的相关性。'},
                        {'text': prompt}
                    ]
                }
            ],
            'generationConfig': {
                'temperature': self.config.temperature,
                'maxOutputTokens': self.config.max_tokens
            }
        }
        
        # Gemini 不需要 Authorization header，使用 API key 作为参数
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        # 解析 Gemini 响应格式
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                parts = candidate['content']['parts']
                if parts and 'text' in parts[0]:
                    return parts[0]['text']
        
        logger.warning(f"无法解析 Gemini 响应: {result}")
        return ''
    
    def _call_claude(self, url: str, prompt: str) -> str:
        """调用 Claude API"""
        payload = {
            'model': self.config.model,
            'max_tokens': self.config.max_tokens,
            'temperature': self.config.temperature,
            'system': '你是一个学术论文分析专家，擅长判断论文与特定研究领域的相关性。',
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }
        
        # Claude 使用 x-api-key header
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.config.api_key,
            'anthropic-version': '2023-06-01'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        # 解析 Claude 响应格式
        if 'content' in result and len(result['content']) > 0:
            return result['content'][0].get('text', '')
        
        logger.warning(f"无法解析 Claude 响应: {result}")
        return ''
    
    def _call_minimax(self, url: str, prompt: str) -> str:
        """调用 MiniMax API"""
        # MiniMax 使用特殊的 header 格式
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.config.api_key}'
        }
        
        payload = {
            'model': self.config.model,
            'messages': [
                {'role': 'system', 'content': '你是一个学术论文分析专家，擅长判断论文与特定研究领域的相关性。'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': self.config.temperature,
            'max_tokens': self.config.max_tokens
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        # 检查错误
        if result.get('base_resp') and result['base_resp'].get('status_code') != 0:
            logger.error(f"MiniMax API 错误: {result['base_resp']}")
            return ''
        
        # 解析 MiniMax 响应格式
        if 'choices' in result and result['choices']:
            choice = result['choices'][0]
            if 'message' in choice:
                return choice['message'].get('content', '')
            elif 'text' in choice:
                return choice['text']
        
        logger.warning(f"无法解析 MiniMax 响应: {result}")
        return ''
    
    def evaluate_relevance(self, paper_title: str, paper_summary: str, keywords: List[str]) -> Tuple[float, str]:
        """
        评估论文与关键词的相关性
        
        Args:
            paper_title: 论文标题
            paper_summary: 论文摘要
            keywords: 关键词列表
            
        Returns:
            (相关度分数 0-10, 评估理由)
        """
        keywords_str = ', '.join(keywords[:10])  # 最多取10个关键词
        
        prompt = f"""请评估以下学术论文与给定研究关键词的相关性。

【研究关键词】
{keywords_str}

【论文标题】
{paper_title}

【论文摘要】
{paper_summary[:2000]}  # 限制摘要长度

请按以下格式回复：
相关度分数: [0-10的数字，10表示高度相关，0表示完全不相关]
评估理由: [简要说明为什么给出这个分数，100字以内]

注意：
- 只看论文是否真的研究关键词涉及的主题
- 不要仅因为提到关键词就给出高分
- 要判断论文的核心贡献是否与关键词领域匹配"""

        response = self._call_llm(prompt)
        
        if not response:
            return 0.0, "LLM 调用失败"
        
        # 解析响应
        score = 0.0
        reason = ""
        
        try:
            # 尝试解析分数
            for line in response.split('\n'):
                line = line.strip()
                if '相关度分数' in line or '分数' in line:
                    # 提取数字
                    import re
                    numbers = re.findall(r'\d+\.?\d*', line)
                    if numbers:
                        score = float(numbers[0])
                        if score > 10:  # 如果分数是100分制，转换为10分制
                            score = score / 10
                        score = min(10, max(0, score))  # 限制在0-10
                
                if '评估理由' in line or '理由' in line:
                    reason = line.split(':', 1)[-1].strip()
            
            if not reason:
                reason = response[:200]  # 如果没解析出理由，取前200字
                
        except Exception as e:
            logger.error(f"解析 LLM 响应失败: {e}")
            reason = response[:200] if response else "解析失败"
        
        return score, reason
    
    def filter_papers(self, papers: List, keywords: List[str], min_score: float = 5.0, top_n: int = None) -> List:
        """
        使用 LLM 筛选论文
        
        Args:
            papers: 论文列表
            keywords: 关键词列表
            min_score: 最低相关度分数
            top_n: 只取前N篇（按分数排序）
            
        Returns:
            筛选后的论文列表
        """
        import time
        import random
        
        logger.info(f"开始使用 LLM 筛选 {len(papers)} 篇论文...")
        logger.info(f"请求延迟: {self.delay}秒, 最大重试次数: {self.max_retries}")
        
        scored_papers = []
        
        for i, paper in enumerate(papers):
            logger.info(f"  评估第 {i+1}/{len(papers)} 篇: {paper.title[:50]}...")
            
            # 带重试的评估
            score, reason = 0.0, "评估失败"
            for attempt in range(self.max_retries):
                try:
                    score, reason = self.evaluate_relevance(
                        paper.title, 
                        paper.summary, 
                        keywords
                    )
                    if score > 0:  # 成功获取到分数
                        break
                except Exception as e:
                    logger.warning(f"    第 {attempt + 1} 次尝试失败: {e}")
                    if attempt < self.max_retries - 1:
                        # 指数退避: 2, 4, 8 秒
                        retry_delay = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"    等待 {retry_delay:.1f} 秒后重试...")
                        time.sleep(retry_delay)
            
            # 将分数添加到论文对象
            paper.llm_score = score
            paper.llm_reason = reason
            
            logger.info(f"    分数: {score:.1f}/10, 理由: {reason[:80]}...")
            
            if score >= min_score:
                scored_papers.append((score, paper))
            
            # 延迟，避免 API 限制（Gemini 建议至少 1-2 秒）
            if i < len(papers) - 1:  # 最后一篇不需要延迟
                time.sleep(self.delay)
        
        # 按分数排序
        scored_papers.sort(key=lambda x: -x[0])
        
        # 取前N篇
        if top_n and len(scored_papers) > top_n:
            scored_papers = scored_papers[:top_n]
        
        result = [paper for _, paper in scored_papers]
        
        logger.info(f"LLM 筛选完成: 从 {len(papers)} 篇中选出 {len(result)} 篇 (最低分数: {min_score})")
        
        return result


def load_llm_config_from_env() -> LLMConfig:
    """从环境变量加载 LLM 配置"""
    api_key = os.environ.get('LLM_API_KEY', '')
    model = os.environ.get('LLM_MODEL', 'gpt-3.5-turbo')
    api_url = os.environ.get('LLM_API_URL', 'openai')
    
    if not api_key:
        raise ValueError("未设置 LLM_API_KEY")
    
    return LLMConfig(
        api_key=api_key,
        model=model,
        api_url=api_url
    )


# 测试代码
if __name__ == "__main__":
    # 测试配置
    config = LLMConfig(
        api_key="your-api-key",
        model="gpt-3.5-turbo",
        api_url="openai"
    )
    
    filter = LLMFilter(config)
    
    # 测试评估
    title = "Market Structure and Innovation in the Automobile Industry"
    summary = "This paper examines how market concentration affects R&D investment..."
    keywords = ["market structure", "innovation", "automobile industry"]
    
    score, reason = filter.evaluate_relevance(title, summary, keywords)
    print(f"分数: {score}")
    print(f"理由: {reason}")
