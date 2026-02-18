#!/usr/bin/env python3
"""
arXiv Agent 邮件发送模块
支持 SMTP 发送 HTML 格式邮件
"""

import os
import re
import yaml
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""
    
    # 常见邮箱 SMTP 配置
    SMTP_SERVERS = {
        'qq.com': {'host': 'smtp.qq.com', 'port': 465, 'ssl': True},
        '163.com': {'host': 'smtp.163.com', 'port': 465, 'ssl': True},
        '126.com': {'host': 'smtp.126.com', 'port': 465, 'ssl': True},
        'gmail.com': {'host': 'smtp.gmail.com', 'port': 587, 'ssl': False, 'tls': True},
        'outlook.com': {'host': 'smtp.office365.com', 'port': 587, 'ssl': False, 'tls': True},
        'hotmail.com': {'host': 'smtp.office365.com', 'port': 587, 'ssl': False, 'tls': True},
        'live.com': {'host': 'smtp.office365.com', 'port': 587, 'ssl': False, 'tls': True},
        'yahoo.com': {'host': 'smtp.mail.yahoo.com', 'port': 465, 'ssl': True},
        'icloud.com': {'host': 'smtp.mail.me.com', 'port': 587, 'ssl': False, 'tls': True},
        'aliyun.com': {'host': 'smtp.aliyun.com', 'port': 465, 'ssl': True},
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.smtp_host = config.get('smtp_host', '')
        self.smtp_port = config.get('smtp_port', 587)
        self.sender_email = config.get('sender_email', '')
        self.sender_password = config.get('sender_password', '')
        self.receiver_emails = config.get('receiver_emails', [])
        self.use_ssl = config.get('use_ssl', True)
        self.use_tls = config.get('use_tls', False)
        
        # 自动检测 SMTP 配置
        if not self.smtp_host and self.sender_email:
            self._auto_detect_smtp()
    
    def _auto_detect_smtp(self):
        """根据发件人邮箱自动检测 SMTP 配置"""
        domain = self.sender_email.split('@')[-1].lower()
        
        if domain in self.SMTP_SERVERS:
            server_info = self.SMTP_SERVERS[domain]
            self.smtp_host = server_info['host']
            self.smtp_port = server_info['port']
            self.use_ssl = server_info.get('ssl', False)
            self.use_tls = server_info.get('tls', False)
            logger.info(f"自动检测到 SMTP 配置: {self.smtp_host}:{self.smtp_port}")
        else:
            logger.warning(f"未能自动识别邮箱 {domain} 的 SMTP 配置，请手动配置")
    
    def send_papers_email(self, papers: List, report_path: str, date_str: str = None) -> bool:
        """
        发送论文推送邮件
        
        Args:
            papers: 论文列表
            report_path: 报告文件路径
            date_str: 日期字符串
            
        Returns:
            发送是否成功
        """
        if not self.receiver_emails:
            logger.warning("未配置收件人邮箱，跳过邮件发送")
            return False
        
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 构建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'📚 arXiv 每日文章推送 ({date_str}) - 共{len(papers)}篇'
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.receiver_emails)
            
            # 生成邮件内容
            html_content = self._generate_html_email(papers, date_str)
            text_content = self._generate_text_email(papers, date_str)
            
            # 添加纯文本和 HTML 版本
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 添加附件（Markdown 报告）
            if os.path.exists(report_path):
                with open(report_path, 'rb') as f:
                    attachment = MIMEBase('application', 'octet-stream')
                    attachment.set_payload(f.read())
                    encoders.encode_base64(attachment)
                    attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{os.path.basename(report_path)}"'
                    )
                    msg.attach(attachment)
            
            # 发送邮件
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
            
            if self.use_tls:
                server.starttls()
            
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, self.receiver_emails, msg.as_string())
            server.quit()
            
            logger.info(f"✅ 邮件发送成功！收件人: {', '.join(self.receiver_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False
    
    def _generate_html_email(self, papers: List, date_str: str) -> str:
        """生成 HTML 格式邮件内容"""
        
        # 按主题分组
        groups = {
            '产业组织与市场': [],
            '航运与环境': [],
            '其他相关文章': []
        }
        
        for paper in papers:
            matched_text = ' '.join(paper.matched_keywords).lower()
            if any(kw in matched_text for kw in ['航运', '碳', 'ship', 'carbon', 'arctic', 'maritime', '绿色', 'green']):
                groups['航运与环境'].append(paper)
            elif any(kw in matched_text for kw in ['市场', '产业', '竞争', '定价', 'market', 'industr', 'competition', '需求', '供给']):
                groups['产业组织与市场'].append(paper)
            else:
                groups['其他相关文章'].append(paper)
        
        # 生成 HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
        .group {{ margin-bottom: 30px; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .group-title {{ background: #f8f9fa; padding: 15px 20px; margin: 0; font-size: 18px; color: #495057; border-bottom: 3px solid #dee2e6; }}
        .paper {{ padding: 20px; border-bottom: 1px solid #e9ecef; }}
        .paper:last-child {{ border-bottom: none; }}
        .paper-title {{ font-size: 16px; font-weight: 600; color: #1a73e8; margin: 0 0 10px 0; line-height: 1.4; }}
        .paper-meta {{ font-size: 13px; color: #666; margin-bottom: 10px; }}
        .paper-meta span {{ margin-right: 15px; }}
        .tag {{ display: inline-block; padding: 2px 8px; background: #e3f2fd; color: #1976d2; border-radius: 12px; font-size: 12px; margin-right: 5px; }}
        .tag-keyword {{ background: #f3e5f5; color: #7b1fa2; }}
        .score {{ color: #ff6b6b; font-weight: 600; }}
        .summary {{ font-size: 14px; color: #555; margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; border-left: 3px solid #667eea; }}
        .links {{ margin-top: 10px; }}
        .links a {{ display: inline-block; padding: 5px 15px; margin-right: 10px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; font-size: 13px; }}
        .links a:hover {{ background: #5a6fd6; }}
        .footer {{ text-align: center; margin-top: 30px; padding: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📚 arXiv 每日文章推送</h1>
        <p>{date_str} | 共 {len(papers)} 篇相关文章</p>
    </div>
"""
        
        paper_num = 1
        for group_name, group_papers in groups.items():
            if not group_papers:
                continue
            
            html += f'    <div class="group">\n'
            html += f'        <h2 class="group-title">{group_name} ({len(group_papers)}篇)</h2>\n'
            
            for paper in group_papers:
                authors_str = ', '.join(paper.authors[:3])
                if len(paper.authors) > 3:
                    authors_str += f' 等 {len(paper.authors)} 人'
                
                keywords_html = ''.join([f'<span class="tag tag-keyword">{kw}</span>' for kw in paper.matched_keywords[:5]])
                
                summary = paper.summary[:300] + '...' if len(paper.summary) > 300 else paper.summary
                summary = summary.replace('<', '&lt;').replace('>', '&gt;')  # 转义 HTML
                
                # 构建元信息行，包括引用次数
                pub_date = paper.published.strftime('%Y-%m-%d')
                meta_line = f'<span>👤 {authors_str}</span>'
                meta_line += f'<span>📅 {pub_date}</span>'
                meta_line += f'<span>📂 {paper.primary_category}</span>'
                meta_line += f'<span class="score">⭐ {paper.score:.1f}</span>'
                if paper.citation_count > 0:
                    meta_line += f'<span style="color: #28a745; font-weight: 600;">📈 被引 {paper.citation_count} 次</span>'
                
                html += f"""
        <div class="paper">
            <div class="paper-title">{paper_num}. {paper.title}</div>
            <div class="paper-meta">
                {meta_line}
            </div>
            <div>{keywords_html}</div>
            <div class="summary">{summary}</div>
            <div class="links">
                <a href="{paper.link}" target="_blank">查看详情</a>
                <a href="{paper.pdf_link}" target="_blank">下载 PDF</a>
            </div>
        </div>
"""
                paper_num += 1
            
            html += '    </div>\n'
        
        html += """
    <div class="footer">
        <p>由 arXiv Agent 自动生成 | 如有问题请联系管理员</p>
    </div>
</body>
</html>
"""
        return html
    
    def _generate_text_email(self, papers: List, date_str: str) -> str:
        """生成纯文本格式邮件内容（用于不支持 HTML 的客户端）"""
        text = f"📚 arXiv 每日文章推送 ({date_str})\n"
        text += f"共 {len(papers)} 篇相关文章\n"
        text += "=" * 60 + "\n\n"
        
        for i, paper in enumerate(papers, 1):
            text += f"{i}. {paper.title}\n"
            text += f"   作者: {', '.join(paper.authors[:5])}\n"
            text += f"   日期: {paper.published.strftime('%Y-%m-%d')}\n"
            text += f"   分类: {paper.primary_category}\n"
            text += f"   得分: {paper.score:.1f}\n"
            if paper.citation_count > 0:
                text += f"   被引: {paper.citation_count} 次\n"
            text += f"   链接: {paper.link}\n"
            text += f"   PDF: {paper.pdf_link}\n"
            text += "\n"
        
        text += "\n由 arXiv Agent 自动生成\n"
        return text
    
    def test_connection(self) -> bool:
        """测试邮件连接"""
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            
            if self.use_tls:
                server.starttls()
            
            server.login(self.sender_email, self.sender_password)
            server.quit()
            logger.info("✅ 邮件服务器连接测试成功！")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件服务器连接测试失败: {e}")
            return False


def create_email_config_template():
    """创建邮件配置模板"""
    config = {
        'email': {
            'enabled': True,
            'sender_email': 'your_email@example.com',
            'sender_password': 'your_password_or_auth_code',
            'receiver_emails': ['receiver@example.com'],
            # SMTP 配置（可选，会自动检测常见邮箱）
            'smtp_host': '',
            'smtp_port': 587,
            'use_ssl': True,
            'use_tls': False,
        }
    }
    
    print("""
# 邮件配置说明：

## 常见邮箱配置示例：

### QQ邮箱
sender_email: your_qq@qq.com
sender_password: xxxxxxxx  # QQ邮箱授权码（不是登录密码）

### 163邮箱
sender_email: your_name@163.com
sender_password: xxxxxxxx  # 163邮箱授权码

### Gmail
sender_email: your_name@gmail.com
sender_password: xxxxxxxx  # Gmail应用专用密码
smtp_host: smtp.gmail.com
smtp_port: 587
use_ssl: false
use_tls: true

### Outlook/Hotmail
sender_email: your_name@outlook.com
sender_password: your_password
smtp_host: smtp.office365.com
smtp_port: 587
use_ssl: false
use_tls: true

## 获取授权码方法：
- QQ邮箱: 设置 -> 账户 -> 开启SMTP服务 -> 获取授权码
- 163邮箱: 设置 -> POP3/SMTP -> 开启服务 -> 获取授权码
- Gmail: 账户 -> 安全性 -> 应用专用密码
""")
    
    return config


if __name__ == "__main__":
    # 测试邮件配置
    print("=" * 60)
    print("arXiv Agent 邮件发送模块测试")
    print("=" * 60)
    print()
    
    # 检查配置文件
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        if config.get("email", {}).get("enabled"):
            sender = EmailSender(config["email"])
            sender.test_connection()
        else:
            print("邮件功能未启用，请修改 config.yaml 中的 email.enabled 为 true")
    else:
        print("未找到 config.yaml 文件")
        print()
        create_email_config_template()
